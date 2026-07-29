"""SEC 13F institutional holdings via edgartools (Tier 2 wrapper).

13F filings are due 45 days after quarter end, so the data is
research-grade structure only: every record carries the mandatory lag
disclaimer and must never back a current-tense holdings claim. The
overview is built from a bounded sample of recent 13F-HR filings — a
full-market EDGAR scan is neither feasible nor needed here.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from structflow.market_data.base import (
    ProviderResult,
    content_header,
    make_record,
    provider_failure,
)


EDGAR_LAG_NOTE = "滞后 45 天，仅供结构研究，不代表当前持仓"

# Most recent 13F-HR filings scanned per pull; annotated in the record
# so the sample scope is never mistaken for a census.
SAMPLE_FILINGS = 80


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def _position_shares(table, code: str) -> float:
    """Shares of ``code`` reported in one 13F infotable (0 if none)."""
    upper = code.upper()
    shares = 0.0
    for _, row in table.iterrows():
        ticker = str(row.get("Ticker") or "").upper()
        issuer = str(row.get("Issuer") or "").upper()
        if ticker != upper and upper not in issuer:
            continue
        shares += float(row.get("SharesPrnAmount") or 0)
    return shares


def _holdings_overview(
    code: str, identity: str, timeout: float
) -> list[dict]:
    """Per-quarter holdings aggregates for ``code``, newest first.

    Each snapshot is ``{"period": date, "holders": {manager: shares},
    "total_shares": float}`` summed over the sampled filings of that
    report period. Filings that fail to parse are skipped silently —
    the sample annotation covers partial coverage.
    """
    from edgar import get_filings, set_identity  # noqa: PLC0415 — optional

    set_identity(identity)
    filings = get_filings(form="13F-HR").latest(SAMPLE_FILINGS)
    periods: dict[date, dict] = {}
    for filing in filings:
        try:
            period = _as_date(filing.period_of_report)
            shares = _position_shares(filing.obj().infotable, code)
        except Exception:
            continue
        if shares <= 0:
            continue
        bucket = periods.setdefault(period, {
            "period": period, "holders": {}, "total_shares": 0.0,
        })
        manager = str(getattr(filing, "company", "") or "unknown manager")
        bucket["holders"][manager] = (
            bucket["holders"].get(manager, 0.0) + shares
        )
        bucket["total_shares"] += shares
    return [periods[key] for key in sorted(periods, reverse=True)]


def fetch_edgar(
    subject: str,
    code: str | None,
    analysis_date: date,
    *,
    timeout: float = 20.0,
    lookback_days: int = 365,
) -> ProviderResult:
    """One institutional-holdings overview record from SEC 13F data."""
    result = ProviderResult()
    if not code:
        result.failures.append(provider_failure(
            "edgar", "code",
            "--code is required for 13F institutional data",
        ))
        return result
    identity = os.environ.get("EDGAR_IDENTITY", "").strip()
    if not identity:
        result.failures.append(provider_failure(
            "edgar", "identity",
            "EDGAR_IDENTITY is not set (SEC requires a contact "
            "identity for EDGAR access)",
        ))
        result.degraded.append(
            "edgar: 缺少 EDGAR_IDENTITY，13F 机构持仓跳过"
        )
        return result
    try:
        snapshots = [
            snapshot
            for snapshot in _holdings_overview(code, identity, timeout)
            if snapshot["period"] <= analysis_date
        ]
        if not snapshots:
            raise ValueError(
                f"No 13F holdings matched {code!r} in the sampled "
                "filings up to the analysis date"
            )
        latest = snapshots[0]
        previous = snapshots[1] if len(snapshots) > 1 else None
        period: date = latest["period"]
        lag_days = max(0, (analysis_date - period).days)
        holders: dict[str, float] = latest["holders"]
        top = sorted(
            holders.items(), key=lambda kv: kv[1], reverse=True
        )[:5]
        concentration = (
            sum(shares for _, shares in top) / latest["total_shares"]
            if latest["total_shares"]
            else 0.0
        )
        lines = [
            content_header(
                f"{subject}（{code}）SEC 13F机构持仓", period, lag_days
            ),
            (
                f"报告期 {period.isoformat()}：样本内机构 {len(holders)} 家，"
                f"合计持仓 {latest['total_shares']:,.0f} 股"
            ),
        ]
        if previous:
            delta = latest["total_shares"] - previous["total_shares"]
            pct = (
                delta / previous["total_shares"]
                if previous["total_shares"]
                else 0.0
            )
            both = set(holders) & set(previous["holders"])
            increases = sum(
                1 for name in both
                if holders[name] > previous["holders"][name]
            )
            decreases = sum(
                1 for name in both
                if holders[name] < previous["holders"][name]
            )
            direction = (
                "增持" if delta > 0 else "减持" if delta < 0 else "持平"
            )
            lines.append(
                f"较上季度（{previous['period'].isoformat()}）主要机构方向为"
                f"{direction}：持仓变动 {delta:+,.0f} 股（{pct:+.2%}），"
                f"增持 {increases} 家 / 减持 {decreases} 家"
            )
        else:
            lines.append("上一季度样本不可得，环比方向缺省")
        lines.append(
            f"前五大机构占样本持仓 {concentration:.0%}："
            + "、".join(name for name, _ in top)
        )
        lines.append(
            f"样本口径：最近 {SAMPLE_FILINGS} 份 13F-HR 申报，非全市场"
        )
        lines.append(EDGAR_LAG_NOTE)
        result.records.append(make_record(
            category="market_data_institutional",
            provider="market_data_sec_13f",
            query=f"SEC 13F holdings {code}",
            title=(
                f"{subject}（{code}）SEC 13F 机构持仓 {period.isoformat()}"
            ),
            url=(
                "https://www.sec.gov/edgar/search/#/q="
                f"{code}&forms=13F-HR&dateRange=custom"
                f"&startdt={period.isoformat()}&enddt={period.isoformat()}"
            ),
            content="\n".join(lines),
            published_at=period.isoformat(),
            source_type="market_data_official",
            upstream_origin="sec.gov EDGAR (edgartools)",
        ))
    except Exception as error:
        result.failures.append(
            provider_failure("edgar", "sec_13f_holdings", error)
        )
        result.degraded.append(
            f"edgar: SEC 13F 机构持仓不可用（{type(error).__name__}），"
            "回落搜索文本路径"
        )
    return result
