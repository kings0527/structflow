"""A-share auxiliary data via AkShare (Tier 3, aggregator-only).

Regional supplement, never a Tier 1 substitute: prices require
EastMoney + Sina dual-upstream cross validation (fail-closed) on the
latest common trading day of both daily series (the newest bars can
legitimately differ by one session — intraday vs settled close), and
every non-price record is ``market_data_aggregated`` with the
mandatory aggregator disclaimer plus inline derived metrics
(net-inflow totals, consecutive-day streaks, balance deltas).
Observation-date filtering uses the effective analysis date passed
in by the caller (including a backdated ``--date``).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from structflow.market_data.base import (
    PriceObservation,
    ProviderResult,
    align_latest_common,
    build_price_records,
    content_header,
    cross_validate_price,
    latest_same_day_conflict,
    make_record,
    provider_failure,
)


CN_AGGREGATOR_NOTE = "聚合器数据，准确性未经官方源核对"

FLOW_WINDOW_DAYS = 20
MARGIN_WINDOW_DAYS = 20
BLOCK_WINDOW_DAYS = 30
LHB_WINDOW_DAYS = 30
SECTOR_FLOW_WINDOWS = ("5日", "20日")


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def _market_prefix(symbol: str) -> str:
    """sh/sz/bj prefix inferred from the six-digit code."""
    if symbol.startswith(("6", "9", "5")):
        return "sh"
    if symbol.startswith(("4", "8")):
        return "bj"
    return "sz"


def _compact(value: float) -> str:
    """Render a CNY amount in 万/亿 units without price keywords."""
    if abs(value) >= 1e8:
        return f"{value / 1e8:,.2f}亿元"
    return f"{value / 1e4:,.0f}万元"


def _streak_days(values: list[float]) -> tuple[str, int]:
    """Consecutive trailing days of net inflow or outflow."""
    if not values:
        return ("持平", 0)
    last = values[-1]
    if last == 0:
        return ("持平", 0)
    direction = "净流入" if last > 0 else "净流出"
    streak = 0
    for value in reversed(values):
        if (value > 0) == (last > 0) and value != 0:
            streak += 1
        else:
            break
    return (direction, streak)


# --- upstream fetchers (all lazy-import akshare) ---------------------------

def _em_stock_series(
    symbol: str, analysis_date: date, timeout: float
) -> list[PriceObservation]:
    """Recent daily closes for one A-share from the EastMoney upstream."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=(analysis_date - timedelta(days=30)).strftime("%Y%m%d"),
        end_date=analysis_date.strftime("%Y%m%d"),
        adjust="",
    )
    if frame is None or frame.empty:
        raise ValueError(f"EastMoney returned no rows for {symbol!r}")
    prefix = _market_prefix(symbol)
    observations: list[PriceObservation] = []
    for _, row in frame.iterrows():
        observations.append(PriceObservation(
            source="eastmoney",
            url=f"https://quote.eastmoney.com/{prefix}{symbol}.html",
            price=float(row["收盘"]),
            observed_on=_as_date(row["日期"]),
            currency="CNY",
            volume=float(row.get("成交量") or 0) or None,
            upstream_origin="quote.eastmoney.com",
        ))
    return observations


def _sina_stock_series(
    symbol: str, analysis_date: date, timeout: float
) -> list[PriceObservation]:
    """Recent daily closes for one A-share from the Sina upstream."""
    import akshare  # noqa: PLC0415 — optional dependency

    prefix = _market_prefix(symbol)
    frame = akshare.stock_zh_a_daily(
        symbol=f"{prefix}{symbol}",
        start_date=(analysis_date - timedelta(days=30)).strftime("%Y%m%d"),
        end_date=analysis_date.strftime("%Y%m%d"),
    )
    if frame is None or frame.empty:
        raise ValueError(f"Sina returned no rows for {symbol!r}")
    observations: list[PriceObservation] = []
    for stamp, row in frame.iterrows():
        observed = (
            _as_date(row["date"]) if "date" in frame.columns
            else _as_date(stamp)
        )
        observations.append(PriceObservation(
            source="sina",
            url=(
                "https://finance.sina.com.cn/realstock/company/"
                f"{prefix}{symbol}/nc.shtml"
            ),
            price=float(row["close"]),
            observed_on=observed,
            currency="CNY",
            volume=float(row.get("volume") or 0) or None,
            upstream_origin="finance.sina.com.cn",
        ))
    return observations


def _fund_flow_series(
    symbol: str, analysis_date: date, window: int
) -> list[dict]:
    """Last ``window`` observed days of main/extra-large net inflow."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_individual_fund_flow(
        stock=symbol, market=_market_prefix(symbol)
    )
    rows: list[dict] = []
    for _, row in frame.iterrows():
        observed = _as_date(row["日期"])
        if observed > analysis_date:
            continue
        rows.append({
            "date": observed,
            "main_net": float(row["主力净流入-净额"]),
            "xl_net": float(row["超大单净流入-净额"]),
        })
    rows.sort(key=lambda item: item["date"])
    return rows[-window:]


def _margin_series(
    symbol: str, analysis_date: date, window: int
) -> list[dict]:
    """Per-day margin balances via the exchange detail endpoints.

    AkShare exposes no per-stock margin history call, so this walks
    recent calendar days through ``stock_margin_detail_{sse,szse,bse}``
    and filters the code; non-trading days are skipped silently.
    """
    import akshare  # noqa: PLC0415 — optional dependency

    prefix = _market_prefix(symbol)
    detail = {
        "sh": akshare.stock_margin_detail_sse,
        "sz": akshare.stock_margin_detail_szse,
        "bj": akshare.stock_margin_detail_bse,
    }[prefix]
    rows: list[dict] = []
    day = analysis_date
    scanned = 0
    while len(rows) < window and scanned < int(window * 1.6) + 4:
        scanned += 1
        try:
            frame = detail(date=day.strftime("%Y%m%d"))
        except Exception:
            frame = None
        day -= timedelta(days=1)
        if frame is None or frame.empty:
            continue
        code_column = (
            "标的证券代码" if "标的证券代码" in frame.columns else "证券代码"
        )
        match = frame[frame[code_column].astype(str) == symbol]
        if match.empty:
            continue
        row = match.iloc[0]
        balance = float(
            row.get("融资融券余额") or row.get("融资余额") or 0
        )
        if balance <= 0:
            continue
        rows.append({
            "date": day + timedelta(days=1),
            "balance": balance,
        })
    rows.sort(key=lambda item: item["date"])
    return rows


def _block_trades(
    symbol: str, analysis_date: date, window: int
) -> list[dict]:
    """Block trades for one code within the trailing window."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_dzjy_mrmx(
        symbol="A股",
        start_date=(
            analysis_date - timedelta(days=window)
        ).strftime("%Y%m%d"),
        end_date=analysis_date.strftime("%Y%m%d"),
    )
    rows: list[dict] = []
    for _, row in frame.iterrows():
        if str(row.get("证券代码") or "") != symbol:
            continue
        observed = _as_date(row["交易日期"])
        if observed > analysis_date:
            continue
        rows.append({
            "date": observed,
            "amount": float(row.get("成交额") or 0),
        })
    rows.sort(key=lambda item: item["date"])
    return rows


def _lhb_entries(
    symbol: str, analysis_date: date, window: int
) -> list[dict]:
    """Dragon-tiger list entries for one code in the trailing window."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_lhb_detail_em(
        start_date=(
            analysis_date - timedelta(days=window)
        ).strftime("%Y%m%d"),
        end_date=analysis_date.strftime("%Y%m%d"),
    )
    rows: list[dict] = []
    for _, row in frame.iterrows():
        if str(row.get("代码") or "") != symbol:
            continue
        observed = _as_date(row["上榜日"])
        if observed > analysis_date:
            continue
        rows.append({
            "date": observed,
            "net_buy": float(row.get("龙虎榜净买额") or 0),
            "reason": str(row.get("上榜原因") or "").strip(),
        })
    rows.sort(key=lambda item: item["date"])
    return rows


def _em_sector_series(
    sector: str, analysis_date: date, timeout: float
) -> list[PriceObservation]:
    """Recent industry-board index closes from EastMoney."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_board_industry_hist_em(
        symbol=sector,
        start_date=(analysis_date - timedelta(days=30)).strftime("%Y%m%d"),
        end_date=analysis_date.strftime("%Y%m%d"),
        period="日k",
        adjust="",
    )
    if frame is None or frame.empty:
        raise ValueError(f"EastMoney returned no rows for {sector!r}")
    observations: list[PriceObservation] = []
    for _, row in frame.iterrows():
        observations.append(PriceObservation(
            source="eastmoney",
            url=(
                "https://quote.eastmoney.com/center/boardlist.html"
                f"#industry-{sector}"
            ),
            price=float(row["收盘"]),
            observed_on=_as_date(row["日期"]),
            currency="CNY",
            volume=float(row.get("成交量") or 0) or None,
            upstream_origin="quote.eastmoney.com",
        ))
    return observations


def _ths_sector_names() -> list[str]:
    """All industry-board names known to the THS upstream."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_board_industry_name_ths()
    column = "name" if "name" in frame.columns else frame.columns[0]
    return [str(name) for name in frame[column]]


def _ths_match_sector(sector: str) -> str:
    """Resolve an EastMoney board name against the THS board list.

    THS and EastMoney use different industry taxonomies (e.g. 有色金属
    exists on EastMoney but not on THS), so the requested name is
    resolved first: exact match, then containment fuzzy match accepted
    only on a unique hit — multiple candidates mean the mapping is
    ambiguous and a wrong-board price must never be validated.
    """
    names = _ths_sector_names()
    if sector in names:
        return sector
    candidates = [
        name for name in names if sector in name or name in sector
    ]
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise ValueError(
            f"THS 板块名模糊匹配非唯一，拒绝猜测匹配"
            f"（东财侧：{sector!r}；THS 侧候选：{candidates}）"
        )
    raise ValueError(
        f"THS 板块列表中无 {sector!r} 的精确或包含式匹配"
        f"（东财侧：{sector!r}；THS 侧共 {len(names)} 个板块名，"
        "无相近候选）"
    )


def _ths_sector_series(
    sector: str, analysis_date: date, timeout: float
) -> list[PriceObservation]:
    """Recent industry index closes from the THS (10jqka) upstream."""
    # Resolve the board name before touching akshare so a taxonomy
    # mismatch surfaces as the candidate-bearing ValueError.
    resolved = _ths_match_sector(sector)

    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.stock_board_industry_index_ths(
        symbol=resolved,
        start_date=(analysis_date - timedelta(days=30)).strftime("%Y%m%d"),
        end_date=analysis_date.strftime("%Y%m%d"),
    )
    if frame is None or frame.empty:
        raise ValueError(f"THS returned no rows for {resolved!r}")
    observations: list[PriceObservation] = []
    for _, row in frame.iterrows():
        observations.append(PriceObservation(
            source="ths",
            url=f"https://q.10jqka.com.cn/thshy/#{resolved}",
            price=float(row["收盘价"]),
            observed_on=_as_date(row["日期"]),
            currency="CNY",
            volume=float(row.get("成交量") or 0) or None,
            upstream_origin="q.10jqka.com.cn",
        ))
    return observations


def _sector_flow_frame(indicator: str):
    """Raw flow-rank frame for one window (seam for column-layout tests)."""
    import akshare  # noqa: PLC0415 — optional dependency

    return akshare.stock_sector_fund_flow_rank(
        indicator=indicator, sector_type="行业资金流"
    )


def _sector_flow_rank(
    sector: str, indicator: str
) -> tuple[int, int, float]:
    """(rank, total sectors, net inflow) for one flow-rank window.

    AkShare renames the net-inflow column across versions, so the
    column is probed from a candidate list instead of hard-coding one
    layout (observed: ``主力净流入-净额`` with the window prefix).
    """
    frame = _sector_flow_frame(indicator)
    match = frame[frame["名称"].astype(str) == sector]
    if match.empty:
        raise ValueError(f"Sector {sector!r} not in the flow ranking")
    row = match.iloc[0]
    rank = int(row.get("序号") or (match.index[0] + 1))
    net_column = next(
        (
            column for column in (
                f"{indicator}主力净流入-净额",
                f"{indicator}主力净流入净额",
                f"{indicator}主力净流入",
            )
            if column in frame.columns
        ),
        None,
    )
    if net_column is None:
        raise KeyError(
            f"No net-inflow column for window {indicator!r}; "
            f"columns: {list(frame.columns)}"
        )
    net = float(row[net_column])
    return (rank, len(frame), net)


def _sector_etf_snapshot(sector: str) -> dict:
    """Largest sector-matching ETF's latest share-count snapshot."""
    import akshare  # noqa: PLC0415 — optional dependency

    frame = akshare.fund_etf_spot_em()
    match = frame[frame["名称"].astype(str).str.contains(
        sector, regex=False
    )]
    if match.empty:
        raise ValueError(f"No ETF name matches sector {sector!r}")
    row = match.sort_values("总市值", ascending=False).iloc[0]
    return {
        "code": str(row["代码"]),
        "name": str(row["名称"]),
        "observed_on": _as_date(row["数据日期"]),
        "shares": float(row["最新份额"]),
    }


# --- record builders --------------------------------------------------------

def _dual_source_price(
    result: ProviderResult,
    *,
    entity_label: str,
    query: str,
    fetchers: list[tuple[str, callable]],
    tolerance: float,
    note: str,
) -> None:
    """Shared dual-upstream fail-closed price path (same as equities).

    Each upstream submits a short daily series; validation runs on the
    latest common trading day (``align_latest_common``), so a T vs T-1
    freshness gap between upstreams never reads as a price deviation.
    """
    series: list[list[PriceObservation]] = []
    for name, fetch in fetchers:
        try:
            observations = fetch()
            if not observations:
                raise ValueError(f"{name} returned an empty series")
            series.append(observations)
        except Exception as error:
            result.failures.append(
                provider_failure("cn", f"{name}_close", error)
            )
    if len(series) != 2:
        result.degraded.append(
            f"cn: {entity_label} 仅 {len(series)} 个上游可用，"
            "不足双源校验，价格记录未入库（fail-closed）"
        )
        return
    # Same latest trading day but diverging prices is a real data
    # quality alarm — never soften it by falling back to an earlier
    # common day.
    conflict = latest_same_day_conflict(series[0], series[1], tolerance)
    if conflict is not None:
        result.cross_validation_failed.append(conflict)
        result.degraded.append(
            f"cn: {entity_label} 最新交易日双源价差超限"
            f"（{conflict['reason']}），价格记录未入库（fail-closed）"
        )
        return
    aligned = align_latest_common(series[0], series[1])
    if aligned is None:
        result.degraded.append(
            f"cn: {entity_label} 双上游日线序列无公共交易日，"
            "无法对齐校验，价格记录未入库（fail-closed）"
        )
        return
    check = cross_validate_price(aligned[0], aligned[1], tolerance)
    if check["passed"]:
        result.cross_validation_passed.append(check)
        result.records.extend(build_price_records(
            entity_label=entity_label,
            query=query,
            observations=(aligned[0], aligned[1]),
            source_type="market_data_aggregated",
            check=check,
            note=f"{note}；{CN_AGGREGATOR_NOTE}",
        ))
    else:
        result.cross_validation_failed.append(check)
        result.degraded.append(
            f"cn: {entity_label} 双上游校验失败（{check['reason']}），"
            "价格记录未入库（fail-closed）"
        )


def _aggregated_record(
    result: ProviderResult,
    *,
    category: str,
    item: str,
    query: str,
    title: str,
    url: str,
    lines: list[str],
    observed_on: date,
) -> None:
    """Append one aggregator-grade record with the shared disclaimer."""
    result.records.append(make_record(
        category=category,
        provider="market_data_akshare",
        query=query,
        title=title,
        url=url,
        content="\n".join([*lines, CN_AGGREGATOR_NOTE]),
        published_at=observed_on.isoformat(),
        source_type="market_data_aggregated",
        upstream_origin=f"akshare ({item})",
    ))


def _stock_flow_record(
    result: ProviderResult,
    entity_label: str,
    symbol: str,
    analysis_date: date,
) -> None:
    rows = _fund_flow_series(symbol, analysis_date, FLOW_WINDOW_DAYS)
    if not rows:
        raise ValueError(f"No fund-flow rows for {symbol!r}")
    observed_on = rows[-1]["date"]
    lag_days = max(0, (analysis_date - observed_on).days)
    main_total = sum(row["main_net"] for row in rows)
    xl_total = sum(row["xl_net"] for row in rows)
    direction, streak = _streak_days(
        [row["main_net"] for row in rows]
    )
    _aggregated_record(
        result,
        category="market_data_capital_flow",
        item="stock_individual_fund_flow",
        query=f"{symbol} 主力资金流",
        title=f"{entity_label} 主力资金流 {observed_on.isoformat()}",
        url=f"https://data.eastmoney.com/zjlx/{symbol}.html",
        lines=[
            content_header(
                f"{entity_label} 主力资金流", observed_on, lag_days
            ),
            (
                f"近{len(rows)}个交易日主力净流入合计 {_compact(main_total)}，"
                f"超大单净流入合计 {_compact(xl_total)}"
            ),
            (
                f"最近一日主力{direction} {_compact(abs(rows[-1]['main_net']))}，"
                f"连续{direction} {streak} 天"
            ),
        ],
        observed_on=observed_on,
    )


def _stock_margin_record(
    result: ProviderResult,
    entity_label: str,
    symbol: str,
    analysis_date: date,
) -> None:
    rows = _margin_series(symbol, analysis_date, MARGIN_WINDOW_DAYS)
    if not rows:
        raise ValueError(f"No margin rows for {symbol!r}")
    observed_on = rows[-1]["date"]
    lag_days = max(0, (analysis_date - observed_on).days)
    latest = rows[-1]["balance"]
    lines = [
        content_header(
            f"{entity_label} 融资融券余额", observed_on, lag_days
        ),
        f"最新余额 {_compact(latest)}（近{len(rows)}个观测日）",
    ]
    if len(rows) >= 2:
        prev = rows[-2]["balance"]
        first = rows[0]["balance"]
        lines.append(
            f"余额环比上一观测日 {(latest - prev) / prev:+.2%}，"
            f"较窗口首日 {(latest - first) / first:+.2%}"
        )
    _aggregated_record(
        result,
        category="market_data_margin",
        item="stock_margin_detail",
        query=f"{symbol} 融资融券余额",
        title=f"{entity_label} 融资融券 {observed_on.isoformat()}",
        url=f"https://data.eastmoney.com/rzrq/detail/{symbol}.html",
        lines=lines,
        observed_on=observed_on,
    )


def _stock_block_trade_record(
    result: ProviderResult,
    entity_label: str,
    symbol: str,
    analysis_date: date,
) -> None:
    rows = _block_trades(symbol, analysis_date, BLOCK_WINDOW_DAYS)
    if not rows:
        raise ValueError(
            f"No block trades for {symbol!r} in the window"
        )
    observed_on = rows[-1]["date"]
    lag_days = max(0, (analysis_date - observed_on).days)
    total = sum(row["amount"] for row in rows)
    _aggregated_record(
        result,
        category="market_data_block_trade",
        item="stock_dzjy_mrmx",
        query=f"{symbol} 大宗交易",
        title=f"{entity_label} 大宗交易 {observed_on.isoformat()}",
        url=f"https://data.eastmoney.com/dzjy/dzjy_mrtj.html#{symbol}",
        lines=[
            content_header(
                f"{entity_label} 大宗交易", observed_on, lag_days
            ),
            (
                f"近{BLOCK_WINDOW_DAYS}天大宗交易 {len(rows)} 笔，"
                f"合计成交额 {_compact(total)}"
            ),
            f"最近一笔发生于 {observed_on.isoformat()}",
        ],
        observed_on=observed_on,
    )


def _stock_lhb_record(
    result: ProviderResult,
    entity_label: str,
    symbol: str,
    analysis_date: date,
) -> None:
    rows = _lhb_entries(symbol, analysis_date, LHB_WINDOW_DAYS)
    if not rows:
        raise ValueError(
            f"No dragon-tiger entries for {symbol!r} in the window"
        )
    observed_on = rows[-1]["date"]
    lag_days = max(0, (analysis_date - observed_on).days)
    net_total = sum(row["net_buy"] for row in rows)
    _aggregated_record(
        result,
        category="market_data_institutional_cn",
        item="stock_lhb_detail_em",
        query=f"{symbol} 龙虎榜",
        title=f"{entity_label} 龙虎榜 {observed_on.isoformat()}",
        url=f"https://data.eastmoney.com/stock/lhb/{symbol}.html",
        lines=[
            content_header(
                f"{entity_label} 龙虎榜", observed_on, lag_days
            ),
            (
                f"近{LHB_WINDOW_DAYS}天上榜 {len(rows)} 次，"
                f"龙虎榜净买额合计 {_compact(net_total)}"
            ),
            (
                f"最近上榜 {observed_on.isoformat()}"
                f"（{rows[-1]['reason'] or '原因未披露'}）"
            ),
        ],
        observed_on=observed_on,
    )


def _sector_flow_record(
    result: ProviderResult,
    entity_label: str,
    sector: str,
    analysis_date: date,
) -> None:
    lines = [content_header(f"{entity_label} 主力资金流排名", analysis_date)]
    available = 0
    for indicator in SECTOR_FLOW_WINDOWS:
        # One window failing (akshare drops or renames a column across
        # versions) must not sink the whole record: keep the windows
        # that resolve and annotate the ones that do not.
        try:
            rank, total, net = _sector_flow_rank(sector, indicator)
        except Exception:
            lines.append(
                f"{indicator}窗口数据不可用"
                "（当前数据源版本缺少该窗口字段）"
            )
            continue
        available += 1
        lines.append(
            f"{indicator}主力净流入 {_compact(net)}，"
            f"行业排名 {rank}/{total}"
        )
    if not available:
        raise ValueError(
            f"No flow-rank window available for {sector!r} "
            f"(tried {SECTOR_FLOW_WINDOWS})"
        )
    _aggregated_record(
        result,
        category="market_data_sector_flow",
        item="stock_sector_fund_flow_rank",
        query=f"{sector} 板块主力资金流排名",
        title=f"{entity_label} 板块资金流 {analysis_date.isoformat()}",
        url="https://data.eastmoney.com/bkzj/hy.html",
        lines=lines,
        observed_on=analysis_date,
    )


def _sector_etf_record(
    result: ProviderResult,
    entity_label: str,
    sector: str,
    analysis_date: date,
) -> None:
    snapshot = _sector_etf_snapshot(sector)
    observed_on = snapshot["observed_on"]
    if observed_on > analysis_date:
        raise ValueError(
            "ETF share observation is in the future relative to the "
            "analysis date"
        )
    lag_days = max(0, (analysis_date - observed_on).days)
    _aggregated_record(
        result,
        category="market_data_etf_flow",
        item="fund_etf_spot_em",
        query=f"{sector} ETF 份额",
        title=(
            f"{entity_label} 相关ETF份额 {observed_on.isoformat()}"
        ),
        url=f"https://fund.eastmoney.com/{snapshot['code']}.html",
        lines=[
            content_header(
                f"{entity_label} 相关ETF份额", observed_on, lag_days
            ),
            (
                f"{snapshot['name']}（{snapshot['code']}）"
                f"最新份额 {snapshot['shares']:,.0f}"
            ),
            "份额为最新快照，历史变动序列暂不可得（东财现货口径）",
        ],
        observed_on=observed_on,
    )


def fetch_cn(
    subject: str,
    code: str | None,
    analysis_date: date,
    *,
    asset_class: str,
    tolerance: float = 0.005,
    timeout: float = 20.0,
    lookback_days: int = 365,
    types: set[str] | None = None,
) -> ProviderResult:
    """A-share stock or sector records, aggregator-grade and fail-closed."""
    result = ProviderResult()
    wanted = types or {
        "price", "positioning", "flow", "institutional",
    }

    if asset_class == "cn_stock":
        symbol = (code or "").strip()
        if not symbol:
            result.failures.append(provider_failure(
                "cn", "code",
                "--code is required for cn_stock data (e.g. 600519)",
            ))
            return result
        entity_label = f"{subject}（{symbol}）"
        if "price" in wanted:
            _dual_source_price(
                result,
                entity_label=entity_label,
                query=f"{symbol} A股收盘行情",
                fetchers=[
                    ("eastmoney", lambda: _em_stock_series(
                        symbol, analysis_date, timeout
                    )),
                    ("sina", lambda: _sina_stock_series(
                        symbol, analysis_date, timeout
                    )),
                ],
                tolerance=tolerance,
                note="聚合器双上游（东方财富/新浪），已交叉校验",
            )
        for data_type, item, build in (
            ("flow", "capital_flow", _stock_flow_record),
            ("positioning", "margin", _stock_margin_record),
            ("institutional", "block_trade", _stock_block_trade_record),
            ("institutional", "lhb", _stock_lhb_record),
        ):
            if data_type not in wanted:
                continue
            try:
                build(result, entity_label, symbol, analysis_date)
            except Exception as error:
                result.failures.append(
                    provider_failure("cn", item, error)
                )
                result.degraded.append(
                    f"cn: {symbol} {item} 不可用"
                    f"（{type(error).__name__}）"
                )
        return result

    # cn_sector
    sector = (code or subject).strip()
    entity_label = (
        subject if sector == subject else f"{subject}（{sector}）"
    )
    if "price" in wanted:
        _dual_source_price(
            result,
            entity_label=f"{entity_label} 板块指数",
            query=f"{sector} 板块指数行情",
            fetchers=[
                ("eastmoney", lambda: _em_sector_series(
                    sector, analysis_date, timeout
                )),
                ("ths", lambda: _ths_sector_series(
                    sector, analysis_date, timeout
                )),
            ],
            tolerance=tolerance,
            note="聚合器双上游（东方财富/同花顺），已交叉校验",
        )
    for data_type, item, build in (
        ("flow", "sector_flow", _sector_flow_record),
        ("flow", "sector_etf", _sector_etf_record),
    ):
        if data_type not in wanted:
            continue
        try:
            build(result, entity_label, sector, analysis_date)
        except Exception as error:
            result.failures.append(
                provider_failure("cn", item, error)
            )
            result.degraded.append(
                f"cn: {sector} {item} 不可用（{type(error).__name__}）"
            )
    return result
