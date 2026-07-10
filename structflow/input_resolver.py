"""Resolve raw scan input into a grounded entity and material-segment profile."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from structflow.evidence import EvidenceRecord, EvidenceStore
from structflow.llm_client import LLMClient
from structflow.models import ScanInput


class InputKind(str, Enum):
    INDUSTRY = "industry"
    COMPANY = "company"
    COMMODITY = "commodity"
    ASSET = "asset"
    POLICY_EVENT = "policy_event"
    UNKNOWN = "unknown"


class MaterialSegment(BaseModel):
    name: str
    revenue_share: Optional[float] = Field(default=None, ge=0, le=1)
    gross_profit_share: Optional[float] = Field(default=None, ge=0, le=1)
    materiality_reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class FinancialFact(BaseModel):
    metric: str
    period: str
    value: Optional[float] = None
    unit: str = ""
    yoy_change: Optional[float] = None
    evidence_ids: list[str] = Field(default_factory=list)
    reported_value: Optional[float] = None
    reported_unit: str = ""


class EvidenceGap(BaseModel):
    description: str
    query: str
    preferred_source_type: str = "company_filing"
    priority: float = Field(default=0.5, ge=0, le=1)


class MarketSnapshot(BaseModel):
    price: float = Field(gt=0)
    currency: str = "CNY"
    as_of: str
    source_id: str
    source_ids: list[str] = Field(default_factory=list)
    stale_days: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class EntityProfile(BaseModel):
    input_kind: InputKind
    canonical_name: str
    ticker: Optional[str] = None
    jurisdiction: Optional[str] = None
    reporting_currency: str = "CNY"
    latest_reporting_period: Optional[str] = None
    material_segments: list[MaterialSegment] = Field(default_factory=list)
    capital_projects: list[str] = Field(default_factory=list)
    required_system_dimensions: list[str] = Field(default_factory=list)
    latest_financial_facts: list[FinancialFact] = Field(default_factory=list)
    financial_quality_flags: list[str] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    market_snapshot: Optional[MarketSnapshot] = None


RESOLUTION_PROMPT = """
Resolve the raw input into a canonical research object before system modeling.

Raw input: {raw_input}
Region: {region}

The external evidence contains source IDs such as src_xxx. Use only those IDs.

Point-in-time and numeric rules:
- Obey the binding analysis cutoff supplied in context. Later observations are forbidden.
- Preserve source-reported monetary number/unit in reported_value/reported_unit.
- Normalize value to base currency: 1万元=10,000元; 1亿元=100,000,000元.
- Recompute numeric comparisons; never infer above/below from narrative wording.
- Unknown publication dates cannot support latest-period or current-price facts.

If the input is a company:
1. Resolve canonical company name, ticker, jurisdiction, and latest reporting period.
2. Build a MaterialSegmentMap from the latest annual filing.
3. Include every segment with at least 5% of revenue or gross profit.
4. Also include loss-making, debt-heavy, or capex-heavy segments even below 5%.
5. Extract the latest annual and quarterly facts when available:
   revenue, net profit, adjusted net profit, operating cash flow,
   investing cash flow, one-off gains, debt, and capex.
6. Record financial-quality warnings, especially differences between headline
   and adjusted profit or between profit and cash flow.
7. List the system dimensions L0 must cover. Include financing and material
   capital projects when they can change equity value.

If the input is an industry, commodity, asset, policy, or event, set input_kind
accordingly and do not invent a company profile.

Evidence gaps must be unresolved factual questions, not generic research topics.
Provide at most six focused search queries. Prefer company filings, regulators,
government statistics, and industry associations.

Do not infer a percentage when the filing does not provide it. Do not treat
broker target prices or community posts as facts. Output Chinese text fields.
"""


def run_input_resolution(
    client: LLMClient,
    scan_input: ScanInput,
    context_data: str,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> EntityProfile:
    prompt = RESOLUTION_PROMPT.format(
        raw_input=scan_input.industry,
        region=scan_input.region or "global",
    )
    if retry_feedback:
        prompt += (
            "\n\nPrevious resolution issues:\n"
            f"{retry_feedback}"
        )
    return client.structured_call(
        prompt,
        EntityProfile,
        context_data=context_data,
        temperature=temperature,
    )


def fallback_profile(
    scan_input: ScanInput, context_data: str = ""
) -> EntityProfile:
    company_markers = (
        "年度报告", "季度报告", "证券代码", "股份有限公司"
    )
    is_company = any(
        marker in context_data for marker in company_markers
    )
    ticker_match = re.search(
        r"(?:证券代码|股票代码|ticker)\s*[:：]?\s*(\d{6})",
        context_data,
        flags=re.IGNORECASE,
    )
    return EntityProfile(
        input_kind=(
            InputKind.COMPANY if is_company else InputKind.UNKNOWN
        ),
        canonical_name=scan_input.industry,
        ticker=ticker_match.group(1) if ticker_match else None,
        jurisdiction=scan_input.region,
        required_system_dimensions=["核心经营业务"],
        financial_quality_flags=[
            "Input resolution degraded: material segments require review"
        ],
    )


def profile_context(profile: EntityProfile) -> str:
    return (
        "## Canonical Input Profile (binding)\n"
        "This profile defines identity, material business boundaries, latest "
        "financial facts, and time-sensitive facts. Downstream layers must not "
        "narrow or contradict it without explicit evidence.\n"
        + profile.model_dump_json(indent=2)
    )


def save_profile(
    profile: EntityProfile, output_dir: str | Path | None
) -> Path | None:
    if not output_dir:
        return None
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "entity_profile.json"
    path.write_text(
        profile.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path


def _record_datetime(
    record: EvidenceRecord, now: datetime
) -> datetime | None:
    candidates = [
        record.published_at or "",
        record.title,
        record.content[:1200],
    ]
    patterns = [
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
    ]
    for text in candidates:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return datetime(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                        tzinfo=timezone.utc,
                    )
                except ValueError:
                    continue
    for text in candidates:
        match = re.search(
            r"(?<!\d)(\d{1,2})月(\d{1,2})日", text
        )
        if match:
            try:
                return datetime(
                    now.year,
                    int(match.group(1)),
                    int(match.group(2)),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                continue
    return None


def _record_price(record: EvidenceRecord) -> float | None:
    text = f"{record.title}\n{record.content[:2200]}"
    patterns = [
        r"(?:报|收于|当前价格为|当前股价为|股价为|股价约)"
        r"\s*[¥￥]?\s*(\d{1,5}(?:\.\d+)?)\s*(?:元/股|元|CNY)",
        r"[¥￥]\s*(\d{1,5}(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 0.01 <= value <= 100_000:
                return value
    return None


def resolve_market_snapshot(
    store: EvidenceStore,
    *,
    now: datetime | None = None,
) -> MarketSnapshot | None:
    """Resolve the newest explicitly dated observed market price."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    candidates: list[
        tuple[datetime, float, EvidenceRecord]
    ] = []
    for record in store.records():
        if not any(
            category.startswith((
                "market_data_",
                "contradiction_downside",
                "l7_asset_",
            ))
            for category in store.record_categories(record)
        ):
            continue
        observed_at = _record_datetime(record, current)
        price = _record_price(record)
        if observed_at is None or price is None:
            continue
        if observed_at > current:
            continue
        candidates.append((observed_at, price, record))
    if not candidates:
        return None
    observed_at, price, record = max(
        candidates,
        key=lambda item: (
            item[0],
            item[2].quality_score,
            item[2].relevance_score,
        ),
    )
    stale_days = max(0, (current - observed_at).days)
    return MarketSnapshot(
        price=price,
        currency="CNY",
        as_of=observed_at.date().isoformat(),
        source_id=record.source_id,
        stale_days=stale_days,
        confidence=min(
            0.95,
            record.quality_score * 0.6
            + record.relevance_score * 0.4,
        ),
    )
