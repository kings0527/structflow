"""CFTC Commitments of Traders futures positioning (Tier 1).

Primary path hits the official ``publicreporting.cftc.gov`` Socrata API
directly (source_type ``exchange_official``); the ``cot_reports``
wrapper is a lazy-imported fallback (``market_data_official``).
"""

from __future__ import annotations

import os
import tempfile
import threading
from datetime import date, datetime
from urllib.parse import quote

from structflow.market_data.base import (
    ProviderResult,
    content_header,
    make_record,
    provider_failure,
)


COT_API_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# COT reports are published Friday for the preceding Tuesday.
COT_KNOWN_LAG_NOTE = "基于周二持仓数据，公布滞后3个交易日"

# os.chdir is process-wide, so the scratch-directory section below is
# serialized to keep concurrent relative-path IO in other threads safe.
_CHDIR_LOCK = threading.Lock()


def _rows_via_api(
    keyword: str, limit: int, timeout: float
) -> list[dict]:
    """Fetch legacy futures rows from the official Socrata endpoint."""
    import requests

    response = requests.get(
        COT_API_URL,
        params={
            "$q": keyword,
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(limit),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected CFTC API payload shape")
    return rows


def _rows_via_cot_reports(keyword: str, limit: int) -> list[dict]:
    """Fallback through the ``cot_reports`` wrapper (lazy import).

    ``cot_reports.cot_year`` downloads and unpacks report files
    (annual.txt etc.) into the current working directory, so the call
    is confined to a throwaway directory with the CWD restored even on
    exceptions. 进程级 CWD 切换，已用锁串行化；信号强杀场景 CWD 可能
    残留于已删除目录。
    """
    import cot_reports  # noqa: PLC0415 — optional dependency

    original_cwd = os.getcwd()
    with _CHDIR_LOCK, tempfile.TemporaryDirectory(
        prefix="structflow_cot_"
    ) as scratch:
        try:
            os.chdir(scratch)
            frame = cot_reports.cot_year(
                year=date.today().year, cot_report_type="legacy_fut"
            )
        finally:
            os.chdir(original_cwd)
    lowered = keyword.lower()
    frame = frame[
        frame["Market and Exchange Names"]
        .str.lower()
        .str.contains(lowered, regex=False)
    ]
    rows: list[dict] = []
    for _, row in frame.iterrows():
        rows.append({
            "market_and_exchange_names": row["Market and Exchange Names"],
            "report_date_as_yyyy_mm_dd": str(
                row["As of Date in Form YYYY-MM-DD"]
            ),
            "noncomm_positions_long_all": row[
                "Noncommercial Positions-Long (All)"
            ],
            "noncomm_positions_short_all": row[
                "Noncommercial Positions-Short (All)"
            ],
            "comm_positions_long_all": row[
                "Commercial Positions-Long (All)"
            ],
            "comm_positions_short_all": row[
                "Commercial Positions-Short (All)"
            ],
        })
    rows.sort(
        key=lambda item: item["report_date_as_yyyy_mm_dd"], reverse=True
    )
    return rows[:limit]


def _fetch_rows(
    keyword: str, limit: int, timeout: float
) -> tuple[list[dict], str]:
    """Rows plus the source_type of the path that produced them."""
    try:
        return _rows_via_api(keyword, limit, timeout), "exchange_official"
    except Exception:
        return _rows_via_cot_reports(keyword, limit), "market_data_official"


def _parse_report_date(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def _net_series(rows: list[dict]) -> list[tuple[date, int, int]]:
    """(report_date, noncommercial net, commercial net), oldest first."""
    series: list[tuple[date, int, int]] = []
    for row in rows:
        try:
            series.append((
                _parse_report_date(row["report_date_as_yyyy_mm_dd"]),
                int(float(row["noncomm_positions_long_all"]))
                - int(float(row["noncomm_positions_short_all"])),
                int(float(row["comm_positions_long_all"]))
                - int(float(row["comm_positions_short_all"])),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    series.sort(key=lambda item: item[0])
    return series


def _percentile(values: list[int], latest: int) -> float:
    if not values:
        return 0.0
    below = sum(1 for value in values if value <= latest)
    return 100.0 * below / len(values)


def _streak(nets: list[int]) -> tuple[str, int]:
    """Consecutive weeks of net-position increases or decreases."""
    if len(nets) < 2:
        return ("持平", 0)
    deltas = [
        nets[index] - nets[index - 1]
        for index in range(1, len(nets))
    ]
    last = deltas[-1]
    if last == 0:
        return ("持平", 0)
    direction = "增" if last > 0 else "减"
    streak = 0
    for delta in reversed(deltas):
        if (delta > 0) == (last > 0) and delta != 0:
            streak += 1
        else:
            break
    return (direction, streak)


def fetch_cot(
    subject: str,
    code: str | None,
    analysis_date: date,
    *,
    lookback_days: int = 365,
    timeout: float = 20.0,
) -> ProviderResult:
    """One positioning record from the latest COT report for a market."""
    result = ProviderResult()
    keyword = (code or subject).strip()
    limit = max(8, lookback_days // 7 + 4)
    try:
        rows, source_type = _fetch_rows(keyword, limit, timeout)
        series = _net_series(rows)
        series = [
            item for item in series if item[0] <= analysis_date
        ]
        if not series:
            raise ValueError(
                f"No CFTC COT rows matched keyword {keyword!r}"
            )
        observed_on, noncomm_net, comm_net = series[-1]
        nets = [item[1] for item in series]
        change = nets[-1] - nets[-2] if len(nets) >= 2 else 0
        direction, streak = _streak(nets)
        lag_days = max(0, (analysis_date - observed_on).days)
        market_name = str(
            rows[0].get("market_and_exchange_names", keyword)
        )
        lines = [
            content_header(
                f"{subject} CFTC COT持仓（{market_name}）",
                observed_on,
                lag_days,
            ),
            f"非商业净持仓 {noncomm_net:+,} 手（周变动 {change:+,} 手）",
            f"商业净持仓 {comm_net:+,} 手",
            (
                f"净持仓近一年百分位 {_percentile(nets, nets[-1]):.0f}%"
                f"（样本 {len(nets)} 周）"
            ),
            f"连续{direction}仓 {streak} 周",
            f"{COT_KNOWN_LAG_NOTE}；数据观测日 {observed_on.isoformat()}",
        ]
        result.records.append(make_record(
            category="market_data_positioning",
            provider="market_data_cftc_cot",
            query=f"CFTC COT {keyword}",
            title=f"{subject} CFTC COT 持仓报告 {observed_on.isoformat()}",
            url=(
                f"{COT_API_URL}?market={quote(keyword)}"
                f"&report_date={observed_on.isoformat()}"
            ),
            content="\n".join(lines),
            published_at=observed_on.isoformat(),
            source_type=source_type,
            upstream_origin="publicreporting.cftc.gov",
        ))
    except Exception as error:
        result.failures.append(
            provider_failure("cot", "cftc_cot_positioning", error)
        )
        result.degraded.append(
            f"cot: CFTC COT 持仓不可用（{type(error).__name__}），"
            "回落搜索文本路径"
        )
    return result
