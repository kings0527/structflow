"""Structured market data channel (accuracy-first, fail-closed).

Routes an asset class to provider combinations and merges their
records, cross-validation results, degraded warnings, and failures.
Providers never raise: missing dependencies, network errors, and
failed validations all surface as structured reasons.
"""

from __future__ import annotations

from datetime import date

from structflow.market_data.base import (
    PRICE_CATEGORY,
    MarketDataContentError,
    PriceObservation,
    ProviderResult,
    build_price_records,
    content_header,
    cross_validate_price,
    make_record,
    matches_quote_pattern,
    price_statement,
    provider_failure,
)


ASSET_CLASSES = ("equity", "commodity", "crypto", "cn_stock", "cn_sector")

DATA_TYPES = (
    "price", "positioning", "macro", "funding", "flow", "institutional",
    "inventory",
)


def collect_market_data(
    *,
    subject: str,
    asset_class: str,
    code: str | None = None,
    types: set[str] | None = None,
    analysis_date: date,
    tolerance: float = 0.005,
    timeout: float = 20.0,
    lookback_days: int = 365,
    fred_api_key: str = "",
    eia_api_key: str = "",
    enable_dbnomics: bool = True,
) -> ProviderResult:
    """Fetch every provider mapped to ``asset_class`` and merge results."""
    from structflow.market_data.providers import (
        cn, cot, crypto, dbnomics, edgar, eia, equities, fred,
    )

    result = ProviderResult()
    if asset_class not in ASSET_CLASSES:
        result.failures.append(provider_failure(
            "router", "asset_class",
            f"Unknown asset class: {asset_class!r}",
        ))
        return result

    wanted = set(types) if types else set(DATA_TYPES)
    calls = []
    if asset_class == "commodity" and "positioning" in wanted:
        calls.append(lambda: cot.fetch_cot(
            subject, code, analysis_date,
            lookback_days=lookback_days, timeout=timeout,
        ))
    if asset_class in ("equity", "commodity") and (
        wanted & {"price", "flow"}
    ):
        calls.append(lambda: equities.fetch_equities(
            subject, code, analysis_date,
            tolerance=tolerance, timeout=timeout,
            lookback_days=lookback_days, types=wanted,
        ))
    if asset_class == "crypto" and (
        wanted & {"price", "positioning", "funding"}
    ):
        calls.append(lambda: crypto.fetch_crypto(
            subject, code, analysis_date,
            tolerance=tolerance, timeout=timeout, types=wanted,
        ))
    if asset_class in ("equity", "commodity") and "institutional" in wanted:
        calls.append(lambda: edgar.fetch_edgar(
            subject, code, analysis_date,
            timeout=timeout, lookback_days=lookback_days,
        ))
    if asset_class in ("cn_stock", "cn_sector") and (
        wanted & {"price", "positioning", "flow", "institutional"}
    ):
        calls.append(lambda: cn.fetch_cn(
            subject, code, analysis_date,
            asset_class=asset_class,
            tolerance=tolerance, timeout=timeout,
            lookback_days=lookback_days, types=wanted,
        ))
    if asset_class == "commodity" and "inventory" in wanted:
        calls.append(lambda: eia.fetch_eia(
            subject, analysis_date,
            api_key=eia_api_key, timeout=timeout,
        ))
    if "macro" in wanted:
        # FRED and DBnomics run independently: one degrading never
        # blocks the other's macro anchors. DBnomics is keyless and
        # always dials out, so offline setups can switch it off via
        # MARKET_DATA_ENABLE_DBNOMICS without touching FRED.
        calls.append(lambda: fred.fetch_fred(
            subject, analysis_date,
            api_key=fred_api_key, timeout=timeout,
        ))
        if enable_dbnomics:
            calls.append(lambda: dbnomics.fetch_dbnomics(
                subject, analysis_date, code=code, timeout=timeout,
            ))

    for call in calls:
        try:
            result.merge(call())
        except Exception as error:
            # Providers are already fail-closed; this is a last-resort
            # guard so one provider bug never aborts the pipeline.
            result.failures.append(
                provider_failure("router", "provider_call", error)
            )
    return result


__all__ = [
    "ASSET_CLASSES",
    "DATA_TYPES",
    "PRICE_CATEGORY",
    "MarketDataContentError",
    "PriceObservation",
    "ProviderResult",
    "build_price_records",
    "collect_market_data",
    "content_header",
    "cross_validate_price",
    "make_record",
    "matches_quote_pattern",
    "price_statement",
    "provider_failure",
]
