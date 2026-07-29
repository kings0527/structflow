"""FRED macro anchors (Tier 1 official data, ``fredapi`` wrapper).

Skips gracefully with a degraded warning when the free API key is not
configured; the wrapper import happens lazily inside the fetcher.
"""

from __future__ import annotations

from datetime import date

from structflow.market_data.base import (
    ProviderResult,
    content_header,
    make_record,
    provider_failure,
)


# (series_id, Chinese label, unit) — macro anchors shared by all themes.
DEFAULT_SERIES: tuple[tuple[str, str, str], ...] = (
    ("DFII10", "美国10年期实际利率(TIPS)", "%"),
    ("DTWEXBGS", "美元指数(广义)", ""),
    ("DFF", "联邦基金有效利率", "%"),
)


def _series_latest(
    series_id: str, api_key: str, timeout: float
) -> tuple[date, float]:
    """Latest (observation_date, value) via fredapi, REST fallback."""
    try:
        from fredapi import Fred  # noqa: PLC0415 — optional dependency

        series = Fred(api_key=api_key).get_series(series_id)
        series = series.dropna()
        if series.empty:
            raise ValueError(f"FRED series {series_id} is empty")
        observed = series.index[-1]
        return (observed.date(), float(series.iloc[-1]))
    except ImportError:
        pass
    import requests

    response = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "10",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    for observation in response.json().get("observations", []):
        raw = observation.get("value", ".")
        if raw in (".", "", None):
            continue
        return (date.fromisoformat(observation["date"]), float(raw))
    raise ValueError(f"FRED series {series_id} has no numeric value")


def fetch_fred(
    subject: str,
    analysis_date: date,
    *,
    api_key: str = "",
    timeout: float = 20.0,
    series: tuple[tuple[str, str, str], ...] = DEFAULT_SERIES,
) -> ProviderResult:
    """One macro record per configured FRED series."""
    result = ProviderResult()
    if not api_key:
        result.failures.append(provider_failure(
            "fred", "api_key",
            "FRED_API_KEY 未配置，宏观锚数据跳过（免费申请后填入 .env）",
        ))
        result.degraded.append("fred: FRED_API_KEY 缺失，宏观锚数据跳过")
        return result
    for series_id, label, unit in series:
        try:
            observed_on, value = _series_latest(
                series_id, api_key, timeout
            )
            if observed_on > analysis_date:
                raise ValueError(
                    f"{series_id} observation {observed_on} is in the "
                    "future relative to the analysis date"
                )
            lag_days = max(0, (analysis_date - observed_on).days)
            lines = [
                content_header(f"{label}（{series_id}）", observed_on, lag_days),
                f"{series_id} 读数 {value:.4g}{unit}",
                f"来源：FRED 官方 API；数据观测日 {observed_on.isoformat()}",
                f"宏观锚背景：{subject}",
            ]
            result.records.append(make_record(
                category="market_data_macro",
                provider="market_data_fred",
                query=f"FRED {series_id}",
                title=f"{label} {observed_on.isoformat()}",
                url=f"https://fred.stlouisfed.org/series/{series_id}",
                content="\n".join(lines),
                published_at=observed_on.isoformat(),
                source_type="market_data_official",
                upstream_origin="api.stlouisfed.org",
            ))
        except Exception as error:
            result.failures.append(
                provider_failure("fred", series_id, error)
            )
            result.degraded.append(
                f"fred: 序列 {series_id} 不可用（{type(error).__name__}）"
            )
    return result
