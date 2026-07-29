"""Global equity/ETF prices via yfinance + Stooq (Tier 3, dual-source).

Aggregator prices may enter the consensus path only after
``cross_validate_price`` passes; a deviation beyond tolerance or a
single surviving source yields zero price records (fail-closed).
Both upstreams submit short daily series and are compared on their
latest common trading day (``align_latest_common``): the newest bars
can legitimately differ by one session (intraday vs settled close),
which must not read as a price deviation. No common day → no record.
Stooq is fetched through its public CSV endpoint directly:
pandas-datareader removed its stooq source (NotImplementedError).
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from structflow.market_data.base import (
    ProviderResult,
    PriceObservation,
    align_latest_common,
    build_price_records,
    content_header,
    cross_validate_price,
    latest_same_day_conflict,
    make_record,
    provider_failure,
)


ETF_FLOW_NOTE = "聚合级数据，未经发行商核对，仅供份额趋势参考"


def _yfinance_series(
    code: str, timeout: float, lookback_days: int, as_of: date
) -> list[PriceObservation]:
    """Recent daily closes from Yahoo Finance via yfinance.

    Observations after ``as_of`` are dropped at the provider seam so a
    backdated analysis never sees look-ahead bars (same local contract
    as the cn provider).
    """
    import yfinance  # noqa: PLC0415 — optional dependency

    ticker = yfinance.Ticker(code)
    history = ticker.history(period="10d", timeout=timeout)
    if history is None or history.empty:
        raise ValueError(f"yfinance returned no rows for {code!r}")
    currency = "USD"
    try:
        currency = str(ticker.fast_info["currency"] or "USD").upper()
    except Exception:
        pass
    observations: list[PriceObservation] = []
    for stamp, row in history.iterrows():
        close = row.get("Close")
        if close is None or close != close:  # NaN guard
            continue
        if stamp.date() > as_of:
            continue
        observations.append(PriceObservation(
            source="yfinance",
            url=f"https://finance.yahoo.com/quote/{code}",
            price=float(close),
            observed_on=stamp.date(),
            currency=currency,
            volume=float(row.get("Volume") or 0) or None,
            upstream_origin="finance.yahoo.com",
        ))
    if not observations:
        raise ValueError(f"yfinance returned no closes for {code!r}")
    return observations


def _stooq_series(
    code: str, timeout: float, as_of: date
) -> list[PriceObservation]:
    """Recent daily closes from Stooq's public CSV history endpoint.

    Observations after ``as_of`` are dropped (provider-local
    look-ahead guard).

    pandas-datareader dropped its stooq source (``DataReader(...,
    "stooq")`` raises ``NotImplementedError`` since 0.11), so the CSV
    endpoint is the primary and only Stooq path. US listings usually
    need a ``.us`` suffix, so a bare symbol is retried with it.
    """
    import requests

    symbol = code.lower()
    candidates = [symbol]
    if "." not in symbol and "=" not in symbol:
        candidates.append(f"{symbol}.us")
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            response = requests.get(
                "https://stooq.com/q/d/l/",
                params={"s": candidate, "i": "d"},
                timeout=timeout,
            )
            response.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(response.text)))
            observations: list[PriceObservation] = []
            for row in rows[-15:]:
                close = row.get("Close")
                if close in (None, "", "N/D"):
                    continue
                observed_on = datetime.fromisoformat(
                    row["Date"]
                ).date()
                if observed_on > as_of:
                    continue
                observations.append(PriceObservation(
                    source="stooq",
                    url=f"https://stooq.com/q/?s={candidate}",
                    price=float(close),
                    observed_on=observed_on,
                    volume=float(row.get("Volume") or 0) or None,
                    upstream_origin="stooq.com",
                ))
            if not observations:
                raise ValueError(
                    f"Stooq CSV has no usable closes for {candidate!r}"
                )
            return observations
        except Exception as error:
            last_error = error
    raise last_error if last_error else ValueError(
        f"Stooq returned no usable close for {code!r}"
    )


def _shares_outstanding(
    code: str, timeout: float, lookback_days: int
) -> tuple[date, float, float | None]:
    """(observed_on, latest shares, shares ~30 days earlier or None)."""
    import pandas  # noqa: PLC0415 — optional dependency (via yfinance)
    import yfinance  # noqa: PLC0415 — optional dependency

    ticker = yfinance.Ticker(code)
    shares = ticker.get_shares_full(
        start=None, end=None
    )
    if shares is None or shares.empty:
        raise ValueError(f"No shares outstanding history for {code!r}")
    shares = shares.dropna().sort_index()
    latest_on = shares.index[-1].date()
    latest = float(shares.iloc[-1])
    earlier = None
    cutoff = shares.index[-1] - pandas.Timedelta(days=30)
    older = shares[shares.index <= cutoff]
    if not older.empty:
        earlier = float(older.iloc[-1])
    return (latest_on, latest, earlier)


def fetch_equities(
    subject: str,
    code: str | None,
    analysis_date: date,
    *,
    tolerance: float = 0.005,
    timeout: float = 20.0,
    lookback_days: int = 365,
    types: set[str] | None = None,
) -> ProviderResult:
    """Dual-source price plus optional ETF share-count records."""
    result = ProviderResult()
    if not code:
        result.failures.append(provider_failure(
            "equities", "code", "--code is required for equity data"
        ))
        return result
    wanted = types or {"price", "flow"}
    entity_label = f"{subject}（{code}）"

    if "price" in wanted:
        series: list[list[PriceObservation]] = []
        for name, fetch in (
            ("yfinance", lambda: _yfinance_series(
                code, timeout, lookback_days, analysis_date
            )),
            ("stooq", lambda: _stooq_series(
                code, timeout, analysis_date
            )),
        ):
            try:
                series.append(fetch())
            except Exception as error:
                result.failures.append(
                    provider_failure("equities", f"{name}_close", error)
                )
        if len(series) == 2:
            conflict = latest_same_day_conflict(
                series[0], series[1], tolerance
            )
            if conflict is not None:
                # Same latest trading day but diverging prices: a real
                # disagreement, never softened by an earlier common day.
                result.cross_validation_failed.append(conflict)
                result.degraded.append(
                    f"equities: {code} 最新交易日双源价差超限"
                    f"（{conflict['reason']}），价格记录未入库（fail-closed）"
                )
            elif (
                aligned := align_latest_common(series[0], series[1])
            ) is None:
                result.degraded.append(
                    f"equities: {code} 双源日线序列无公共交易日，"
                    "无法对齐校验，价格记录未入库（fail-closed）"
                )
            else:
                check = cross_validate_price(
                    aligned[0], aligned[1], tolerance
                )
                if check["passed"]:
                    result.cross_validation_passed.append(check)
                    result.records.extend(build_price_records(
                        entity_label=entity_label,
                        query=f"{code} close price",
                        observations=(aligned[0], aligned[1]),
                        source_type="market_data_aggregated",
                        check=check,
                        note="聚合器双源（yfinance/Stooq），已交叉校验",
                    ))
                else:
                    result.cross_validation_failed.append(check)
                    result.degraded.append(
                        f"equities: {code} 双源价格校验失败"
                        f"（{check['reason']}），价格记录未入库（fail-closed）"
                    )
        else:
            result.degraded.append(
                f"equities: {code} 仅 {len(series)} 个聚合器源可用，"
                "不足双源校验，价格记录未入库（fail-closed）"
            )

    if "flow" in wanted:
        try:
            observed_on, latest, earlier = _shares_outstanding(
                code, timeout, lookback_days
            )
            if observed_on > analysis_date:
                raise ValueError(
                    "shares observation is in the future relative to "
                    "the analysis date"
                )
            lag_days = max(0, (analysis_date - observed_on).days)
            lines = [
                content_header(
                    f"{entity_label} ETF份额", observed_on, lag_days
                ),
                f"最新流通份额 {latest:,.0f}",
            ]
            if earlier:
                delta = latest - earlier
                lines.append(
                    f"较约30天前变动 {delta:+,.0f}"
                    f"（{delta / earlier:+.2%}）"
                )
            lines.append(ETF_FLOW_NOTE)
            result.records.append(make_record(
                category="market_data_etf_flow",
                provider="market_data_yfinance",
                query=f"{code} shares outstanding",
                title=f"{entity_label} 份额变动 {observed_on.isoformat()}",
                url=(
                    f"https://finance.yahoo.com/quote/{code}"
                    "/key-statistics"
                ),
                content="\n".join(lines),
                published_at=observed_on.isoformat(),
                source_type="market_data_aggregated",
                upstream_origin="finance.yahoo.com",
            ))
        except Exception as error:
            result.failures.append(
                provider_failure("equities", "etf_shares", error)
            )
    return result
