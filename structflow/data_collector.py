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
from structflow.system_templates import (
    SystemTemplate,
    get_template_search_keywords,
    get_template_search_context,
    match_template,
)


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

# Common Chinese finance/analysis terms → English for Tavily queries
_ZH_QUERY_EN_MAP: dict[str, str] = {
    "代币化": "tokenization",
    "现实世界资产": "real world assets RWA",
    "质押": "staking",
    "锁仓": "locked value",
    "监管": "regulation",
    "监管强度": "regulatory intensity",
    "监管框架": "regulatory framework",
    "风险偏好": "risk appetite",
    "市场情绪": "market sentiment",
    "通缩": "deflationary",
    "通胀": "inflationary",
    "机构": "institutional",
    "净流入": "net inflows",
    "价格": "price",
    "收益率": "yield",
    "流动性": "liquidity",
    "共识": "consensus",
    "错配": "mispricing",
    "估值": "valuation",
    "做多": "long",
    "做空": "short",
    "竞争": "competition",
    "市场份额": "market share",
    "价值流失": "value loss",
    "价值捕获": "value capture",
    "升级": "upgrade",
    "扩容": "scaling",
    "手续费": "transaction fees",
    "手续费燃烧": "fee burn",
    "稳定币": "stablecoin",
    "验证者": "validators",
    "活跃地址": "active addresses",
    "交易量": "transaction volume",
    "区块": "block",
    "性能": "performance",
    "吞吐量": "throughput",
    "供应链": "supply chain",
    "产能": "capacity",
    "库存": "inventory",
    "需求": "demand",
    "利率": "interest rate",
    "关税": "tariff",
    "碳税": "carbon tax",
    "补贴": "subsidy",
    "景气": "business cycle",
    "周期": "cycle",
    "反馈": "feedback",
    "系统性风险": "systemic risk",
    "信用风险": "credit risk",
    "流动性风险": "liquidity risk",
    "地缘政治": "geopolitical",
    "宏观": "macro",
    "做空机构": "short seller",
    "信心": "confidence",
    "叙事": "narrative",
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
    for delim in ['；', ';', '，', ',', '。', '.', '：', ':', '→', ' ']:
        if delim in cleaned:
            cleaned = cleaned.split(delim)[0].strip()
            break
    # Truncate to max_len
    if len(cleaned) > max_len:
        truncated = cleaned[:max_len]
        if ' ' in truncated:
            truncated = truncated.rsplit(' ', 1)[0]
        cleaned = truncated
    return cleaned


def zh_to_en_query(text: str) -> str:
    """Translate Chinese terms in a query to English for Tavily (English search engine).

    Replaces known Chinese finance/analysis terms with their English equivalents.
    Leaves English words and unknown Chinese terms unchanged.
    """
    if not text:
        return ""
    result = text
    # Sort by length (longest first) to avoid partial replacements
    for zh_term, en_term in sorted(_ZH_QUERY_EN_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        result = result.replace(zh_term, f" {en_term} ")
    # Clean up extra spaces
    result = re.sub(r'\s+', ' ', result).strip()
    # Remove any remaining Chinese characters that weren't translated
    # (they won't help Tavily search anyway)
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', result))
    if has_chinese:
        # Keep only the English parts
        en_parts = re.findall(r'[a-zA-Z0-9\s]+', result)
        result = ' '.join(p.strip() for p in en_parts if p.strip())
    return result


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

        # System template — set after L0 via set_template()
        self._template: SystemTemplate | None = None

    def set_template(self, system_type: str) -> SystemTemplate | None:
        """Match and cache a system template based on L0's system_type.

        Called by agent.py after L0 completes.
        Template provides pre-defined search keywords (zh+en) for each variable type,
        replacing the need to use raw LLM output text as search queries.
        """
        self._template = match_template(system_type)
        return self._template

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
        # Translate Chinese terms in query suffix to English for Tavily
        en_suffix = zh_to_en_query(query_suffix)
        tavily_query = f"{en_name} {en_suffix}" if is_bilingual else f"{raw_name} {en_suffix}"
        # If translation removed everything (all Chinese, no mapping), fall back to raw
        if not tavily_query.strip() or len(tavily_query.strip()) < 3:
            tavily_query = f"{raw_name} {query_suffix}"
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
        "l0": ["industry_overview", "market_structure", "policy_context", "risk_landscape", "revenue_model", "ma_activity", "precision_"],
        "l1": ["industry_overview", "market_structure", "policy_context", "l0_", "precision_"],
        "l2": ["l1_", "policy_context", "industry_overview", "precision_"],
        "l3": ["l2_", "l1_", "market_structure", "precision_supply_chain"],
        "nonlinear": ["l3_", "l2_", "l1_", "risk_landscape", "precision_capacity"],
        "l4": ["l3_", "l4_", "nonlinear_", "risk_landscape", "industry_overview", "contradiction_", "market_data_"],
        "l5": ["l5_", "revenue_model", "industry_overview", "contradiction_", "precision_", "market_data_"],
        "l6": ["l6_", "l5_", "risk_landscape", "contradiction_", "precision_", "market_data_"],
        "l7": ["company_", "l4_", "l5_", "ma_activity", "contradiction_", "market_data_"],
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

        # ── Round 0: Market Data (CRITICAL — must be first) ──
        # Fetch current price, recent chart, key levels BEFORE any analysis
        # Without this, LLM generates price targets and risk scenarios disconnected from reality
        self._bilingual_search(f"current price today {years}", "market_data_price", anysearch_domain="finance", tavily_max=5)
        self._bilingual_search(f"price chart technical analysis support resistance {years}", "market_data_technical", anysearch_domain="finance", tavily_max=3)
        self._bilingual_search(f"price trend recent performance YTD {years}", "market_data_trend", anysearch_domain="general", tavily_max=3)

        # ── Round 1: Exploration (broad) ──
        self._bilingual_search(f"industry overview market share {region_str} {years}", "industry_overview", anysearch_domain="general")
        self._bilingual_search(f"market structure concentration barriers {region_str} {years}", "market_structure", anysearch_domain="business")
        self._bilingual_search(f"policy regulation government {region_str} {years}", "policy_context", anysearch_domain="general")
        self._bilingual_search(f"systemic risk financial risk {region_str} {years}", "risk_landscape", anysearch_domain="finance")
        self._bilingual_search(f"revenue model pricing value chain {region_str} {years}", "revenue_model", anysearch_domain="business")
        self._bilingual_search(f"merger acquisition consolidation {region_str} {years}", "ma_activity", anysearch_domain="business")

        # ── Round 2: Precision (financials, supply chain, pricing) ──
        self._bilingual_search(f"pricing mechanism spot futures margin {region_str} {years}", "precision_pricing", anysearch_domain="finance", tavily_max=3)
        self._bilingual_search(f"supply chain bottleneck suppliers {region_str} {years}", "precision_supply_chain", anysearch_domain="business", tavily_max=3)
        self._bilingual_search(f"capacity utilization inventory level {region_str} {years}", "precision_capacity", anysearch_domain="finance", tavily_max=3)

        # ── Round 3: Contradiction (bearish, crisis, short) ──
        self._bilingual_search(f"crisis shortage oversupply {region_str} {years}", "contradiction_crisis", anysearch_domain="finance", tavily_max=3)
        self._bilingual_search(f"bear case short thesis risks {region_str} {years}", "contradiction_bearish", anysearch_domain="general", tavily_max=3)
        self._bilingual_search(f"price crash bubble burst downside {region_str} {years}", "contradiction_downside", anysearch_domain="finance", tavily_max=3)

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
        # Use template search context if available, otherwise shorten LLM output
        l0_context = get_template_search_context(self._template, "l0") if self._template else []
        if l0_context:
            for ctx in l0_context[:2]:
                self._bilingual_search(f"{ctx} {years}", "l0_system_type", anysearch_domain="general", tavily_max=3)
        else:
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
        # Use template keywords if available (prevents search drift)
        # Template provides clean English/Chinese keywords per variable type
        if self._template:
            var_configs = [
                ("SV", "capacity stock", "finance"),
                ("CV", "regulation policy", "general"),
                ("LV", "sentiment expectations", "general"),
            ]
            for var_type, suffix, domain in var_configs:
                en_kws = get_template_search_keywords(self._template, var_type, "en")
                for kw in en_kws[:3]:
                    self._bilingual_search(f"{kw} {suffix} {years}", f"l1_{var_type.lower()}_{kw}",
                                           anysearch_domain=domain, tavily_max=3)
        else:
            # Fallback: use LLM output (may produce noisier queries)
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

    # ── Phase 8b: Contradiction Search (防确认偏差) ──────────
    def collect_contradiction(self, industry: str, l5_result) -> None:
        """搜索反证 — 看空观点/崩溃场景/做空报告.

        search_spec.md Round 3: Contradiction
        防止确认偏差 (confirmation bias):
        - 搜索支持 market_belief 的证据 (可能证明市场是对的)
        - 搜索反驳 structural_truth 的证据 (可能证明结构分析是错的)
        - 搜索做空报告和看空论点
        """
        years = _year_range()
        # Search for evidence SUPPORTING market belief (counter-argument to our distortion)
        belief_kw = shorten_for_query(l5_result.market_belief, max_len=50)
        if belief_kw:
            en_belief = zh_to_en_query(belief_kw)
            self._bilingual_search(f"{en_belief} evidence supporting {years}", "contradiction_support_belief", anysearch_domain="general", tavily_max=3)
        # Search for evidence AGAINST structural truth (challenge our analysis)
        truth_kw = shorten_for_query(l5_result.structural_truth, max_len=50)
        if truth_kw:
            en_truth = zh_to_en_query(truth_kw)
            self._bilingual_search(f"{en_truth} criticism rebuttal {years}", "contradiction_challenge_truth", anysearch_domain="finance", tavily_max=3)
        # Search for bearish/short views
        self._bilingual_search(f"bearish short thesis risks downside {years}", "contradiction_bearish_views", anysearch_domain="finance", tavily_max=3)
        self._bilingual_search(f"bubble overvalued crash scenario {years}", "contradiction_crash", anysearch_domain="general", tavily_max=3)
        self._save_incremental()

    # ── Phase 9: After L6 (Alpha) ─────────────────────────────
    def collect_after_l6(self, industry: str, l6_result) -> None:
        years = _year_range()
        kw = shorten_for_query(l6_result.alpha_signal, max_len=50)
        if kw:
            self._bilingual_search(f"{kw} alpha signal evidence {years}", "l6_alpha", anysearch_domain="finance", tavily_max=3)
        self._save_incremental()

    # ── Phase 10: After L7 (Investment Mapping) ───────────────
    def collect_after_l7(self, industry: str, l7_result) -> None:
        """搜索L7生成的具体资产 — 验证价格、基本面和风险。

        Qwen批评: L7后搜索管线终止，生成的资产未经验证。
        修复: 对每个资产搜索当前价格、基本面和风险。
        """
        years = _year_range()
        all_assets = []
        for category_name in ["best_positioned", "overvalued", "fragile"]:
            assets = getattr(l7_result, category_name, [])
            for a in assets:
                all_assets.append((a.asset, category_name))

        for asset, category in all_assets[:8]:  # Limit to 8 assets
            # Search current price and fundamentals
            en_asset = zh_to_en_query(asset)
            self._bilingual_search(f"{en_asset} current price market cap {years}",
                                   f"l7_asset_{asset[:30]}", anysearch_domain="finance", tavily_max=3)
            self._bilingual_search(f"{en_asset} business model risks bear case {years}",
                                   f"l7_risk_{asset[:30]}", anysearch_domain="general", tavily_max=2)
        self._save_incremental()

    # ── Competitor discovery ──────────────────────────────────
    def _discover_competitors(self, industry: str, region: Optional[str] = None) -> list[str]:
        """Discover key players through search — filter out article titles."""
        region_str = f" in {region}" if region else ""
        en_name = self._industry_parts.get("en") or industry
        query = f"top companies {en_name}{region_str} market leaders key players {_year_range()}"
        try:
            response = self.tavily.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
        except Exception:
            return []

        # Article title patterns to reject
        article_patterns = [
            r'\?',           # Questions ("Which companies own ETH?")
            r':',            # Subtitles ("Ethereum: A Complete Guide")
            r'^Top \d+',     # Listicles ("Top 10 Cryptocurrencies")
            r'^Best ',       # Recommendations ("Best Ethereum Wallets")
            r'^How ',        # How-to articles
            r'^What ',       # Explainers
            r'^Why ',        # Opinion pieces
            r'^\d+ ',       # Numbered listicles
            r'20\d\d',      # Year-focused articles
            r'price predict', # Price prediction articles
            r'forecast',     # Forecast articles
        ]
        article_re = re.compile('|'.join(article_patterns), re.IGNORECASE)

        competitors = []
        for result in response.get("results", []):
            title = result.get("title", "")
            # Skip article titles
            if article_re.search(title):
                continue
            # Try extracting company name from title
            name = title.strip()
            # If title has " - ", take the first part
            if " - " in title:
                name = title.split(" - ")[0].strip()
            # If title has " | ", take the first part
            if " | " in name:
                name = name.split(" | ")[0].strip()
            # Validate: not too long, not an article pattern
            if name and 2 <= len(name) <= 40 and not article_re.search(name):
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
