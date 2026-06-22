"""Dual-layer data collection: Tavily + AnySearch with iterative heuristic search.

V2.1: Search stages adapted for Meta-Generalization Layer.
  1. Initial broad search (6 dimensions × 2 engines)
  2. After L0: search driven by system_type, core_function, state_variables
  3. After L1: search driven by specific variables (SV/FV/CV/LV)
  4. After L2: search driven by system equation dynamics
  5. After L3: search driven by each driver factor
  6. After L4: search driven by regime indicators
  7. After L5: search driven by distortion/mispricing evidence
  8. After L6: search driven by alpha signal validation
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
    current_year = datetime.now().year
    return f"{current_year - 1} {current_year}"


# ──────────────────────────────────────────────────────────────────────
# AnySearch Client
# ──────────────────────────────────────────────────────────────────────

class AnySearchClient:
    ENDPOINT = "https://api.anysearch.com/mcp"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.anysearch.api_key
        self.endpoint = config.anysearch.endpoint or self.ENDPOINT

    def search(self, query: str, domain: Optional[str] = None, max_results: int = 5) -> str:
        if not self.api_key:
            return ""
        arguments: dict = {"query": query, "max_results": min(max_results, 10)}
        if domain:
            arguments["domain"] = domain
        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "search", "arguments": arguments},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=30)
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
# Search Context
# ──────────────────────────────────────────────────────────────────────

class SearchContext:
    def __init__(self):
        self._categories: dict[str, list[str]] = {}
        self._queries: set[str] = set()

    def add(self, category: str, content: str, query: str = "") -> None:
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
    def __init__(self, api_key: Optional[str] = None, anysearch_key: Optional[str] = None, output_dir: Optional[str] = None):
        self.tavily_key = api_key or config.tavily.api_key
        if not self.tavily_key:
            raise ValueError("Tavily API key not configured. Set TAVILY_API_KEY in .env or pass --tavily-key")
        self.tavily = TavilyClient(api_key=self.tavily_key)
        self.anysearch_key = anysearch_key or config.anysearch.api_key
        self.anysearch = AnySearchClient(api_key=self.anysearch_key) if self.anysearch_key else None
        self.context = SearchContext()
        self._output_dir = Path(output_dir) if output_dir else None

    def _dual_search(self, query: str, category: str, tavily_depth: str = "advanced",
                     tavily_max: int = 5, anysearch_domain: Optional[str] = None, anysearch_max: int = 3) -> None:
        tavily_result = ""
        try:
            response = self.tavily.search(query=query, search_depth=tavily_depth, max_results=tavily_max, include_answer=True)
            tavily_result = self._format_tavily_results(response)
        except Exception:
            pass
        self.context.add(category, tavily_result, query=f"tavily:{query}")
        if self.anysearch:
            anysearch_result = ""
            try:
                anysearch_result = self.anysearch.search(query=query, domain=anysearch_domain, max_results=anysearch_max)
            except Exception:
                pass
            if anysearch_result:
                self.context.add(category, anysearch_result, query=f"anysearch:{query}")

    # ── Phase 1: Initial broad search ─────────────────────────

    def collect_initial(self, industry: str, region: Optional[str] = None, peer_set: Optional[list[str]] = None) -> dict[str, str]:
        region_str = f" in {region}" if region else ""
        years = _year_range()

        self._dual_search(f"{industry}{region_str} industry overview market share competition {years}", "industry_overview", anysearch_domain="general")
        self._dual_search(f"{industry}{region_str} market structure concentration barriers to entry {years}", "market_structure", anysearch_domain="business")
        self._dual_search(f"{industry} policy regulation government intervention{region_str} {years}", "policy_context", anysearch_domain="general")
        self._dual_search(f"{industry}{region_str} systemic risk financial risk operational risk {years}", "risk_landscape", anysearch_domain="finance")
        self._dual_search(f"{industry}{region_str} revenue model pricing value chain profit margin {years}", "revenue_model", anysearch_domain="business")
        self._dual_search(f"{industry}{region_str} merger acquisition consolidation {years}", "ma_activity", anysearch_domain="business")

        if not peer_set:
            discovered = self._discover_competitors(industry, region)
            if discovered:
                peer_set = discovered
                self.context.add("discovered_competitors", ", ".join(discovered))

        if peer_set:
            for company in peer_set:
                self._dual_search(f"{company} {industry} revenue market share {years}", f"company_{company}", anysearch_domain="finance")

        self._save_incremental()
        return self._export_raw()

    def _save_incremental(self) -> None:
        if not self._output_dir:
            return
        try:
            self.save_to_directory(self._output_dir)
        except Exception:
            pass

    # ── Phase 2: Iterative search after L0 ────────────────────

    def collect_after_l0(self, industry: str, l0_result, region: Optional[str] = None) -> None:
        region_str = f" in {region}" if region else ""
        years = _year_range()

        if l0_result.system_type:
            self._dual_search(f"{industry} {l0_result.system_type} system dynamics {years}", "l0_system_type", anysearch_domain="general")
        if l0_result.core_function:
            self._dual_search(f"{l0_result.core_function} demand drivers market {years}", "l0_core_function", anysearch_domain="general")
        if l0_result.exogenous_drivers:
            for driver in l0_result.exogenous_drivers[:3]:
                self._dual_search(f"{industry} {driver} exogenous impact {years}", "l0_exogenous", anysearch_domain="general", tavily_max=3)

        self._save_incremental()

    # ── Phase 3: Iterative search after L1 ────────────────────

    def collect_after_l1(self, industry: str, l1_result) -> None:
        years = _year_range()

        for var in l1_result.state_variables[:3]:
            self._dual_search(f"{industry} {var} state variable capacity stock {years}", f"l1_sv_{var[:30]}", anysearch_domain="finance", tavily_max=3, anysearch_max=2)
        for var in l1_result.control_variables[:3]:
            self._dual_search(f"{industry} {var} control regulation policy {years}", f"l1_cv_{var[:30]}", anysearch_domain="general", tavily_max=3, anysearch_max=2)
        for var in l1_result.latent_variables[:2]:
            self._dual_search(f"{industry} {var} sentiment expectations confidence {years}", f"l1_lv_{var[:30]}", anysearch_domain="general", tavily_max=3, anysearch_max=2)

        self._save_incremental()

    # ── Phase 4: Iterative search after L2 ────────────────────

    def collect_after_l2(self, industry: str, l2_result) -> None:
        years = _year_range()
        self._dual_search(f"{industry} system dynamics flow control latent variables {years}", "l2_dynamics", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Phase 5: Iterative search after L3 ────────────────────

    def collect_after_l3(self, industry: str, l3_result) -> None:
        years = _year_range()
        for driver in l3_result.drivers[:5]:
            self._dual_search(f"{industry} {driver.name} driver impact forecast {years}", f"l3_driver_{driver.name[:30]}", anysearch_domain="finance", tavily_max=3, anysearch_max=2)
        self._save_incremental()

    # ── Phase 6: Iterative search after L4 ────────────────────

    def collect_after_l4(self, industry: str, l4_result) -> None:
        years = _year_range()
        self._dual_search(f"{industry} {l4_result.current_regime} regime indicators signals {years}", "l4_regime", anysearch_domain="finance", tavily_max=3)
        for driver in l4_result.regime_drivers[:3]:
            self._dual_search(f"{industry} {driver} regime driver {years}", "l4_regime_driver", anysearch_domain="general", tavily_max=3, anysearch_max=2)
        self._save_incremental()

    # ── Phase 7: Iterative search after L5 ────────────────────

    def collect_after_l5(self, industry: str, l5_result) -> None:
        years = _year_range()
        if l5_result.market_belief:
            self._dual_search(f"{industry} market consensus analyst outlook narrative {years}", "l5_consensus", anysearch_domain="general", tavily_max=3)
        for source in l5_result.mispricing_sources[:3]:
            self._dual_search(f"{industry} {source} mispricing undervalued overvalued {years}", "l5_mispricing", anysearch_domain="finance", tavily_max=3, anysearch_max=2)
        self._save_incremental()

    # ── Phase 8: Iterative search after L6 ────────────────────

    def collect_after_l6(self, industry: str, l6_result) -> None:
        years = _year_range()
        if l6_result.alpha_signal:
            self._dual_search(f"{industry} {l6_result.alpha_signal[:100]} alpha signal evidence {years}", "l6_alpha", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Competitor discovery ──────────────────────────────────

    def _discover_competitors(self, industry: str, region: Optional[str] = None) -> list[str]:
        region_str = f" in {region}" if region else ""
        years = _year_range()
        query = f"top companies {industry}{region_str} market leaders {years}"
        try:
            response = self.tavily.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
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

    # ── Formatting helpers ────────────────────────────────────

    def _format_tavily_results(self, response: dict) -> str:
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
        raw = {}
        for cat, entries in self.context._categories.items():
            raw[cat] = "\n\n".join(entries)
        return raw

    # ── Context access ────────────────────────────────────────

    # Layer-to-context prefix mapping: each layer gets only relevant search categories.
    # This prevents hallucination, attention drift, and context explosion.
    LAYER_CONTEXT_PREFIXES: dict[str, list[str]] = {
        "l0": [
            "industry_overview", "market_structure", "policy_context",
            "risk_landscape", "revenue_model", "ma_activity",
        ],
        "l1": [
            "industry_overview", "market_structure", "policy_context",
            "l0_",
        ],
        "l2": [
            "l1_", "market_structure", "risk_landscape",
        ],
        "l3": [
            "l2_", "l1_", "policy_context", "industry_overview",
        ],
        "l4": [
            "l3_", "l4_", "risk_landscape", "industry_overview",
        ],
        "l5": [
            "l5_", "revenue_model", "industry_overview",
        ],
        "l6": [
            "l6_", "l5_", "risk_landscape",
        ],
        "l7": [
            "company_", "l4_", "l5_", "ma_activity",
        ],
    }

    def get_context_for_layer(self, layer: str) -> str:
        """Get search context relevant to a specific pipeline layer.

        Instead of dumping ALL accumulated search results, this method
        returns only the categories relevant to the given layer.
        This prevents:
        - Hallucination: irrelevant context causes spurious connections
        - Attention drift: LLM focuses on irrelevant parts of a huge context
        - Context explosion: later layers get O(n) context instead of O(1)
        """
        prefixes = self.LAYER_CONTEXT_PREFIXES.get(layer)
        if not prefixes:
            # Fallback: return all context for unknown layers
            return self.get_context_data()

        all_cats = self.context.get_all_categories()
        relevant_cats = []
        for cat in all_cats:
            if any(cat == prefix or cat.startswith(prefix) for prefix in prefixes):
                relevant_cats.append(cat)

        return self.context.get_context_string(relevant_cats)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate for mixed Chinese/English text.

        Chinese: ~1.5 chars per token (conservative)
        English: ~4 chars per token
        Mixed: use ~3 chars per token as heuristic
        """
        if not text:
            return 0
        return len(text) // 3

    def get_context_data(self, include_categories: Optional[list[str]] = None, exclude_categories: Optional[list[str]] = None) -> str:
        cats = include_categories
        if exclude_categories:
            all_cats = self.context.get_all_categories()
            cats = [c for c in all_cats if c not in exclude_categories]
        return self.context.get_context_string(cats)

    @property
    def total_sources(self) -> int:
        return self.context.total_sources

    def save_to_directory(self, directory: str | Path) -> Path:
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        export = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_sources": self.context.total_sources,
                "categories": list(self.context.get_all_categories()),
                "queries_executed": sorted(self.context._queries),
                "engines": {"tavily": True, "anysearch": self.anysearch is not None},
            },
            "categories": {},
        }
        for cat, entries in self.context._categories.items():
            export["categories"][cat] = entries
        file_path = dir_path / "search_data.json"
        file_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
        return file_path
