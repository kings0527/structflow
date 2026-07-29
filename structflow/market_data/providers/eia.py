"""EIA weekly US energy inventories (Tier 1 direct government API).

The US Energy Information Administration v2 REST API
(``api.eia.gov/v2``) is a direct regulator/government statistics pull,
so records carry ``exchange_official`` (0.93) — same tier as the CFTC
Socrata endpoint. A free API key is required
(https://www.eia.gov/opendata/register.php); without one the provider
degrades and skips, it never raises (verified live: a keyless call
returns HTTP 403 with ``{"error": {"code": "API_KEY_MISSING", ...}}``).

Data shape: ``{"response": {"data": [{"period": "YYYY-MM-DD",
"value": ..., ...}]}}`` sorted descending by period when requested.
Weekly stocks are published with a several-day lag, so every record
carries the lag annotation and WoW / one-year-percentile derivations
for trend and crowding context.
"""

from __future__ import annotations

from datetime import date

from structflow.market_data.base import (
    ProviderResult,
    content_header,
    make_record,
    provider_failure,
)


API_BASE = "https://api.eia.gov/v2"

# Roughly one year of weekly observations plus headroom for the
# percentile window after future-dated rows are dropped.
FETCH_LENGTH = 60
PERCENTILE_WINDOW = 52

# (route, series facet, Chinese label, unit) — headline weekly stocks.
DEFAULT_SERIES: tuple[tuple[str, str, str, str], ...] = (
    (
        "petroleum/stoc/wstk", "WCESTUS1",
        "美国商业原油库存(EIA周度)", "千桶",
    ),
    (
        "natural-gas/stor/wkly", "NW2_EPG0_SWO_R48_BCF",
        "美国Lower48天然气工作库存(EIA周度)", "十亿立方英尺",
    ),
)

EIA_LAG_NOTE = "周度统计，公布滞后数天，仅反映报告周截止日库存"


def _series_rows(
    route: str, series_id: str, api_key: str, timeout: float
) -> list[dict]:
    """Descending weekly rows for one series from the EIA v2 API."""
    import requests

    response = requests.get(
        f"{API_BASE}/{route}/data/",
        params={
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": series_id,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": str(FETCH_LENGTH),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "response" not in payload:
        error = payload.get("error", {})
        raise ValueError(
            f"EIA API error: {error.get('code', 'unknown')} "
            f"{error.get('message', '')}".strip()
        )
    return payload["response"].get("data", [])


def _observations(
    rows: list[dict], analysis_date: date
) -> list[tuple[date, float]]:
    """Descending (observed_on, value) pairs at or before the cutoff.

    Future-dated report weeks are dropped, never served (no look-ahead
    leakage on backdated runs); non-numeric values are skipped.
    """
    observations: list[tuple[date, float]] = []
    for row in rows:
        raw_value = row.get("value")
        if raw_value in (None, "", "NA"):
            continue
        observed_on = date.fromisoformat(str(row["period"]))
        if observed_on > analysis_date:
            continue
        observations.append((observed_on, float(raw_value)))
    observations.sort(key=lambda pair: pair[0], reverse=True)
    return observations


def _percentile_rank(latest: float, window: list[float]) -> float:
    """Share of the trailing window at or below the latest reading."""
    at_or_below = sum(1 for value in window if value <= latest)
    return 100.0 * at_or_below / len(window)


def fetch_eia(
    subject: str,
    analysis_date: date,
    *,
    api_key: str = "",
    timeout: float = 20.0,
    series: tuple[tuple[str, str, str, str], ...] = DEFAULT_SERIES,
) -> ProviderResult:
    """One inventory record per series with WoW and percentile context."""
    result = ProviderResult()
    if not api_key:
        result.failures.append(provider_failure(
            "eia", "api_key",
            "EIA_API_KEY 未配置，能源库存数据跳过（免费申请后填入 .env）",
        ))
        result.degraded.append("eia: EIA_API_KEY 缺失，能源库存数据跳过")
        return result
    for route, series_id, label, unit in series:
        try:
            rows = _series_rows(route, series_id, api_key, timeout)
            observations = _observations(rows, analysis_date)
            if not observations:
                raise ValueError(
                    f"{series_id} has no observation at or before "
                    f"{analysis_date.isoformat()}"
                )
            observed_on, latest = observations[0]
            lag_days = max(0, (analysis_date - observed_on).days)
            lines = [
                content_header(
                    f"{label}（{series_id}）", observed_on, lag_days
                ),
                f"库存读数 {latest:,.0f}{unit}",
            ]
            if len(observations) >= 2:
                _, prior = observations[1]
                delta = latest - prior
                ratio = delta / prior if prior else 0.0
                lines.append(
                    f"环比上周 {delta:+,.0f}{unit}（{ratio:+.2%}）"
                )
            window = [value for _, value in
                      observations[:PERCENTILE_WINDOW]]
            if len(window) >= 8:
                lines.append(
                    f"近一年百分位 {_percentile_rank(latest, window):.0f}%"
                    f"（样本 {len(window)} 周）"
                )
            lines.append(
                f"来源：EIA 官方 v2 API；报告周截止日 "
                f"{observed_on.isoformat()}；{EIA_LAG_NOTE}"
            )
            lines.append(f"能源库存背景：{subject}")
            result.records.append(make_record(
                category="market_data_inventory",
                provider="market_data_eia",
                query=f"EIA {series_id}",
                title=f"{label} {observed_on.isoformat()}",
                url=f"https://www.eia.gov/opendata/browser/{route}",
                content="\n".join(lines),
                published_at=observed_on.isoformat(),
                source_type="exchange_official",
                upstream_origin="api.eia.gov",
            ))
        except Exception as error:
            result.failures.append(
                provider_failure("eia", series_id, error)
            )
            result.degraded.append(
                f"eia: 序列 {series_id} 不可用（{type(error).__name__}）"
            )
    return result
