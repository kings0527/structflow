"""Consensus market quote extraction from independent, dated evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from statistics import median
from urllib.parse import urlparse

from structflow.evidence import EvidenceRecord
from structflow.input_resolver import EntityProfile, MarketSnapshot
from structflow.research_clock import coerce_date, dates_in_text, normalize_analysis_date


QUOTE_PATTERNS = (
    re.compile(
        r"(?:收盘(?:价)?|最新价|现价|当前股价|股价)"
        r"[^\d]{0,40}(?:约\s*)?[¥￥]?\s*(\d+(?:\.\d+)?)\s*元?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:close|closing price|last price|share price)"
        r"[^\d]{0,30}(?:cny|rmb|[¥￥])?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
)

AI_REPORT_SIGNALS = (
    "ai-powered",
    "llm model",
    "multi-agent stock analysis",
    "trade decision",
    "tokens:",
)


@dataclass(frozen=True)
class QuoteCandidate:
    price: float
    observed_on: date
    source_id: str
    domain: str
    quality: float


def _entity_matches(text: str, profile: EntityProfile) -> bool:
    normalized = text.lower()
    ticker_digits = re.sub(r"\D", "", profile.ticker or "")
    name = (profile.canonical_name or "").lower()
    short_name = name.removesuffix("股份有限公司").removesuffix("有限公司")
    return bool(
        (ticker_digits and ticker_digits in normalized)
        or (short_name and short_name in normalized)
    )


def _candidate(
    record: EvidenceRecord,
    profile: EntityProfile,
    as_of: date,
    max_age_days: int,
) -> QuoteCandidate | None:
    title = str(getattr(record, "title", "") or "")
    content = str(getattr(record, "content", "") or "")
    text = f"{title}\n{content}"
    lowered = text.lower()
    source_type = str(getattr(record, "source_type", "") or "").lower()
    if source_type in {"social", "search_bundle", "ai_generated"}:
        return None
    if any(signal in lowered for signal in AI_REPORT_SIGNALS):
        return None
    if not _entity_matches(text, profile):
        return None

    prices: list[float] = []
    for pattern in QUOTE_PATTERNS:
        prices.extend(float(match.group(1)) for match in pattern.finditer(text))
    prices = [price for price in prices if 0.01 <= price <= 1_000_000]
    if not prices:
        return None

    observed_on = coerce_date(getattr(record, "published_at", None))
    text_dates = dates_in_text(text, as_of)
    if text_dates:
        observed_on = max(text_dates)
    if observed_on is None or observed_on > as_of:
        return None
    if (as_of - observed_on).days > max_age_days:
        return None

    domain = urlparse(str(getattr(record, "url", "") or "")).netloc.lower()
    source_id = str(getattr(record, "source_id", "") or "")
    if not source_id:
        return None
    quality = float(getattr(record, "quality_score", 0.5) or 0.5)
    return QuoteCandidate(
        price=prices[0],
        observed_on=observed_on,
        source_id=source_id,
        domain=domain or source_id,
        quality=quality,
    )


def resolve_consensus_market_snapshot(
    records: list[EvidenceRecord],
    profile: EntityProfile,
    as_of: str | date | None = None,
    *,
    max_age_days: int = 7,
    tolerance: float = 0.03,
) -> MarketSnapshot | None:
    cutoff = normalize_analysis_date(as_of)
    candidates = [
        candidate
        for record in records
        if (
            candidate := _candidate(
                record, profile, cutoff, max_age_days
            )
        )
        is not None
    ]
    if len(candidates) < 2:
        return None

    clusters: list[list[QuoteCandidate]] = []
    for seed in candidates:
        cluster = [
            item
            for item in candidates
            if abs(item.price - seed.price) / max(seed.price, 0.01) <= tolerance
            and abs((item.observed_on - seed.observed_on).days) <= 3
        ]
        if (
            len({item.source_id for item in cluster}) >= 2
            and len({item.domain for item in cluster}) >= 2
        ):
            clusters.append(cluster)
    if not clusters:
        return None

    best = max(
        clusters,
        key=lambda cluster: (
            max(item.observed_on for item in cluster),
            len({item.domain for item in cluster}),
            len({item.source_id for item in cluster}),
            sum(item.quality for item in cluster),
        ),
    )
    unique = {item.source_id: item for item in best}
    selected = list(unique.values())
    observed_on = max(item.observed_on for item in selected)
    price = float(median(item.price for item in selected))
    source_ids = sorted(unique)
    confidence = min(
        0.99,
        0.55
        + 0.1 * min(len(source_ids), 3)
        + 0.15 * min(len({item.domain for item in selected}), 2),
    )
    return MarketSnapshot(
        price=round(price, 4),
        currency=profile.reporting_currency or "CNY",
        as_of=observed_on.isoformat(),
        source_id=source_ids[0],
        source_ids=source_ids,
        stale_days=(cutoff - observed_on).days,
        confidence=confidence,
    )
