"""Dual-layer data collection: Tavily + AnySearch with iterative heuristic search.

Search strategy:
  1. Initial broad search (5 dimensions × 2 engines = up to 10 data sources)
  2. After L0: search driven by core_need, substitution alternatives, narrative deps
  3. After L1: search driven by identified entities and power dynamics
  4. After L2: search driven by risk accumulation points and hidden subsidies

All results accumulate in a SearchContext that deduplicates and structures data
by category, providing a rich context string for each LLM layer call.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from tavily import TavilyClient

from structflow.config import config


def _year_range() -> str:
    """Generate a dynamic year range string for search queries."""
    current_year = datetime.now().year
    return f"{current_year - 1} {current_year}"


# ──────────────────────────────────────────────────────────────────────
# AnySearch Client
# ──────────────────────────────────────────────────────────────────────

class AnySearchClient:
    """Thin wrapper around the AnySearch MCP API (JSON-RPC 2.0).

    AnySearch provides domain-specific vertical search (finance, business,
    academic, etc.) that complements Tavily's general web search.
    """

    ENDPOINT = "https://api.anysearch.com/mcp"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.anysearch.api_key
        self.endpoint = config.anysearch.endpoint or self.ENDPOINT

    def search(
        self,
        query: str,
        domain: Optional[str] = None,
        max_results: int = 5,
    ) -> str:
        """Execute a search via AnySearch API.

        Args:
            query: Search query string.
            domain: Vertical domain (finance, business, academic, general, etc.).
            max_results: Maximum number of results (capped at 10 by API).

        Returns:
            Formatted text with search results.
        """
        if not self.api_key:
            return ""

        arguments: dict = {"query": query, "max_results": min(max_results, 10)}
        if domain:
            arguments["domain"] = domain

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search", "arguments": arguments},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            resp = requests.post(
                self.endpoint, json=payload, headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return ""

            result = data.get("result", {})
            content = result.get("content", [])
            for item in content:
                if item.get("type") == "text":
                    return item.get("text", "")
            return ""
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────
# Search Context — accumulator for all search results
# ──────────────────────────────────────────────────────────────────────

class SearchContext:
    """Accumulates search results across the pipeline, deduplicates, and
    provides a structured context string for LLM prompts.

    Results are stored by category (e.g., 'industry_overview', 'l0_core_need').
    Each category can have multiple entries from different search engines.
    """

    def __init__(self):
        self._categories: dict[str, list[str]] = {}
        self._queries: set[str] = set()  # Track queries to avoid duplicates

    def add(self, category: str, content: str, query: str = "") -> None:
        """Add search results to a category. Skips if query was already searched."""
        if query and query.lower() in self._queries:
            return
        if query:
            self._queries.add(query.lower())
        if not content or not content.strip():
            return
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(content.strip())

    def has_category(self, category: str) -> bool:
        return category in self._categories and len(self._categories[category]) > 0

    def get_context_string(self, categories: Optional[list[str]] = None) -> str:
        """Return a formatted context string for LLM prompts.

        Args:
            categories: If provided, only include these categories.
                        If None, include all categories.
        """
        parts = []
        cats = categories if categories else list(self._categories.keys())
        for cat in cats:
            if cat not in self._categories:
                continue
            entries = self._categories[cat]
            if not entries:
                continue
            title = cat.replace("_", " ").title()
            parts.append(f"### {title}\n" + "\n\n".join(entries))
        return "\n\n".join(parts)

    def get_all_categories(self) -> list[str]:
        return list(self._categories.keys())

    @property
    def total_sources(self) -> int:
        return sum(len(entries) for entries in self._categories.values())


# ──────────────────────────────────────────────────────────────────────
# Dual Search Collector
# ──────────────────────────────────────────────────────────────────────

class DataCollector:
    """Dual-layer data collector using Tavily + AnySearch.

    Search flow:
      1. collect_initial() — broad multi-dimensional search (both engines)
      2. collect_after_l0() — driven by L0 output (core_need, substitution, etc.)
      3. collect_after_l1() — driven by L1 entities and power dynamics
      4. collect_after_l2() — driven by L2 risk accumulation points

    All results accumulate in a SearchContext, which is passed to each LLM
    layer as enriched context data.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        anysearch_key: Optional[str] = None,
    ):
        # Tavily (primary)
        self.tavily_key = api_key or config.tavily.api_key
        if not self.tavily_key:
            raise ValueError(
                "Tavily API key not configured. Set TAVILY_API_KEY in .env or pass --tavily-key"
            )
        self.tavily = TavilyClient(api_key=self.tavily_key)

        # AnySearch (complementary)
        self.anysearch_key = anysearch_key or config.anysearch.api_key
        self.anysearch = AnySearchClient(api_key=self.anysearch_key) if self.anysearch_key else None

        # Search context accumulator
        self.context = SearchContext()

    def _dual_search(
        self,
        query: str,
        category: str,
        tavily_depth: str = "advanced",
        tavily_max: int = 5,
        anysearch_domain: Optional[str] = None,
        anysearch_max: int = 3,
    ) -> None:
        """Execute a search on both engines and add results to context."""
        # Tavily search
        tavily_result = ""
        try:
            response = self.tavily.search(
                query=query,
                search_depth=tavily_depth,
                max_results=tavily_max,
                include_answer=True,
            )
            tavily_result = self._format_tavily_results(response)
        except Exception:
            pass
        self.context.add(category, tavily_result, query=f"tavily:{query}")

        # AnySearch search (complementary)
        if self.anysearch:
            anysearch_result = ""
            try:
                anysearch_result = self.anysearch.search(
                    query=query,
                    domain=anysearch_domain,
                    max_results=anysearch_max,
                )
            except Exception:
                pass
            if anysearch_result:
                self.context.add(category, anysearch_result, query=f"anysearch:{query}")

    # ── Phase 1: Initial broad search ─────────────────────────────

    def collect_initial(
        self,
        industry: str,
        region: Optional[str] = None,
        peer_set: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """Initial broad multi-dimensional search across both engines.

        Searches 6 dimensions:
        - Industry overview (general domain)
        - Market structure (business domain)
        - Policy & regulation (general domain)
        - Risk landscape (finance domain)
        - Revenue model (business domain)
        - M&A and consolidation (business domain) — catches acquired/merged entities
        """
        region_str = f" in {region}" if region else ""
        years = _year_range()

        # 1. Industry overview
        self._dual_search(
            query=f"{industry}{region_str} industry overview market share competition {years}",
            category="industry_overview",
            anysearch_domain="general",
        )

        # 2. Market structure
        self._dual_search(
            query=f"{industry}{region_str} market structure concentration barriers to entry competitive landscape {years}",
            category="market_structure",
            anysearch_domain="business",
        )

        # 3. Policy & regulation
        self._dual_search(
            query=f"{industry} policy regulation government subsidy{region_str} {years}",
            category="policy_context",
            anysearch_domain="general",
        )

        # 4. Risk landscape
        self._dual_search(
            query=f"{industry}{region_str} industry risks regulatory risk financial risk systemic risk {years}",
            category="risk_landscape",
            anysearch_domain="finance",
        )

        # 5. Revenue model
        self._dual_search(
            query=f"{industry}{region_str} revenue model pricing structure value chain profit margin {years}",
            category="revenue_model",
            anysearch_domain="business",
        )

        # 6. M&A and consolidation — detect acquired/merged entities
        self._dual_search(
            query=f"{industry}{region_str} merger acquisition consolidation restructuring {years}",
            category="ma_activity",
            anysearch_domain="business",
        )

        # Discover competitors if no peers provided
        if not peer_set:
            discovered = self._discover_competitors(industry, region)
            if discovered:
                peer_set = discovered
                self.context.add(
                    "discovered_competitors",
                    ", ".join(discovered),
                )

        # Search for each company
        if peer_set:
            for company in peer_set:
                self._dual_search(
                    query=f"{company} {industry} revenue market share business model {years}",
                    category=f"company_{company}",
                    anysearch_domain="finance",
                )

        return self._export_raw()

    # ── Phase 2: Iterative search after L0 ────────────────────────

    def collect_after_l0(
        self,
        industry: str,
        l0_result,
        region: Optional[str] = None,
    ) -> None:
        """Heuristic search driven by L0 output.

        L0 identifies:
        - core_need: what rigid demand does this industry fulfill?
        - substitution_risk: how easily substituted?
        - demand_stability: how stable is demand?
        - narrative_dependency: how dependent on policy/narrative?

        Each of these should trigger targeted searches to provide data
        for deeper layers (L1/L2/L3).
        """
        region_str = f" in {region}" if region else ""
        years = _year_range()

        # Search for the core need — what drives demand?
        if l0_result.core_need:
            self._dual_search(
                query=f"{l0_result.core_need} demand drivers market size{region_str} {years}",
                category="l0_core_need",
                anysearch_domain="general",
            )

        # If substitution risk is high, search for alternatives
        if l0_result.substitution_risk > 0.4:
            self._dual_search(
                query=f"{industry} alternatives substitutes replacement technology{region_str} {years}",
                category="l0_substitution",
                anysearch_domain="general",
            )

        # If narrative dependency is high, search for policy/narrative context
        if l0_result.narrative_dependency > 0.4:
            self._dual_search(
                query=f"{industry} policy narrative regulation government intervention{region_str} {years}",
                category="l0_narrative",
                anysearch_domain="general",
            )

        # If demand stability is low, search for demand volatility factors
        if l0_result.demand_stability < 0.6:
            self._dual_search(
                query=f"{industry} demand volatility cyclicality seasonal factors {years}",
                category="l0_demand_volatility",
                anysearch_domain="finance",
            )

    # ── Phase 3: Iterative search after L1 ────────────────────────

    def collect_after_l1(
        self,
        industry: str,
        l1_result,
    ) -> None:
        """Heuristic search driven by L1 output — entity power dynamics.

        L1 identifies 4 roles and a power matrix. We search for each
        key entity's competitive position and power dynamics.
        """
        years = _year_range()

        # Collect all entities from L1
        l1_entities = []
        for role in l1_result.roles:
            l1_entities.extend(role.entities)

        # Search for top 5 entities' power and competitive position
        for entity in l1_entities[:5]:
            self._dual_search(
                query=f"{entity} {industry} market power competitive advantage pricing control {years}",
                category=f"l1_entity_{entity}",
                anysearch_domain="business",
                tavily_max=3,
                anysearch_max=2,
            )

        # Search for power matrix dynamics
        power = l1_result.power_matrix
        # If there's interesting pricing power info, search for pricing dynamics
        if power.pricing_power and len(power.pricing_power) > 10:
            self._dual_search(
                query=f"{industry} pricing power dynamics price competition {years}",
                category="l1_pricing_dynamics",
                anysearch_domain="finance",
            )

    # ── Phase 4: Iterative search after L2 ────────────────────────

    def collect_after_l2(
        self,
        industry: str,
        l2_result,
    ) -> None:
        """Heuristic search driven by L2 output — risk and flow details.

        L2 identifies cash flow chains, risk accumulation points, hidden
        subsidies, and information asymmetry. We search for specifics.
        """
        years = _year_range()

        # Search for each risk accumulation point
        risk_keywords = [n.entity for n in l2_result.risk_accumulation_points]
        for keyword in risk_keywords[:3]:
            self._dual_search(
                query=f"{industry} {keyword} risk concentration systemic {years}",
                category=f"l2_risk_{keyword}",
                anysearch_domain="finance",
                tavily_max=3,
                anysearch_max=2,
            )

        # Search for hidden subsidies if identified
        if l2_result.hidden_subsidy_sources:
            for sub in l2_result.hidden_subsidy_sources[:2]:
                self._dual_search(
                    query=f"{industry} {sub.entity} subsidy hidden support {years}",
                    category=f"l2_subsidy_{sub.entity}",
                    anysearch_domain="general",
                    tavily_max=3,
                    anysearch_max=2,
                )

        # Search for profit-risk separation if identified
        if l2_result.profit_risk_separation_answer and len(l2_result.profit_risk_separation_answer) > 10:
            self._dual_search(
                query=f"{industry} profit risk separation moral hazard {years}",
                category="l2_profit_risk",
                anysearch_domain="finance",
                tavily_max=3,
                anysearch_max=2,
            )

    # ── Competitor discovery ──────────────────────────────────────

    def _discover_competitors(
        self,
        industry: str,
        region: Optional[str] = None,
    ) -> list[str]:
        """Discover key players through search."""
        region_str = f" in {region}" if region else ""
        years = _year_range()
        query = f"top companies {industry}{region_str} market leaders key players {years}"

        try:
            response = self.tavily.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
            )
        except Exception:
            return []

        competitors: list[str] = []
        for result in response.get("results", []):
            title = result.get("title", "")
            if " - " in title:
                name = title.split(" - ")[0].strip()
                if name and len(name) < 50:
                    competitors.append(name)

        seen = set()
        unique = []
        for c in competitors:
            if c.lower() not in seen:
                seen.add(c.lower())
                unique.append(c)

        return unique[:5]

    # ── Formatting helpers ────────────────────────────────────────

    def _format_tavily_results(self, response: dict) -> str:
        """Format Tavily response into structured context string."""
        lines = []
        if response.get("answer"):
            lines.append(f"## Summary\n{response['answer']}\n")
        results = response.get("results", [])
        if results:
            lines.append("## Sources\n")
            for i, result in enumerate(results, 1):
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                content = result.get("content", "")
                lines.append(f"### {i}. {title}")
                lines.append(f"URL: {url}")
                lines.append(f"Content: {content}\n")
        return "\n".join(lines)

    def _export_raw(self) -> dict[str, str]:
        """Export context as a flat dict for OutputValidator compatibility."""
        raw = {}
        for cat, entries in self.context._categories.items():
            raw[cat] = "\n\n".join(entries)
        return raw

    # ── Context access ────────────────────────────────────────────

    def get_context_data(
        self,
        include_categories: Optional[list[str]] = None,
        exclude_categories: Optional[list[str]] = None,
    ) -> str:
        """Get formatted context string for LLM prompts.

        Args:
            include_categories: Only include these categories.
            exclude_categories: Exclude these categories.
        """
        cats = include_categories
        if exclude_categories:
            all_cats = self.context.get_all_categories()
            cats = [c for c in all_cats if c not in exclude_categories]
        return self.context.get_context_string(cats)

    @property
    def total_sources(self) -> int:
        return self.context.total_sources

    def save_to_directory(self, directory: str | Path) -> Path:
        """Save all search context data to a JSON file in the given directory.

        The file includes:
        - All search queries executed (deduplicated)
        - All search results grouped by category
        - Metadata: industry, timestamp, total sources, engines used

        Returns the path to the saved file.
        """
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)

        export = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_sources": self.context.total_sources,
                "categories": list(self.context.get_all_categories()),
                "queries_executed": sorted(self.context._queries),
                "engines": {
                    "tavily": True,
                    "anysearch": self.anysearch is not None,
                },
            },
            "categories": {},
        }
        for cat, entries in self.context._categories.items():
            export["categories"][cat] = entries

        file_path = dir_path / "search_data.json"
        file_path.write_text(
            json.dumps(export, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path
