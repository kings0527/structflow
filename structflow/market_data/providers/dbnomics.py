"""DBnomics global macro anchors (Tier 2 official-data aggregation).

DBnomics (db.nomics.world) republishes official series from central
banks and statistical agencies (ECB, Eurostat, BIS, IMF, ...) behind a
free, keyless REST API — no client package and no API key required.
The upstream origin of every record is the issuing agency, relayed via
api.db.nomics.world; hence ``market_data_official`` (0.92), not Tier 1.

Endpoint verified live (2026-07):
``GET https://api.db.nomics.world/v22/series/{PROVIDER}/{DATASET}/{SERIES}
?observations=1&format=json&metadata=false`` returns
``{"series": {"docs": [{"period": [...], "period_start_day": [...],
"value": [...], "series_name": ..., "@frequency": ...}]}}`` with
``period_start_day`` in ISO dates and ``value`` possibly containing
``"NA"`` placeholders.
"""

from __future__ import annotations

from datetime import date

from structflow.market_data.base import (
    ProviderResult,
    content_header,
    make_record,
    provider_failure,
)


API_BASE = "https://api.db.nomics.world/v22/series"

# (series_id, Chinese label, unit, issuing agency) — global macro
# anchors complementing the US-centric FRED set. All verified live.
DEFAULT_SERIES: tuple[tuple[str, str, str, str], ...] = (
    (
        "ECB/FM/D.U2.EUR.4F.KR.MRR_FR.LEV",
        "欧央行主要再融资利率", "%", "ECB",
    ),
    (
        "Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA20",
        "欧元区HICP同比", "%", "Eurostat",
    ),
    ("BIS/WS_CBPOL/M.US", "美国央行政策利率(BIS口径)", "%", "BIS"),
    ("BIS/WS_CBPOL/M.CN", "中国央行政策利率(BIS口径)", "%", "BIS"),
)


def is_series_id(code: str | None) -> bool:
    """A DBnomics series ID is ``PROVIDER/DATASET/SERIES`` — instrument
    codes like ``GLD`` or ``ETH/USDT`` never carry two slashes."""
    return bool(code) and code.count("/") >= 2


def _series_doc(series_id: str, timeout: float) -> dict:
    """Raw series document from the keyless DBnomics REST API."""
    import requests

    response = requests.get(
        f"{API_BASE}/{series_id}",
        params={
            "observations": "1",
            "format": "json",
            "metadata": "false",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    docs = response.json().get("series", {}).get("docs", [])
    if not docs:
        raise ValueError(f"DBnomics series {series_id} not found")
    return docs[0]


def _latest_observation(
    doc: dict, analysis_date: date
) -> tuple[date, float]:
    """Latest numeric (observed_on, value) at or before the cutoff.

    ``period_start_day`` holds ISO dates for every frequency (monthly
    ``period`` entries are ``YYYY-MM``); values may be ``"NA"`` or null
    for unpublished periods. Observations after the analysis date are
    dropped, never served (no look-ahead leakage on backdated runs).
    """
    days = doc.get("period_start_day") or doc.get("period") or []
    values = doc.get("value") or []
    for raw_day, raw_value in zip(reversed(days), reversed(values)):
        if raw_value in ("NA", "", None):
            continue
        observed_on = date.fromisoformat(str(raw_day))
        if observed_on > analysis_date:
            continue
        return (observed_on, float(raw_value))
    raise ValueError(
        "no numeric observation at or before "
        f"{analysis_date.isoformat()}"
    )


def fetch_dbnomics(
    subject: str,
    analysis_date: date,
    *,
    code: str | None = None,
    timeout: float = 20.0,
    series: tuple[tuple[str, str, str, str], ...] = DEFAULT_SERIES,
) -> ProviderResult:
    """One macro record per DBnomics series; keyless, fail-closed.

    ``code`` may carry a custom ``PROVIDER/DATASET/SERIES`` ID, which
    is fetched in addition to the default anchors; instrument codes
    (``GLD``, ``ETH/USDT``) are ignored here — they belong to the
    price providers.
    """
    result = ProviderResult()
    wanted = list(series)
    if is_series_id(code):
        agency = code.split("/", 1)[0]
        wanted.append((code, code, "", agency))
    for series_id, label, unit, agency in wanted:
        try:
            doc = _series_doc(series_id, timeout)
            observed_on, value = _latest_observation(doc, analysis_date)
            lag_days = max(0, (analysis_date - observed_on).days)
            display = label if label != series_id else (
                doc.get("series_name") or series_id
            )
            lines = [
                content_header(
                    f"{display}（{series_id}）", observed_on, lag_days
                ),
                f"{display} 读数 {value:.4g}{unit}",
                (
                    f"来源：{agency} 官方序列，经 DBnomics 免认证 REST API"
                    f" 获取；数据观测日 {observed_on.isoformat()}"
                ),
                f"宏观锚背景：{subject}",
            ]
            result.records.append(make_record(
                category="market_data_macro",
                provider="market_data_dbnomics",
                query=f"DBnomics {series_id}",
                title=f"{display} {observed_on.isoformat()}",
                url=f"https://db.nomics.world/{series_id}",
                content="\n".join(lines),
                published_at=observed_on.isoformat(),
                source_type="market_data_official",
                upstream_origin=f"{agency} via api.db.nomics.world",
            ))
        except Exception as error:
            result.failures.append(
                provider_failure("dbnomics", series_id, error)
            )
            result.degraded.append(
                f"dbnomics: 序列 {series_id} 不可用"
                f"（{type(error).__name__}）"
            )
    return result
