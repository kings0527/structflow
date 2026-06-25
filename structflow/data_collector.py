"""V2.2 Dual-layer data collection with bilingual search + query shortening.

Key improvements:
1. Bilingual search: split "eth 以太坊" → search "ethereum" on Tavily, "以太坊" on AnySearch
2. Query shortening: extract key phrases from long LLM outputs (not full sentences)
3. Per-layer context delivery: each layer gets only relevant search categories
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
    return f"{datetime.now().year - 1} {datetime.now().year}"


# ──────────────────────────────────────────────────────────────────────
# Bilingual industry name utilities
# ──────────────────────────────────────────────────────────────────────

# Common Chinese→English industry term mapping for better English searches
_ZH_EN_MAP: dict[str, str] = {
    "以太坊": "ethereum",
    "比特币": "bitcoin",
    "半导体": "semiconductor",
    "化工": "chemical industry",
    "新能源": "renewable energy",
    "人工智能": "artificial intelligence",
    "云计算": "cloud computing",
    "电动车": "electric vehicle",
    "锂电池": "lithium battery",
    "光伏": "solar photovoltaic",
    "稀土": "rare earth",
    "石油": "petroleum",
    "天然气": "natural gas",
    "钢铁": "steel",
    "铝业": "aluminum industry",
    "医药": "pharmaceutical",
    "银行": "banking",
    "保险": "insurance",
    "房地产": "real estate",
    "消费电子": "consumer electronics",
    "游戏": "gaming",
    "电商": "e-commerce",
    "物流": "logistics",
    "军工": "defense industry",
    "农业": "agriculture",
    "食品": "food industry",
    "白酒": "baijiu liquor",
    "黄金": "gold",
    "铜": "copper",
    "煤炭": "coal",
}


def split_bilingual(industry: str) -> dict[str, str]:
    """Split a bilingual industry name into Chinese and English parts.

    "eth 以太坊" → {"zh": "以太坊", "en": "eth ethereum", "raw": "eth 以太坊"}
    "semiconductor" → {"zh": "", "en": "semiconductor", "raw": "semiconductor"}
    """
    zh_chars = re.findall(r'[\u4e00-\u9fff]+', industry)
    en_words = re.findall(r'[a-zA-Z]+', industry)

    zh = " ".join(zh_chars) if zh_chars else ""
    en = " ".join(en_words) if en_words else ""

    # Enhance English with known translations
    for zh_term, en_term in _ZH_EN_MAP.items():
        if zh_term in zh and en_term not in en:
            en = f"{en} {en_term}".strip()
        if en_term in en.lower() and zh_term not in zh:
            zh = f"{zh} {zh_term}".strip()

    return {"zh": zh, "en": en, "raw": industry}


def shorten_for_query(text: str, max_len: int = 50) -> str:
    """Extract a short, focused search phrase from a long LLM output text.

    - Removes parenthetical content (details, examples)
    - Takes the first phrase (split by common delimiters)
    - Truncates to max_len
    """
    if not text:
        return ""
    # Remove parenthetical content: （...）or (...)
    cleaned = re.sub(r'[（(].*?[)）]', '', text).strip()
    # Take first phrase
    for delim in ['；', ';', '，', ',', '。', '.', '：', ':']:
        if delim in cleaned:
            cleaned = cleaned.split(delim)[0].strip()
            break
    # Truncate to max_len
    if len(cleaned) > max_len:
        # Try to cut at word boundary
        truncated = cleaned[:max_len]
        if ' ' in truncated:
            truncated = truncated.rsplit(' ', 1)[0]
        cleaned = truncated
    return cleaned


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
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "search", "arguments": arguments}}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        try:
            resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return ""
            result = data.get("result", {})
            for item in result.get("content", []):
                if item.get("type") == "text":
                    return item.get("text", "")
            return ""
        except Exception:
            return ""


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
        self._categories.setdefault(category, []).append(content.strip())

    def get_context_string(self, categories: Optional[list[str]] = None) -> str:
        parts = []
        cats = categories if categories else list(self._categories.keys())
        for cat in cats:
            entries = self._categories.get(cat, [])
            if entries:
                parts.append(f"### {cat.replace('_', ' ').title()}\n" + "\n\n".join(entries))
        return "\n\n".join(parts)

    def get_all_categories(self) -> list[str]:
        return list(self._categories.keys())

    @property
    def total_sources(self) -> int:
        return sum(len(e) for e in self._categories.values())


# ──────────────────────────────────────────────────────────────────────
# Dual Search Collector with Bilingual Support
# ──────────────────────────────────────────────────────────────────────

class DataCollector:
    def __init__(self, api_key: Optional[str] = None, anysearch_key: Optional[str] = None,
                 output_dir: Optional[str] = None, industry: str = ""):
        self.tavily_key = api_key or config.tavily.api_key
        if not self.tavily_key:
            raise ValueError("Tavily API key not configured.")
        self.tavily = TavilyClient(api_key=self.tavily_key)
        self.anysearch_key = anysearch_key or config.anysearch.api_key
        self.anysearch = AnySearchClient(api_key=self.anysearch_key) if self.anysearch_key else None
        self.context = SearchContext()
        self._output_dir = Path(output_dir) if output_dir else None

        # Bilingual industry name split — cached for all searches
        self._industry_parts = split_bilingual(industry) if industry else {"zh": "", "en": "", "raw": industry}

    def _bilingual_search(self, query_suffix: str, category: str,
                          tavily_depth: str = "advanced", tavily_max: int = 5,
                          anysearch_domain: Optional[str] = None, anysearch_max: int = 3) -> None:
        """Bilingual search: use English for Tavily, Chinese for AnySearch general domain.

        If industry name is bilingual (e.g., "eth 以太坊"):
        - Tavily: "{english_name} {query_suffix}" (English-leaning search engine)
        - AnySearch general: "{chinese_name} {query_suffix}" (Chinese vertical search)
        - AnySearch finance: "{english_name} {query_suffix}" (English financial data)

        If monolingual, uses the single language for all engines.
        """
        parts = self._industry_parts
        zh_name = parts["zh"]
        en_name = parts["en"]
        raw_name = parts["raw"]

        # Determine search language
        is_bilingual = bool(zh_name and en_name)

        # ── Tavily search (English-leaning) ──
        tavily_query = f"{en_name} {query_suffix}" if is_bilingual else f"{raw_name} {query_suffix}"
        tavily_result = ""
        try:
            response = self.tavily.search(query=tavily_query, search_depth=tavily_depth,
                                          max_results=tavily_max, include_answer=True)
            tavily_result = self._format_tavily_results(response)
        except Exception:
            pass
        self.context.add(category, tavily_result, query=f"tavily:{tavily_query}")

        # ── AnySearch (bilingual if available) ──
        if self.anysearch:
            if is_bilingual and anysearch_domain == "general":
                # Use Chinese for general domain searches
                zh_query = f"{zh_name} {query_suffix}"
                try:
                    result = self.anysearch.search(query=zh_query, domain=anysearch_domain, max_results=anysearch_max)
                    if result:
                        self.context.add(category, result, query=f"anysearch_zh:{zh_query}")
                except Exception:
                    pass
            else:
                # Use English for finance/business domains or monolingual
                en_query = f"{en_name} {query_suffix}" if is_bilingual else f"{raw_name} {query_suffix}"
                try:
                    result = self.anysearch.search(query=en_query, domain=anysearch_domain, max_results=anysearch_max)
                    if result:
                        self.context.add(category, result, query=f"anysearch:{en_query}")
                except Exception:
                    pass

    # Keep backward compatibility — _dual_search delegates to _bilingual_search
    def _dual_search(self, query: str, category: str, **kwargs) -> None:
        """Legacy method — use _bilingual_search for new code."""
        # Split the query back into industry + suffix (best effort)
        # This is used when query is pre-built (e.g., in collect_initial)
        parts = self._industry_parts
        for name in [parts["en"], parts["zh"], parts["raw"]]:
            if name and query.startswith(name + " "):
                suffix = query[len(name) + 1:]
                self._bilingual_search(suffix, category, **kwargs)
                return
        # Fallback: search as-is
        tavily_result = ""
        try:
            response = self.tavily.search(query=query, search_depth=kwargs.get("tavily_depth", "advanced"),
                                          max_results=kwargs.get("tavily_max", 5), include_answer=True)
            tavily_result = self._format_tavily_results(response)
        except Exception:
            pass
        self.context.add(category, tavily_result, query=f"tavily:{query}")

    # ── Per-layer context mapping ──────────────────────────────
    LAYER_CONTEXT_PREFIXES: dict[str, list[str]] = {
        "l0": ["industry_overview", "market_structure", "policy_context", "risk_landscape", "revenue_model", "ma_activity"],
        "l1": ["industry_overview", "market_structure", "policy_context", "l0_"],
        "l2": ["l1_", "policy_context", "industry_overview"],
        "l3": ["l2_", "l1_", "market_structure"],
        "nonlinear": ["l3_", "l2_", "l1_", "risk_landscape"],
        "l4": ["l3_", "l4_", "nonlinear_", "risk_landscape", "industry_overview"],
        "l5": ["l5_", "revenue_model", "industry_overview"],
        "l6": ["l6_", "l5_", "risk_landscape"],
        "l7": ["company_", "l4_", "l5_", "ma_activity"],
    }

    def get_context_for_layer(self, layer: str) -> str:
        prefixes = self.LAYER_CONTEXT_PREFIXES.get(layer)
        if not prefixes:
            return self.get_context_data()
        all_cats = self.context.get_all_categories()
        relevant = [c for c in all_cats if any(c == p or c.startswith(p) for p in prefixes)]
        return self.context.get_context_string(relevant)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 3 if text else 0

    # ── Phase 1: Initial broad search ─────────────────────────
    def collect_initial(self, industry: str, region: Optional[str] = None,
                        peer_set: Optional[list[str]] = None) -> dict[str, str]:
        # Update bilingual split if industry changed
        if industry and industry != self._industry_parts.get("raw"):
            self._industry_parts = split_bilingual(industry)

        region_str = f" in {region}" if region else ""
        years = _year_range()

        self._bilingual_search(f"industry overview market share {region_str} {years}", "industry_overview", anysearch_domain="general")
        self._bilingual_search(f"market structure concentration barriers {region_str} {years}", "market_structure", anysearch_domain="business")
        self._bilingual_search(f"policy regulation government {region_str} {years}", "policy_context", anysearch_domain="general")
        self._bilingual_search(f"systemic risk financial risk {region_str} {years}", "risk_landscape", anysearch_domain="finance")
        self._bilingual_search(f"revenue model pricing value chain {region_str} {years}", "revenue_model", anysearch_domain="business")
        self._bilingual_search(f"merger acquisition consolidation {region_str} {years}", "ma_activity", anysearch_domain="business")

        if not peer_set:
            discovered = self._discover_competitors(industry, region)
            if discovered:
                peer_set = discovered
                self.context.add("discovered_competitors", ", ".join(discovered))
        if peer_set:
            for c in peer_set:
                self._bilingual_search(f"{c} revenue market share {years}", f"company_{c}", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()
        return self._export_raw()

    def _save_incremental(self) -> None:
        if self._output_dir:
            try: self.save_to_directory(self._output_dir)
            except Exception: pass

    # ── Phase 2: After L0 ─────────────────────────────────────
    def collect_after_l0(self, industry: str, l0_result, region: Optional[str] = None) -> None:
        years = _year_range()
        # Shorten LLM output for query — don't use full sentences
        system_kw = shorten_for_query(l0_result.system_type, max_len=30)
        failure_kw = shorten_for_query(l0_result.failure_mode, max_len=40)

        if system_kw:
            self._bilingual_search(f"{system_kw} system dynamics {years}", "l0_system_type", anysearch_domain="general", tavily_max=3)
        if failure_kw:
            self._bilingual_search(f"{failure_kw} failure risk {years}", "l0_failure_mode", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Phase 3: After L1 ─────────────────────────────────────
    def collect_after_l1(self, industry: str, l1_result) -> None:
        years = _year_range()
        for var in l1_result.state_variables[:3]:
            kw = shorten_for_query(var, max_len=30)
            self._bilingual_search(f"{kw} capacity stock {years}", f"l1_sv_{var[:30]}", anysearch_domain="finance", tavily_max=3)
        for var in l1_result.control_variables[:3]:
            kw = shorten_for_query(var, max_len=30)
            self._bilingual_search(f"{kw} regulation policy {years}", f"l1_cv_{var[:30]}", anysearch_domain="general", tavily_max=3)
        for var in l1_result.latent_variables[:2]:
            kw = shorten_for_query(var, max_len=30)
            self._bilingual_search(f"{kw} sentiment expectations {years}", f"l1_lv_{var[:30]}", anysearch_domain="general", tavily_max=3)
        self._save_incremental()

    # ── Phase 4: After L2 (Drivers) ───────────────────────────
    def collect_after_l2(self, industry: str, l2_result) -> None:
        years = _year_range()
        for d in l2_result.drivers[:5]:
            kw = shorten_for_query(d.name, max_len=40)
            self._bilingual_search(f"{kw} driver impact {years}", f"l2_driver_{d.name[:30]}", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Phase 5: After L3 (Flow+Feedback) ─────────────────────
    def collect_after_l3(self, industry: str, l3_result) -> None:
        years = _year_range()
        flow_kw = " ".join(shorten_for_query(f, 20) for f in l3_result.flow_types[:3])
        self._bilingual_search(f"{flow_kw} flow dynamics {years}", "l3_flows", anysearch_domain="finance", tavily_max=3)
        for loop in l3_result.feedback_loops[:3]:
            kw = shorten_for_query(loop.loop_name, max_len=30)
            self._bilingual_search(f"{kw} feedback loop {years}", f"l3_loop_{loop.loop_name[:30]}", anysearch_domain="general", tavily_max=3)
        self._save_incremental()

    # ── Phase 6: After Nonlinear ──────────────────────────────
    def collect_after_nonlinear(self, industry: str, nl_result) -> None:
        years = _year_range()
        stage = nl_result.inventory_cycle.cycle_stage
        self._bilingual_search(f"inventory cycle {stage} capacity lag {years}", "nonlinear_cycle", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Phase 7: After L4 (Regime) ────────────────────────────
    def collect_after_l4(self, industry: str, l4_result) -> None:
        years = _year_range()
        self._bilingual_search(f"{l4_result.current_regime} regime indicators {years}", "l4_regime", anysearch_domain="finance", tavily_max=3)
        next_regime = l4_result.transition_probability.next_regime
        self._bilingual_search(f"{next_regime} regime transition probability {years}", "l4_transition", anysearch_domain="general", tavily_max=3)
        self._save_incremental()

    # ── Phase 8: After L5 (Distortion) ────────────────────────
    def collect_after_l5(self, industry: str, l5_result) -> None:
        years = _year_range()
        self._bilingual_search(f"market consensus analyst outlook {years}", "l5_consensus", anysearch_domain="general", tavily_max=3)
        for src in l5_result.mispricing_sources[:3]:
            kw = shorten_for_query(src, max_len=40)
            self._bilingual_search(f"{kw} mispricing {years}", "l5_mispricing", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Phase 9: After L6 (Alpha) ─────────────────────────────
    def collect_after_l6(self, industry: str, l6_result) -> None:
        years = _year_range()
        # Alpha signal is often very long — extract key phrase only
        kw = shorten_for_query(l6_result.alpha_signal, max_len=50)
        if kw:
            self._bilingual_search(f"{kw} alpha signal evidence {years}", "l6_alpha", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Competitor discovery ──────────────────────────────────
    def _discover_competitors(self, industry: str, region: Optional[str] = None) -> list[str]:
        region_str = f" in {region}" if region else ""
        # Use English name for competitor discovery (Tavily is English-leaning)
        en_name = self._industry_parts.get("en") or industry
        query = f"top companies {en_name}{region_str} market leaders {_year_range()}"
        try:
            response = self.tavily.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
        except Exception:
            return []
        competitors = []
        for result in response.get("results", []):
            title = result.get("title", "")
            if " - " in title:
                name = title.split(" - ")[0].strip()
                if name and len(name) < 50:
                    competitors.append(name)
        seen, unique = set(), []
        for c in competitors:
            if c.lower() not in seen:
                seen.add(c.lower())
                unique.append(c)
        return unique[:5]

    def _format_tavily_results(self, response: dict) -> str:
        lines = []
        if response.get("answer"):
            lines.append(f"## Summary\n{response['answer']}\n")
        for i, result in enumerate(response.get("results", []), 1):
            lines.append(f"### {i}. {result.get('title', 'Untitled')}\nURL: {result.get('url', '')}\n{result.get('content', '')}\n")
        return "\n".join(lines)

    def _export_raw(self) -> dict[str, str]:
        return {cat: "\n\n".join(entries) for cat, entries in self.context._categories.items()}

    def get_context_data(self, include_categories: Optional[list[str]] = None, exclude_categories: Optional[list[str]] = None) -> str:
        cats = include_categories
        if exclude_categories:
            cats = [c for c in self.context.get_all_categories() if c not in exclude_categories]
        return self.context.get_context_string(cats)

    @property
    def total_sources(self) -> int:
        return self.context.total_sources

    def save_to_directory(self, directory: str | Path) -> Path:
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        export = {
            "metadata": {"timestamp": datetime.now().isoformat(), "total_sources": self.context.total_sources,
                         "categories": list(self.context.get_all_categories()),
                         "queries_executed": sorted(self.context._queries),
                         "engines": {"tavily": True, "anysearch": self.anysearch is not None},
                         "bilingual": self._industry_parts},
            "categories": {cat: entries for cat, entries in self.context._categories.items()},
        }
        file_path = dir_path / "search_data.json"
        file_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
        return file_path
