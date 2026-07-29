"""Shared primitives for the structured market data channel.

Accuracy-first contract enforced here:
- every record is an ``EvidenceImportItem``-compatible dict with an
  observation-date header and explicit lag annotation;
- price content must satisfy the consensus quote grammar
  (``QUOTE_PATTERNS``), non-price content must never match it;
- aggregator prices only exist after dual-source cross validation
  (fail-closed: reject on deviation or a single source).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from structflow.evidence import source_weight
from structflow.market_snapshot import QUOTE_PATTERNS


PRICE_CATEGORY = "market_data_price"

MARKET_DATA_SOURCE_TYPES = {
    "exchange_official",
    "market_data_official",
    "market_data_aggregated",
}


class MarketDataContentError(ValueError):
    """Generated content violates the quote-grammar contract."""


@dataclass(frozen=True)
class PriceObservation:
    """One raw close/last-price observation from a single upstream."""

    source: str
    url: str
    price: float
    observed_on: date
    currency: str = "USD"
    volume: float | None = None
    upstream_origin: str | None = None


@dataclass
class ProviderResult:
    """Aggregated outcome of one or more provider fetches."""

    records: list[dict] = field(default_factory=list)
    cross_validation_passed: list[dict] = field(default_factory=list)
    cross_validation_failed: list[dict] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    def merge(self, other: "ProviderResult") -> None:
        self.records.extend(other.records)
        self.cross_validation_passed.extend(other.cross_validation_passed)
        self.cross_validation_failed.extend(other.cross_validation_failed)
        self.degraded.extend(other.degraded)
        self.failures.extend(other.failures)


def provider_failure(
    provider: str, item: str, error: Exception | str
) -> dict:
    """Structured, non-throwing failure reason for one data item."""
    if isinstance(error, Exception):
        return {
            "provider": provider,
            "item": item,
            "error_type": type(error).__name__,
            "message": str(error),
        }
    return {
        "provider": provider,
        "item": item,
        "error_type": "ProviderError",
        "message": str(error),
    }


def matches_quote_pattern(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in QUOTE_PATTERNS)


def content_header(
    entity_label: str, observed_on: date, lag_days: int | None = None
) -> str:
    """Mandatory first line: entity, observation date, known lag."""
    header = (
        f"{entity_label} "
        f"{observed_on.year}年{observed_on.month:02d}月{observed_on.day:02d}日"
    )
    if lag_days is not None and lag_days > 0:
        header += f" [数据滞后{lag_days}天]"
    return header


def price_statement(price: float, currency: str = "USD") -> str:
    """Quote line guaranteed to match ``QUOTE_PATTERNS``."""
    rendered = f"{price:.2f}" if price >= 1 else f"{price:.6f}"
    if currency.upper() in ("CNY", "RMB"):
        return f"收盘价{rendered}元"
    return f"last price {rendered} {currency.upper()}"


def make_record(
    *,
    category: str,
    provider: str,
    query: str,
    title: str,
    url: str,
    content: str,
    published_at: str,
    source_type: str,
    upstream_origin: str | None = None,
    quality_score: float | None = None,
) -> dict:
    """Build one ``EvidenceImportItem``-compatible dict.

    Enforces the content contract: price records must match the
    consensus quote grammar; every other category must not, so lagged
    or aggregated data can never pollute the price consensus.
    """
    if source_type not in MARKET_DATA_SOURCE_TYPES:
        raise MarketDataContentError(
            f"Unknown market data source_type: {source_type}"
        )
    is_price = category == PRICE_CATEGORY
    if is_price and not matches_quote_pattern(content):
        raise MarketDataContentError(
            "Price record content does not match QUOTE_PATTERNS: "
            f"{content[:120]!r}"
        )
    # The consensus extractor scans title and content together, so the
    # combined text must stay pattern-free for every non-price record.
    if not is_price and matches_quote_pattern(f"{title}\n{content}"):
        raise MarketDataContentError(
            "Non-price record title/content must not match "
            f"QUOTE_PATTERNS: {title!r} / {content[:120]!r}"
        )
    return {
        "category": category,
        "provider": provider,
        "query": query,
        "title": title,
        "url": url,
        "content": content,
        "published_at": published_at,
        "source_type": source_type,
        "upstream_origin": upstream_origin,
        "quality_score": (
            quality_score
            if quality_score is not None
            else source_weight(source_type)
        ),
    }


def cross_validate_price(
    a: PriceObservation,
    b: PriceObservation,
    tolerance: float = 0.005,
) -> dict:
    """Dual-source price check; returns both raw values on failure.

    Deviation is measured against the mean of both observations, and
    observation dates must be within 3 days of each other (the same
    window the consensus algorithm uses).
    """
    mean = (a.price + b.price) / 2
    deviation = abs(a.price - b.price) / max(mean, 1e-9)
    date_gap = abs((a.observed_on - b.observed_on).days)
    passed = deviation <= tolerance and date_gap <= 3
    reason = None
    if deviation > tolerance:
        reason = (
            f"price deviation {deviation:.4%} exceeds "
            f"tolerance {tolerance:.4%}"
        )
    elif date_gap > 3:
        reason = f"observation dates differ by {date_gap} days (> 3)"
    return {
        "passed": passed,
        "deviation": round(deviation, 6),
        "tolerance": tolerance,
        "reason": reason,
        "observations": [
            {
                "source": obs.source,
                "price": obs.price,
                "observed_on": obs.observed_on.isoformat(),
                "url": obs.url,
            }
            for obs in (a, b)
        ],
    }


def latest_same_day_conflict(
    a: list[PriceObservation],
    b: list[PriceObservation],
    tolerance: float,
) -> dict | None:
    """Failed check when both freshest bars share a day yet diverge.

    A same-day divergence on the newest observation is a genuine
    price-disagreement alarm, not a freshness artifact; falling back
    to an earlier common day via ``align_latest_common`` would swallow
    it. Callers must fail closed with the returned check. ``None``
    means the guard does not apply (different latest days, or the
    latest bars agree).
    """
    latest_a = max(a, key=lambda obs: obs.observed_on)
    latest_b = max(b, key=lambda obs: obs.observed_on)
    if latest_a.observed_on != latest_b.observed_on:
        return None
    check = cross_validate_price(latest_a, latest_b, tolerance)
    if check["passed"]:
        return None
    return check


def align_latest_common(
    a: list[PriceObservation],
    b: list[PriceObservation],
) -> tuple[PriceObservation, PriceObservation] | None:
    """Latest observation pair sharing one trading day, or ``None``.

    Upstreams disagree on the most recent bar (one serves an intraday
    or T close while the other still ends at T-1), which would fail
    cross validation on a price gap that is really a date gap. Both
    sides therefore submit a short daily series and are compared on
    their most recent common trading day.
    """
    by_date_a = {obs.observed_on: obs for obs in a}
    by_date_b = {obs.observed_on: obs for obs in b}
    common = set(by_date_a) & set(by_date_b)
    if not common:
        return None
    day = max(common)
    return (by_date_a[day], by_date_b[day])


def build_price_records(
    *,
    entity_label: str,
    query: str,
    observations: tuple[PriceObservation, PriceObservation],
    source_type: str,
    check: dict,
    note: str = "",
) -> list[dict]:
    """Two independent price records from a passed cross validation.

    One record per upstream keeps ≥2 source_id and ≥2 domain diversity
    so the consensus snapshot algorithm can accept the cluster.
    """
    if not check.get("passed"):
        raise MarketDataContentError(
            "build_price_records requires a passed cross validation"
        )
    records: list[dict] = []
    for obs in observations:
        lines = [
            content_header(entity_label, obs.observed_on),
            price_statement(obs.price, obs.currency),
        ]
        if obs.volume is not None:
            lines.append(f"成交量 {obs.volume:,.0f}")
        lines.append(
            f"双源交叉校验通过（偏差 {check['deviation']:.4%}，"
            f"对照源：{'、'.join(o.source for o in observations)}）"
        )
        if note:
            lines.append(note)
        records.append(make_record(
            category=PRICE_CATEGORY,
            provider=f"market_data_{obs.source}",
            query=query,
            # Keep quote keywords out of the title: the consensus
            # extractor scans title+content and a keyword next to the
            # header date would inject a bogus price.
            title=f"{entity_label} {obs.source} 行情快照",
            url=obs.url,
            content="\n".join(lines),
            published_at=obs.observed_on.isoformat(),
            source_type=source_type,
            upstream_origin=obs.upstream_origin or obs.source,
        ))
    return records
