"""Unit tests for the structured market data channel (network mocked).

Covers the fail-closed contract end to end: cross validation, quote
grammar isolation, consensus formation through the real
``resolve_consensus_market_snapshot``, weights, idempotent import,
future-date rejection, and graceful degradation without extras.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from structflow import skill_runtime
from structflow.evidence import EvidenceRecord, source_weight
from structflow.input_resolver import EntityProfile, InputKind
from structflow.main import build_parser
from structflow.market_data import collect_market_data
from structflow.market_data.base import (
    MarketDataContentError,
    PriceObservation,
    ProviderResult,
    build_price_records,
    cross_validate_price,
    make_record,
    matches_quote_pattern,
)
from structflow.market_data.providers import (
    cn, cot, crypto, dbnomics, edgar, eia, equities, fred,
)
from structflow.market_snapshot import resolve_consensus_market_snapshot
from structflow.models import TimeHorizon
from structflow.skill_runtime import (
    GenerationMode,
    ResearchRequest,
    fetch_market_data,
    initialize_run,
)


AS_OF = date(2026, 7, 28)
OBSERVED = AS_OF - timedelta(days=1)


def _observation(
    source: str, url: str, price: float, upstream: str
) -> PriceObservation:
    return PriceObservation(
        source=source,
        url=url,
        price=price,
        observed_on=OBSERVED,
        currency="USD",
        volume=1_500_000,
        upstream_origin=upstream,
    )


def _yfinance_obs(price: float = 231.11) -> PriceObservation:
    return _observation(
        "yfinance",
        "https://finance.yahoo.com/quote/GLD",
        price,
        "finance.yahoo.com",
    )


def _stooq_obs(price: float = 231.53) -> PriceObservation:
    return _observation(
        "stooq", "https://stooq.com/q/?s=gld", price, "stooq.com"
    )


def _fetch_equities(monkeypatch, yf_price: float, stooq_price: float):
    monkeypatch.setattr(
        equities, "_yfinance_series",
        lambda code, timeout, lookback_days, as_of: [
            _yfinance_obs(yf_price),
        ],
    )
    monkeypatch.setattr(
        equities, "_stooq_series",
        lambda code, timeout, as_of: [_stooq_obs(stooq_price)],
    )
    return equities.fetch_equities(
        "SPDR Gold Shares", "GLD", AS_OF,
        tolerance=0.005, types={"price"},
    )


# 1. Cross validation: fail-closed core path -------------------------------

def test_cross_validation_within_tolerance_yields_two_records(monkeypatch):
    result = _fetch_equities(monkeypatch, 231.11, 231.80)  # dev ≈ 0.30%

    assert len(result.records) == 2
    assert result.cross_validation_passed
    assert not result.cross_validation_failed
    assert not result.degraded
    urls = {record["url"] for record in result.records}
    assert len(urls) == 2
    for record in result.records:
        assert record["category"] == "market_data_price"
        assert record["source_type"] == "market_data_aggregated"
        assert matches_quote_pattern(record["content"])


def test_cross_validation_rejects_excess_deviation_fail_closed(monkeypatch):
    result = _fetch_equities(monkeypatch, 100.0, 100.8)  # dev ≈ 0.80%

    assert result.records == []
    assert result.cross_validation_failed
    failed = result.cross_validation_failed[0]
    prices = {obs["price"] for obs in failed["observations"]}
    assert prices == {100.0, 100.8}
    assert "tolerance" in failed and failed["reason"]
    assert result.degraded


def test_single_aggregator_source_yields_no_price_records(monkeypatch):
    monkeypatch.setattr(
        equities, "_yfinance_series",
        lambda code, timeout, lookback_days, as_of: [_yfinance_obs()],
    )

    def _broken_stooq(code, timeout, as_of):
        raise ConnectionError("stooq unreachable")

    monkeypatch.setattr(equities, "_stooq_series", _broken_stooq)
    result = equities.fetch_equities(
        "SPDR Gold Shares", "GLD", AS_OF, types={"price"},
    )

    assert result.records == []
    assert result.degraded
    assert any(
        failure["error_type"] == "ConnectionError"
        for failure in result.failures
    )


# 2. Dual-source records reach real consensus ------------------------------

def test_price_records_form_consensus_via_real_snapshot(monkeypatch):
    result = _fetch_equities(monkeypatch, 231.11, 231.80)
    records = [
        EvidenceRecord(
            category=item["category"],
            provider=item["provider"],
            query=item["query"],
            title=item["title"],
            url=item["url"],
            content=item["content"],
            published_at=item["published_at"],
            source_type=item["source_type"],
            upstream_origin=item["upstream_origin"],
            quality_score=item["quality_score"],
        )
        for item in result.records
    ]
    profile = EntityProfile(
        input_kind=InputKind.ASSET,
        canonical_name="SPDR Gold Shares",
        ticker="GLD",
        reporting_currency="USD",
    )

    snapshot = resolve_consensus_market_snapshot(
        records, profile, AS_OF.isoformat()
    )

    assert snapshot is not None
    assert snapshot.price == pytest.approx(231.455, abs=0.01)
    assert len(snapshot.source_ids) == 2
    assert snapshot.as_of == OBSERVED.isoformat()


# 3. Quote-grammar isolation and lag annotations ---------------------------

def _cot_rows() -> list[dict]:
    rows = []
    net = 150_000
    for week in range(8):
        report_date = AS_OF - timedelta(days=3 + 7 * week)
        rows.append({
            "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
            "report_date_as_yyyy_mm_dd": report_date.isoformat(),
            "noncomm_positions_long_all": str(200_000 - 2_000 * week),
            "noncomm_positions_short_all": str(200_000 - net),
            "comm_positions_long_all": "90000",
            "comm_positions_short_all": "240000",
        })
    return rows


def test_cot_record_is_lag_annotated_and_never_price_shaped(monkeypatch):
    monkeypatch.setattr(
        cot, "_fetch_rows",
        lambda keyword, limit, timeout: (_cot_rows(), "exchange_official"),
    )
    result = cot.fetch_cot("黄金", "gold", AS_OF)

    assert len(result.records) == 1
    record = result.records[0]
    assert record["category"] == "market_data_positioning"
    assert record["source_type"] == "exchange_official"
    assert "滞后" in record["content"]
    assert "基于周二持仓数据" in record["content"]
    assert "百分位" in record["content"]
    assert not matches_quote_pattern(
        f"{record['title']}\n{record['content']}"
    )


def test_fred_records_are_macro_only_and_key_gated(monkeypatch):
    monkeypatch.setattr(
        fred, "_series_latest",
        lambda series_id, api_key, timeout: (OBSERVED, 2.13),
    )
    result = fred.fetch_fred("黄金", AS_OF, api_key="test-key")

    assert len(result.records) == 3
    for record in result.records:
        assert record["category"] == "market_data_macro"
        assert record["source_type"] == "market_data_official"
        assert not matches_quote_pattern(
            f"{record['title']}\n{record['content']}"
        )

    missing = fred.fetch_fred("黄金", AS_OF, api_key="")
    assert missing.records == []
    assert missing.degraded
    assert missing.failures[0]["item"] == "api_key"


def test_make_record_enforces_quote_grammar_contract():
    with pytest.raises(MarketDataContentError):
        make_record(
            category="market_data_positioning",
            provider="market_data_test",
            query="q",
            title="持仓",
            url="https://example.com/positioning",
            content="黄金 2026年07月27日\n收盘价100.00元",
            published_at=OBSERVED.isoformat(),
            source_type="exchange_official",
        )
    with pytest.raises(MarketDataContentError):
        make_record(
            category="market_data_price",
            provider="market_data_test",
            query="q",
            title="行情",
            url="https://example.com/price",
            content="黄金 2026年07月27日 没有报价格式",
            published_at=OBSERVED.isoformat(),
            source_type="market_data_aggregated",
        )


# 4. Source weights ---------------------------------------------------------

def test_market_data_source_weights():
    assert source_weight("exchange_official") == 0.93
    assert source_weight("market_data_official") == 0.92
    assert source_weight("market_data_aggregated") == 0.70


# 5. Workspace import: idempotency, future dates, degradation --------------

def _initialize(
    tmp_path: Path,
    subject: str = "黄金",
    analysis_date: date | None = None,
) -> ResearchRequest:
    kwargs: dict = dict(
        subject=subject,
        region="Global",
        time_horizon=TimeHorizon.MID,
        generation_mode=GenerationMode.CORE,
    )
    if analysis_date is not None:
        kwargs["analysis_date"] = analysis_date
    request = ResearchRequest(**kwargs)
    initialize_run(request, root=tmp_path)
    return request


def _fake_result(analysis_date: date) -> ProviderResult:
    observed = analysis_date - timedelta(days=1)
    obs_a = PriceObservation(
        source="yfinance",
        url="https://finance.yahoo.com/quote/GLD",
        price=231.11,
        observed_on=observed,
        upstream_origin="finance.yahoo.com",
    )
    obs_b = PriceObservation(
        source="stooq",
        url="https://stooq.com/q/?s=gld",
        price=231.53,
        observed_on=observed,
        upstream_origin="stooq.com",
    )
    check = cross_validate_price(obs_a, obs_b, 0.005)
    records = build_price_records(
        entity_label="SPDR Gold Shares（GLD）",
        query="GLD close price",
        observations=(obs_a, obs_b),
        source_type="market_data_aggregated",
        check=check,
    )
    records.append(make_record(
        category="market_data_positioning",
        provider="market_data_cftc_cot",
        query="CFTC COT gold",
        title="黄金 CFTC COT 持仓报告",
        url="https://publicreporting.cftc.gov/resource/6dca-aqww.json?market=gold",
        content=(
            f"黄金 CFTC COT持仓 {observed.year}年{observed.month:02d}月"
            f"{observed.day:02d}日 [数据滞后3天]\n非商业净持仓 +150,000 手\n"
            "基于周二持仓数据，公布滞后3个交易日"
        ),
        published_at=observed.isoformat(),
        source_type="exchange_official",
    ))
    return ProviderResult(
        records=records, cross_validation_passed=[check]
    )


def test_fetch_market_data_import_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")
    request = _initialize(tmp_path)
    fake = _fake_result(request.analysis_date)
    monkeypatch.setattr(
        skill_runtime, "collect_market_data",
        lambda **kwargs: fake,
    )

    first = fetch_market_data(
        "黄金", asset_class="commodity", code="GLD", root=tmp_path
    )
    second = fetch_market_data(
        "黄金", asset_class="commodity", code="GLD", root=tmp_path
    )

    assert first["ok"] is True
    assert first["added_unique_sources"] == 3
    assert set(first["categories"]) == {
        "market_data_price", "market_data_positioning",
    }
    assert first["cross_validation"]["passed"]
    assert not first["cross_validation"]["failed"]
    assert second["added_unique_sources"] == 0
    # Idempotent rerun: dedup keeps added at 0, yet the data is in the
    # store — ok must stay true.
    assert second["ok"] is True
    assert second["total_unique_sources"] == first["total_unique_sources"]
    cache = json.loads(
        Path(first["search_cache"]).read_text(encoding="utf-8")
    )
    assert cache["metadata"]["total_sources"] == 3


def test_fetch_market_data_rejects_future_observations(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")
    request = _initialize(tmp_path)
    future = (request.analysis_date + timedelta(days=5)).isoformat()
    fake = ProviderResult(records=[make_record(
        category="market_data_macro",
        provider="market_data_fred",
        query="FRED DFII10",
        title="美国10年期实际利率",
        url="https://fred.stlouisfed.org/series/DFII10",
        content="美国10年期实际利率 2099年01月01日\nDFII10 读数 2.1%",
        published_at=future,
        source_type="market_data_official",
    )])
    monkeypatch.setattr(
        skill_runtime, "collect_market_data",
        lambda **kwargs: fake,
    )

    result = fetch_market_data(
        "黄金", asset_class="commodity", root=tmp_path
    )

    assert result["rejected_future_records"] == 1
    assert result["added_unique_sources"] == 0
    # Every record was rejected — the host must not treat this as a
    # successful structured pull.
    assert result["ok"] is False


def test_fetch_market_data_degrades_without_dependencies(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    _initialize(tmp_path, subject="ETH")

    def _no_ccxt(exchange_id, timeout):
        raise ImportError("No module named 'ccxt'")

    monkeypatch.setattr(crypto, "_exchange", _no_ccxt)

    def _no_network(series_id, timeout):
        raise ConnectionError("api.db.nomics.world unreachable")

    # DBnomics is keyless and would otherwise hit the live API here.
    monkeypatch.setattr(dbnomics, "_series_doc", _no_network)

    result = fetch_market_data(
        "ETH", asset_class="crypto", code="ETH/USDT", root=tmp_path
    )

    assert result["ok"] is False
    assert result["added_unique_sources"] == 0
    assert result["degraded"]
    assert any(
        failure["error_type"] == "ImportError"
        for failure in result["failures"]
    )


def test_router_unlocks_cn_asset_classes(monkeypatch):
    sentinel = ProviderResult(records=[{"category": "market_data_price"}])
    captured = {}

    def _fake_fetch_cn(subject, code, analysis_date, **kwargs):
        captured["asset_class"] = kwargs["asset_class"]
        captured["analysis_date"] = analysis_date
        return sentinel

    monkeypatch.setattr(cn, "fetch_cn", _fake_fetch_cn)

    result = collect_market_data(
        subject="贵州茅台",
        asset_class="cn_stock",
        code="600519",
        types={"price"},
        analysis_date=AS_OF,
    )

    assert result.records == sentinel.records
    assert captured == {"asset_class": "cn_stock", "analysis_date": AS_OF}
    assert not any(
        failure["provider"] == "router" for failure in result.failures
    )


def test_router_routes_institutional_to_edgar(monkeypatch):
    sentinel = ProviderResult(
        records=[{"category": "market_data_institutional"}]
    )
    monkeypatch.setattr(
        edgar, "fetch_edgar",
        lambda subject, code, analysis_date, **kwargs: sentinel,
    )

    result = collect_market_data(
        subject="SPDR Gold Shares",
        asset_class="equity",
        code="GLD",
        types={"institutional"},
        analysis_date=AS_OF,
    )

    assert result.records == sentinel.records
    assert result.failures == []


# 6. CLI registration -------------------------------------------------------

def test_cli_registers_fetch_market_data_command():
    args = build_parser().parse_args([
        "fetch-market-data", "黄金",
        "--asset-class", "commodity",
        "--code", "GC=F",
        "--types", "price", "positioning",
        "--date", "2026-07-28",
    ])

    assert args.command == "fetch-market-data"
    assert args.asset_class == "commodity"
    assert args.types == ["price", "positioning"]
    assert args.date == "2026-07-28"


# 7. Regressions from real-network verification ----------------------------

class _FakeCsvResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


def test_stooq_uses_csv_even_when_pandas_datareader_is_broken(monkeypatch):
    """pandas-datareader raises NotImplementedError for stooq (>=0.11);
    the CSV endpoint must serve the observation regardless."""
    import sys
    import types

    fake_data = types.ModuleType("pandas_datareader.data")

    def _broken_reader(*args, **kwargs):
        raise NotImplementedError("data_source='stooq' is not implemented")

    fake_data.DataReader = _broken_reader
    fake_pdr = types.ModuleType("pandas_datareader")
    fake_pdr.data = fake_data
    monkeypatch.setitem(sys.modules, "pandas_datareader", fake_pdr)
    monkeypatch.setitem(sys.modules, "pandas_datareader.data", fake_data)

    csv_payload = (
        "Date,Open,High,Low,Close,Volume\n"
        "2026-07-24,228.10,230.00,227.90,229.40,1100000\n"
        "2026-07-27,229.00,232.00,228.50,231.53,1200000\n"
    )
    requested: list[str] = []

    def _fake_get(url, params=None, timeout=None):
        requested.append(params["s"])
        return _FakeCsvResponse(csv_payload)

    monkeypatch.setattr("requests.get", _fake_get)

    observations = equities._stooq_series("GLD", timeout=5.0, as_of=AS_OF)

    assert requested == ["gld"]
    assert [obs.observed_on for obs in observations] == [
        date(2026, 7, 24), date(2026, 7, 27),
    ]
    latest = observations[-1]
    assert latest.source == "stooq"
    assert latest.price == 231.53
    assert "stooq.com" in latest.url


def test_stooq_csv_retries_with_us_suffix(monkeypatch):
    csv_payload = (
        "Date,Open,High,Low,Close,Volume\n"
        "2026-07-27,229.00,232.00,228.50,231.53,1200000\n"
    )
    requested: list[str] = []

    def _fake_get(url, params=None, timeout=None):
        requested.append(params["s"])
        if params["s"] == "gld":
            return _FakeCsvResponse("No data\n")
        return _FakeCsvResponse(csv_payload)

    monkeypatch.setattr("requests.get", _fake_get)

    observations = equities._stooq_series("GLD", timeout=5.0, as_of=AS_OF)

    assert requested == ["gld", "gld.us"]
    assert observations[-1].price == 231.53
    assert observations[-1].url.endswith("s=gld.us")


def _install_fake_cot_reports(monkeypatch, cot_year):
    import sys
    import types

    fake = types.ModuleType("cot_reports")
    fake.cot_year = cot_year
    monkeypatch.setitem(sys.modules, "cot_reports", fake)


def test_cot_reports_call_never_pollutes_working_directory(
    monkeypatch, tmp_path
):
    """cot_reports.cot_year writes annual.txt into the CWD; the call
    must run in a scratch directory and restore the CWD on error."""
    import os

    project_cwd = os.getcwd()

    def _dirty_cot_year(**kwargs):
        Path(os.getcwd(), "annual.txt").write_text("x", encoding="utf-8")
        raise RuntimeError("download failed after writing temp files")

    _install_fake_cot_reports(monkeypatch, _dirty_cot_year)

    with pytest.raises(RuntimeError):
        cot._rows_via_cot_reports("gold", limit=8)

    assert os.getcwd() == project_cwd
    assert not Path(project_cwd, "annual.txt").exists()


def test_cot_reports_success_path_restores_cwd_and_leaves_no_residue(
    monkeypatch,
):
    import os

    pandas = pytest.importorskip("pandas")
    project_cwd = os.getcwd()
    write_dirs: list[str] = []

    def _dirty_cot_year(**kwargs):
        write_dirs.append(os.getcwd())
        Path(os.getcwd(), "annual.txt").write_text("x", encoding="utf-8")
        return pandas.DataFrame([{
            "Market and Exchange Names": "GOLD - COMMODITY EXCHANGE INC.",
            "As of Date in Form YYYY-MM-DD": "2026-07-21",
            "Noncommercial Positions-Long (All)": 200000,
            "Noncommercial Positions-Short (All)": 50000,
            "Commercial Positions-Long (All)": 90000,
            "Commercial Positions-Short (All)": 240000,
        }])

    _install_fake_cot_reports(monkeypatch, _dirty_cot_year)

    rows = cot._rows_via_cot_reports("gold", limit=8)

    assert len(rows) == 1
    assert rows[0]["report_date_as_yyyy_mm_dd"] == "2026-07-21"
    assert os.getcwd() == project_cwd
    assert not Path(project_cwd, "annual.txt").exists()
    # The write landed in the scratch directory, not the project CWD.
    assert write_dirs and write_dirs[0] != project_cwd
    assert not Path(write_dirs[0]).exists()


# 8. Future-date rejection anchors to the effective --date ------------------

def _macro_result(published_on: date) -> ProviderResult:
    return ProviderResult(records=[make_record(
        category="market_data_macro",
        provider="market_data_fred",
        query="FRED DFII10",
        title="美国10年期实际利率",
        url="https://fred.stlouisfed.org/series/DFII10",
        content=(
            f"美国10年期实际利率 {published_on.year}年"
            f"{published_on.month:02d}月{published_on.day:02d}日\n"
            "DFII10 读数 2.1%"
        ),
        published_at=published_on.isoformat(),
        source_type="market_data_official",
    )])


def test_backdated_date_rejects_observations_after_it(tmp_path, monkeypatch):
    """Workspace initialized on day N, analysis backdated via --date to
    N-1: an observation from day N must be rejected as future data
    relative to the backdated analysis date (no look-ahead leakage)."""
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")
    workspace_day = AS_OF + timedelta(days=1)
    _initialize(tmp_path, analysis_date=workspace_day)
    # Observation between --date and the workspace analysis_date.
    fake = _macro_result(workspace_day)
    monkeypatch.setattr(
        skill_runtime, "collect_market_data", lambda **kwargs: fake
    )

    result = fetch_market_data(
        "黄金", asset_class="commodity",
        as_of=AS_OF.isoformat(), root=tmp_path,
    )

    assert result["rejected_future_records"] == 1
    assert result["added_unique_sources"] == 0
    assert result["total_unique_sources"] == 0
    assert result["source_ids"] == []
    cache = json.loads(
        Path(result["search_cache"]).read_text(encoding="utf-8")
    )
    assert cache["metadata"]["total_sources"] == 0
    # The stored workspace request keeps its own analysis date.
    reloaded = skill_runtime._load_request(
        skill_runtime.workspace_for("黄金", tmp_path)
    )
    assert reloaded.analysis_date == workspace_day


def test_backdated_date_accepts_observation_on_that_date(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")
    workspace_day = AS_OF + timedelta(days=1)
    _initialize(tmp_path, analysis_date=workspace_day)
    fake = _macro_result(AS_OF)
    monkeypatch.setattr(
        skill_runtime, "collect_market_data", lambda **kwargs: fake
    )

    result = fetch_market_data(
        "黄金", asset_class="commodity",
        as_of=AS_OF.isoformat(), root=tmp_path,
    )

    assert result["rejected_future_records"] == 0
    assert result["added_unique_sources"] == 1
    assert result["ok"] is True


# 9. Phase 2 providers: SEC 13F (edgar) and A-share (cn) --------------------

def _edgar_snapshots() -> list[dict]:
    return [
        {  # future report period must be ignored
            "period": AS_OF + timedelta(days=30),
            "holders": {"Future Fund": 999_999.0},
            "total_shares": 999_999.0,
        },
        {
            "period": date(2026, 6, 30),
            "holders": {
                "Alpha Advisors": 100_000.0,
                "Beta Capital": 150_000.0,
                "Gamma Partners": 50_000.0,
            },
            "total_shares": 300_000.0,
        },
        {
            "period": date(2026, 3, 31),
            "holders": {
                "Alpha Advisors": 80_000.0,
                "Beta Capital": 160_000.0,
            },
            "total_shares": 240_000.0,
        },
    ]


def test_edgar_record_is_lag_annotated_and_never_price_shaped(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")
    monkeypatch.setattr(
        edgar, "_holdings_overview",
        lambda code, identity, timeout: _edgar_snapshots(),
    )

    result = edgar.fetch_edgar("SPDR Gold Shares", "GLD", AS_OF)

    assert len(result.records) == 1
    record = result.records[0]
    assert record["category"] == "market_data_institutional"
    assert record["source_type"] == "market_data_official"
    assert record["quality_score"] == 0.92
    assert record["published_at"] == "2026-06-30"  # future period skipped
    assert "[数据滞后28天]" in record["content"]
    assert "滞后 45 天，仅供结构研究，不代表当前持仓" in record["content"]
    assert "增持 1 家 / 减持 1 家" in record["content"]
    assert "样本口径" in record["content"]
    assert not matches_quote_pattern(
        f"{record['title']}\n{record['content']}"
    )


def test_edgar_requires_identity_and_degrades(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

    result = edgar.fetch_edgar("SPDR Gold Shares", "GLD", AS_OF)

    assert result.records == []
    assert result.degraded
    assert result.failures[0]["item"] == "identity"


def test_edgar_degrades_without_dependency(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")

    def _no_edgartools(code, identity, timeout):
        raise ImportError("No module named 'edgar'")

    monkeypatch.setattr(edgar, "_holdings_overview", _no_edgartools)

    result = edgar.fetch_edgar("SPDR Gold Shares", "GLD", AS_OF)

    assert result.records == []
    assert result.degraded
    assert result.failures[0]["error_type"] == "ImportError"


def _cn_observation(
    source: str, url: str, upstream: str, price: float
) -> PriceObservation:
    return PriceObservation(
        source=source,
        url=url,
        price=price,
        observed_on=OBSERVED,
        currency="CNY",
        volume=1_000_000,
        upstream_origin=upstream,
    )


def _patch_cn_price(monkeypatch, em_price: float, sina_price: float):
    monkeypatch.setattr(
        cn, "_em_stock_series",
        lambda symbol, analysis_date, timeout: [_cn_observation(
            "eastmoney",
            "https://quote.eastmoney.com/sh600519.html",
            "quote.eastmoney.com",
            em_price,
        )],
    )
    monkeypatch.setattr(
        cn, "_sina_stock_series",
        lambda symbol, analysis_date, timeout: [_cn_observation(
            "sina",
            "https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml",
            "finance.sina.com.cn",
            sina_price,
        )],
    )


def test_cn_stock_dual_upstream_price_passes(monkeypatch):
    _patch_cn_price(monkeypatch, 1700.10, 1702.30)  # dev ≈ 0.13%

    result = cn.fetch_cn(
        "贵州茅台", "600519", AS_OF,
        asset_class="cn_stock", types={"price"},
    )

    assert len(result.records) == 2
    assert result.cross_validation_passed
    domains = {record["url"].split("/")[2] for record in result.records}
    assert domains == {"quote.eastmoney.com", "finance.sina.com.cn"}
    for record in result.records:
        assert record["category"] == "market_data_price"
        assert record["source_type"] == "market_data_aggregated"
        assert "收盘价" in record["content"]
        assert matches_quote_pattern(record["content"])
        assert cn.CN_AGGREGATOR_NOTE in record["content"]


def test_cn_stock_price_deviation_fails_closed(monkeypatch):
    _patch_cn_price(monkeypatch, 1700.00, 1721.00)  # dev ≈ 1.2%

    result = cn.fetch_cn(
        "贵州茅台", "600519", AS_OF,
        asset_class="cn_stock", types={"price"},
    )

    assert result.records == []
    assert result.cross_validation_failed
    assert result.degraded


def test_cn_stock_non_price_records_format_and_weight(monkeypatch):
    flow_rows = [
        {
            "date": OBSERVED - timedelta(days=2 - index),
            "main_net": 1_000_000.0 * (index + 1),
            "xl_net": 500_000.0,
        }
        for index in range(3)
    ]
    margin_rows = [
        {
            "date": OBSERVED - timedelta(days=2 - index),
            "balance": 2.0e9 + 1e7 * index,
        }
        for index in range(3)
    ]
    monkeypatch.setattr(
        cn, "_fund_flow_series",
        lambda symbol, analysis_date, window: flow_rows,
    )
    monkeypatch.setattr(
        cn, "_margin_series",
        lambda symbol, analysis_date, window: margin_rows,
    )
    monkeypatch.setattr(
        cn, "_block_trades",
        lambda symbol, analysis_date, window: [
            {"date": OBSERVED, "amount": 56_000_000.0},
        ],
    )
    monkeypatch.setattr(
        cn, "_lhb_entries",
        lambda symbol, analysis_date, window: [
            {"date": OBSERVED, "net_buy": -12_000_000.0,
             "reason": "日涨幅偏离值达7%"},
        ],
    )

    result = cn.fetch_cn(
        "贵州茅台", "600519", AS_OF,
        asset_class="cn_stock",
        types={"flow", "positioning", "institutional"},
    )

    categories = {record["category"] for record in result.records}
    assert categories == {
        "market_data_capital_flow", "market_data_margin",
        "market_data_block_trade", "market_data_institutional_cn",
    }
    for record in result.records:
        assert record["source_type"] == "market_data_aggregated"
        assert record["quality_score"] == 0.70
        assert cn.CN_AGGREGATOR_NOTE in record["content"]
        assert not matches_quote_pattern(
            f"{record['title']}\n{record['content']}"
        )
    by_category = {
        record["category"]: record["content"]
        for record in result.records
    }
    assert "合计" in by_category["market_data_capital_flow"]
    assert "连续净流入 3 天" in by_category["market_data_capital_flow"]
    assert "环比" in by_category["market_data_margin"]
    assert "净买额合计" in by_category["market_data_institutional_cn"]


def test_cn_sector_dual_index_flow_and_etf(monkeypatch):
    monkeypatch.setattr(
        cn, "_em_sector_series",
        lambda sector, analysis_date, timeout: [_cn_observation(
            "eastmoney",
            "https://quote.eastmoney.com/center/boardlist.html#industry",
            "quote.eastmoney.com",
            2450.10,
        )],
    )
    monkeypatch.setattr(
        cn, "_ths_sector_series",
        lambda sector, analysis_date, timeout: [_cn_observation(
            "ths",
            "https://q.10jqka.com.cn/thshy/",
            "q.10jqka.com.cn",
            2453.80,
        )],
    )
    monkeypatch.setattr(
        cn, "_sector_flow_rank",
        lambda sector, indicator: (3, 86, 1.5e9),
    )
    monkeypatch.setattr(
        cn, "_sector_etf_snapshot",
        lambda sector: {
            "code": "512400",
            "name": "有色金属ETF",
            "observed_on": OBSERVED,
            "shares": 6_800_000_000.0,
        },
    )

    result = cn.fetch_cn(
        "有色金属", None, AS_OF,
        asset_class="cn_sector", types={"price", "flow"},
    )

    categories = sorted(
        record["category"] for record in result.records
    )
    assert categories == [
        "market_data_etf_flow",
        "market_data_price",
        "market_data_price",
        "market_data_sector_flow",
    ]
    assert result.cross_validation_passed
    sector_flow = next(
        record for record in result.records
        if record["category"] == "market_data_sector_flow"
    )
    assert "5日主力净流入" in sector_flow["content"]
    assert "20日主力净流入" in sector_flow["content"]
    assert "排名 3/86" in sector_flow["content"]


def test_cn_degrades_without_akshare(monkeypatch):
    def _no_akshare(symbol, analysis_date, timeout):
        raise ImportError("No module named 'akshare'")

    monkeypatch.setattr(cn, "_em_stock_series", _no_akshare)
    monkeypatch.setattr(cn, "_sina_stock_series", _no_akshare)

    result = cn.fetch_cn(
        "贵州茅台", "600519", AS_OF,
        asset_class="cn_stock", types={"price"},
    )

    assert result.records == []
    assert result.degraded
    assert all(
        failure["error_type"] == "ImportError"
        for failure in result.failures
    )


# 10. Availability fixes: date alignment, THS names, flow columns ----------

def _dated_obs(
    source: str, url: str, upstream: str, price: float, day: date,
    currency: str = "CNY",
) -> PriceObservation:
    return PriceObservation(
        source=source,
        url=url,
        price=price,
        observed_on=day,
        currency=currency,
        volume=1_000_000,
        upstream_origin=upstream,
    )


def _em_series_obs(price: float, day: date) -> PriceObservation:
    return _dated_obs(
        "eastmoney", "https://quote.eastmoney.com/sh600089.html",
        "quote.eastmoney.com", price, day,
    )


def _sina_series_obs(price: float, day: date) -> PriceObservation:
    return _dated_obs(
        "sina",
        "https://finance.sina.com.cn/realstock/company/sh600089/nc.shtml",
        "finance.sina.com.cn", price, day,
    )


def test_cn_price_alignment_uses_latest_common_trading_day(monkeypatch):
    """EastMoney serves an intraday T bar, Sina still ends at T-1: the
    pair must be validated on T-1 (their latest common trading day),
    not on the mismatched latest bars."""
    monkeypatch.setattr(
        cn, "_em_stock_series",
        lambda symbol, analysis_date, timeout: [
            _em_series_obs(23.10, OBSERVED),
            _em_series_obs(23.54, AS_OF),  # intraday, ~1.9% above T-1
        ],
    )
    monkeypatch.setattr(
        cn, "_sina_stock_series",
        lambda symbol, analysis_date, timeout: [
            _sina_series_obs(23.02, OBSERVED - timedelta(days=1)),
            _sina_series_obs(23.11, OBSERVED),
        ],
    )

    result = cn.fetch_cn(
        "特变电工", "600089", AS_OF,
        asset_class="cn_stock", types={"price"},
    )

    assert len(result.records) == 2
    assert result.cross_validation_passed
    check = result.cross_validation_passed[0]
    observed_days = {
        obs["observed_on"] for obs in check["observations"]
    }
    assert observed_days == {OBSERVED.isoformat()}
    for record in result.records:
        assert record["published_at"] == OBSERVED.isoformat()


def test_cn_price_alignment_fails_closed_without_common_day(monkeypatch):
    monkeypatch.setattr(
        cn, "_em_stock_series",
        lambda symbol, analysis_date, timeout: [
            _em_series_obs(23.54, AS_OF),
        ],
    )
    monkeypatch.setattr(
        cn, "_sina_stock_series",
        lambda symbol, analysis_date, timeout: [
            _sina_series_obs(23.02, OBSERVED - timedelta(days=1)),
        ],
    )

    result = cn.fetch_cn(
        "特变电工", "600089", AS_OF,
        asset_class="cn_stock", types={"price"},
    )

    assert result.records == []
    assert not result.cross_validation_passed
    assert any("无公共交易日" in message for message in result.degraded)


def test_equities_price_alignment_uses_latest_common_trading_day(
    monkeypatch,
):
    def _yf_obs(price: float, day: date) -> PriceObservation:
        return _dated_obs(
            "yfinance", "https://finance.yahoo.com/quote/GLD",
            "finance.yahoo.com", price, day, currency="USD",
        )

    def _sq_obs(price: float, day: date) -> PriceObservation:
        return _dated_obs(
            "stooq", "https://stooq.com/q/?s=gld",
            "stooq.com", price, day, currency="USD",
        )

    monkeypatch.setattr(
        equities, "_yfinance_series",
        lambda code, timeout, lookback_days, as_of: [
            _yf_obs(231.11, OBSERVED),
            _yf_obs(235.60, AS_OF),  # fresh bar Stooq does not have yet
        ],
    )
    monkeypatch.setattr(
        equities, "_stooq_series",
        lambda code, timeout, as_of: [
            _sq_obs(230.90, OBSERVED - timedelta(days=1)),
            _sq_obs(231.53, OBSERVED),
        ],
    )

    result = equities.fetch_equities(
        "SPDR Gold Shares", "GLD", AS_OF,
        tolerance=0.005, types={"price"},
    )

    assert len(result.records) == 2
    assert result.cross_validation_passed
    for record in result.records:
        assert record["published_at"] == OBSERVED.isoformat()


def test_equities_price_alignment_fails_closed_without_common_day(
    monkeypatch,
):
    monkeypatch.setattr(
        equities, "_yfinance_series",
        lambda code, timeout, lookback_days, as_of: [_dated_obs(
            "yfinance", "https://finance.yahoo.com/quote/GLD",
            "finance.yahoo.com", 231.11, AS_OF, currency="USD",
        )],
    )
    monkeypatch.setattr(
        equities, "_stooq_series",
        lambda code, timeout, as_of: [_dated_obs(
            "stooq", "https://stooq.com/q/?s=gld",
            "stooq.com", 231.53, OBSERVED, currency="USD",
        )],
    )

    result = equities.fetch_equities(
        "SPDR Gold Shares", "GLD", AS_OF,
        tolerance=0.005, types={"price"},
    )

    assert result.records == []
    assert not result.cross_validation_passed
    assert any("无公共交易日" in message for message in result.degraded)


def test_ths_sector_name_exact_match(monkeypatch):
    monkeypatch.setattr(
        cn, "_ths_sector_names",
        lambda: ["贵金属", "有色金属", "工业金属"],
    )

    assert cn._ths_match_sector("有色金属") == "有色金属"


def test_ths_sector_name_unique_fuzzy_match(monkeypatch):
    monkeypatch.setattr(
        cn, "_ths_sector_names",
        lambda: ["贵金属", "有色金属行业", "能源金属"],
    )

    assert cn._ths_match_sector("有色金属") == "有色金属行业"


def test_ths_sector_name_ambiguous_or_missing_match_fails(monkeypatch):
    monkeypatch.setattr(
        cn, "_ths_sector_names",
        lambda: ["有色金属行业", "有色金属材料"],
    )
    with pytest.raises(ValueError) as ambiguous:
        cn._ths_match_sector("有色金属")
    assert "有色金属行业" in str(ambiguous.value)
    assert "有色金属材料" in str(ambiguous.value)

    monkeypatch.setattr(
        cn, "_ths_sector_names",
        lambda: ["贵金属", "工业金属"],
    )
    with pytest.raises(ValueError) as missing:
        cn._ths_match_sector("有色金属")
    assert "无相近候选" in str(missing.value)


def test_ths_mismatch_degrades_dual_source_without_records(monkeypatch):
    """A THS taxonomy miss must surface as a structured failure with
    candidates and fail-closed — never a raw KeyError, never a record
    from a guessed board."""
    monkeypatch.setattr(
        cn, "_em_sector_series",
        lambda sector, analysis_date, timeout: [_cn_observation(
            "eastmoney",
            "https://quote.eastmoney.com/center/boardlist.html#industry",
            "quote.eastmoney.com",
            2450.10,
        )],
    )
    monkeypatch.setattr(
        cn, "_ths_sector_names",
        lambda: ["贵金属", "工业金属", "小金属", "能源金属"],
    )

    result = cn.fetch_cn(
        "有色金属", None, AS_OF,
        asset_class="cn_sector", types={"price"},
    )

    assert result.records == []
    assert result.degraded
    ths_failure = next(
        failure for failure in result.failures
        if failure["item"] == "ths_close"
    )
    assert "东财侧" in ths_failure["message"]


def test_sector_flow_rank_column_layout_compat(monkeypatch):
    """Both observed akshare column layouts must resolve the net inflow."""
    pandas = pytest.importorskip("pandas")

    def _frame(net_column: str):
        return pandas.DataFrame([
            {"序号": 1, "名称": "半导体", net_column: 9.9e8},
            {"序号": 3, "名称": "有色金属", net_column: 1.5e9},
        ])

    monkeypatch.setattr(
        cn, "_sector_flow_frame",
        lambda indicator: _frame(f"{indicator}主力净流入-净额"),
    )
    assert cn._sector_flow_rank("有色金属", "5日") == (3, 2, 1.5e9)

    monkeypatch.setattr(
        cn, "_sector_flow_frame",
        lambda indicator: _frame(f"{indicator}主力净流入"),
    )
    assert cn._sector_flow_rank("有色金属", "5日") == (3, 2, 1.5e9)


def test_sector_flow_missing_window_is_annotated_not_fatal(monkeypatch):
    """akshare's flow ranking dropped the 20日 window: the record must
    still ship the available windows and annotate the missing one."""
    def _rank(sector, indicator):
        if indicator == "20日":
            raise KeyError("20日")
        return (3, 86, 1.5e9)

    monkeypatch.setattr(cn, "_sector_flow_rank", _rank)

    result = ProviderResult()
    cn._sector_flow_record(result, "有色金属", "有色金属", AS_OF)

    assert len(result.records) == 1
    content = result.records[0]["content"]
    assert "5日主力净流入" in content
    assert "排名 3/86" in content
    assert "20日窗口数据不可用" in content


def test_sector_flow_all_windows_missing_raises(monkeypatch):
    def _rank(sector, indicator):
        raise KeyError(indicator)

    monkeypatch.setattr(cn, "_sector_flow_rank", _rank)

    result = ProviderResult()
    with pytest.raises(ValueError):
        cn._sector_flow_record(result, "有色金属", "有色金属", AS_OF)
    assert result.records == []


# 11. Review fixes: ok semantics, same-day guard, cn_sector routing --------

def test_fetch_market_data_cli_exits_nonzero_when_all_records_future(
    tmp_path, monkeypatch, capsys
):
    """All records rejected as future-dated: ok must be false and the
    CLI must exit 1 so the host falls back to the search path."""
    import sys

    from structflow.main import main

    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")
    request = _initialize(tmp_path)
    fake = _macro_result(request.analysis_date + timedelta(days=5))
    monkeypatch.setattr(
        skill_runtime, "collect_market_data", lambda **kwargs: fake
    )
    monkeypatch.setattr(sys, "argv", [
        "structflow", "--root", str(tmp_path),
        "fetch-market-data", "黄金", "--asset-class", "commodity",
    ])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["rejected_future_records"] == 1
    assert payload["added_unique_sources"] == 0


def test_cn_same_day_latest_divergence_fails_closed(monkeypatch):
    """Both upstreams end on the same trading day with prices beyond
    tolerance: a genuine disagreement — must not be softened by
    falling back to an earlier common day that would pass."""
    monkeypatch.setattr(
        cn, "_em_stock_series",
        lambda symbol, analysis_date, timeout: [
            _em_series_obs(23.10, OBSERVED - timedelta(days=1)),
            _em_series_obs(24.00, OBSERVED),
        ],
    )
    monkeypatch.setattr(
        cn, "_sina_stock_series",
        lambda symbol, analysis_date, timeout: [
            _sina_series_obs(23.11, OBSERVED - timedelta(days=1)),
            _sina_series_obs(23.50, OBSERVED),  # ~2.1% below EastMoney
        ],
    )

    result = cn.fetch_cn(
        "特变电工", "600089", AS_OF,
        asset_class="cn_stock", types={"price"},
    )

    assert result.records == []
    assert result.cross_validation_failed
    assert any(
        "最新交易日双源价差超限" in message for message in result.degraded
    )


def test_equities_same_day_latest_divergence_fails_closed(monkeypatch):
    monkeypatch.setattr(
        equities, "_yfinance_series",
        lambda code, timeout, lookback_days, as_of: [
            _dated_obs(
                "yfinance", "https://finance.yahoo.com/quote/GLD",
                "finance.yahoo.com", 231.11,
                OBSERVED - timedelta(days=1), currency="USD",
            ),
            _dated_obs(
                "yfinance", "https://finance.yahoo.com/quote/GLD",
                "finance.yahoo.com", 236.00, OBSERVED, currency="USD",
            ),
        ],
    )
    monkeypatch.setattr(
        equities, "_stooq_series",
        lambda code, timeout, as_of: [
            _dated_obs(
                "stooq", "https://stooq.com/q/?s=gld",
                "stooq.com", 231.53,
                OBSERVED - timedelta(days=1), currency="USD",
            ),
            _dated_obs(
                "stooq", "https://stooq.com/q/?s=gld",
                "stooq.com", 231.60, OBSERVED, currency="USD",
            ),
        ],
    )

    result = equities.fetch_equities(
        "SPDR Gold Shares", "GLD", AS_OF,
        tolerance=0.005, types={"price"},
    )

    assert result.records == []
    assert result.cross_validation_failed
    assert any(
        "最新交易日双源价差超限" in message for message in result.degraded
    )


def test_router_routes_cn_sector_with_types(monkeypatch):
    sentinel = ProviderResult(
        records=[{"category": "market_data_sector_flow"}]
    )
    captured: dict = {}

    def _fake_fetch_cn(subject, code, analysis_date, **kwargs):
        captured.update(
            subject=subject, code=code,
            analysis_date=analysis_date, **kwargs,
        )
        return sentinel

    monkeypatch.setattr(cn, "fetch_cn", _fake_fetch_cn)

    result = collect_market_data(
        subject="有色金属",
        asset_class="cn_sector",
        code=None,
        types={"price", "flow"},
        analysis_date=AS_OF,
        tolerance=0.004,
    )

    assert result.records == sentinel.records
    assert captured["subject"] == "有色金属"
    assert captured["code"] is None
    assert captured["analysis_date"] == AS_OF
    assert captured["asset_class"] == "cn_sector"
    assert captured["types"] == {"price", "flow"}
    assert captured["tolerance"] == 0.004
    assert not result.failures


def test_stooq_series_filters_observations_after_as_of(monkeypatch):
    csv_payload = (
        "Date,Open,High,Low,Close,Volume\n"
        "2026-07-24,228.10,230.00,227.90,229.40,1100000\n"
        "2026-07-27,229.00,232.00,228.50,231.53,1200000\n"
        "2026-07-29,231.00,234.00,230.50,233.10,1300000\n"
    )

    def _fake_get(url, params=None, timeout=None):
        return _FakeCsvResponse(csv_payload)

    monkeypatch.setattr("requests.get", _fake_get)

    observations = equities._stooq_series(
        "GLD", timeout=5.0, as_of=date(2026, 7, 28)
    )

    assert [obs.observed_on for obs in observations] == [
        date(2026, 7, 24), date(2026, 7, 27),
    ]


# 12. DBnomics global macro anchors (keyless REST) --------------------------

class _FakeJsonResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def _dbnomics_payload(
    days: list[str], values: list, freq: str = "daily"
) -> dict:
    """Mirror of the live api.db.nomics.world/v22 response structure
    (curl-verified 2026-07: top-level _meta/errors/series, docs with
    period, period_start_day, value, series_name, @frequency)."""
    return {
        "_meta": {"version": "22.1.17"},
        "errors": None,
        "series": {
            "docs": [{
                "@frequency": freq,
                "dataset_code": "FM",
                "dataset_name": "Financial market data",
                "provider_code": "ECB",
                "series_code": "D.U2.EUR.4F.KR.MRR_FR.LEV",
                "series_name": (
                    "Daily – Euro area – ECB – Key interest rate – "
                    "Main refinancing operations – Level"
                ),
                "period": days,
                "period_start_day": days,
                "value": values,
            }],
            "limit": 1000, "num_found": 1, "offset": 0,
        },
    }


_ECB_SERIES = ((
    "ECB/FM/D.U2.EUR.4F.KR.MRR_FR.LEV",
    "欧央行主要再融资利率", "%", "ECB",
),)


def test_dbnomics_parses_live_response_structure(monkeypatch):
    requested: list[str] = []

    def _fake_get(url, params=None, timeout=None):
        requested.append(url)
        return _FakeJsonResponse(_dbnomics_payload(
            ["2026-07-24", "2026-07-27"], [2.15, 2.4],
        ))

    monkeypatch.setattr("requests.get", _fake_get)

    result = dbnomics.fetch_dbnomics("黄金", AS_OF, series=_ECB_SERIES)

    assert requested == [
        "https://api.db.nomics.world/v22/series/"
        "ECB/FM/D.U2.EUR.4F.KR.MRR_FR.LEV"
    ]
    assert len(result.records) == 1
    record = result.records[0]
    assert record["category"] == "market_data_macro"
    assert record["provider"] == "market_data_dbnomics"
    assert record["source_type"] == "market_data_official"
    assert record["quality_score"] == 0.92
    assert record["published_at"] == "2026-07-27"
    assert record["upstream_origin"] == "ECB via api.db.nomics.world"
    assert "读数 2.4%" in record["content"]
    assert "[数据滞后1天]" in record["content"]
    assert "DBnomics" in record["content"]
    assert not matches_quote_pattern(
        f"{record['title']}\n{record['content']}"
    )
    assert not result.degraded


def test_dbnomics_drops_future_observations_and_na_values(monkeypatch):
    future = (AS_OF + timedelta(days=2)).isoformat()
    monkeypatch.setattr(
        dbnomics, "_series_doc",
        lambda series_id, timeout: _dbnomics_payload(
            ["2026-07-24", "2026-07-27", future],
            [2.15, "NA", 9.99],
        )["series"]["docs"][0],
    )

    result = dbnomics.fetch_dbnomics("黄金", AS_OF, series=_ECB_SERIES)

    # The future bar and the NA placeholder are dropped; the record
    # falls back to the newest valid observation at or before AS_OF.
    assert len(result.records) == 1
    assert result.records[0]["published_at"] == "2026-07-24"
    assert "读数 2.15%" in result.records[0]["content"]


def test_dbnomics_all_observations_future_fails_closed(monkeypatch):
    future = (AS_OF + timedelta(days=2)).isoformat()
    monkeypatch.setattr(
        dbnomics, "_series_doc",
        lambda series_id, timeout: _dbnomics_payload(
            [future], [9.99],
        )["series"]["docs"][0],
    )

    result = dbnomics.fetch_dbnomics("黄金", AS_OF, series=_ECB_SERIES)

    assert result.records == []
    assert result.degraded
    assert result.failures[0]["error_type"] == "ValueError"


def test_dbnomics_degrades_per_series_on_network_failure(monkeypatch):
    def _broken(series_id, timeout):
        raise ConnectionError("api.db.nomics.world unreachable")

    monkeypatch.setattr(dbnomics, "_series_doc", _broken)

    result = dbnomics.fetch_dbnomics("黄金", AS_OF)

    assert result.records == []
    assert len(result.failures) == len(dbnomics.DEFAULT_SERIES)
    assert all(
        failure["error_type"] == "ConnectionError"
        for failure in result.failures
    )
    assert result.degraded


def test_dbnomics_custom_series_code_is_fetched_instrument_code_ignored(
    monkeypatch,
):
    fetched: list[str] = []

    def _fake_doc(series_id, timeout):
        fetched.append(series_id)
        doc = _dbnomics_payload(["2026-07-27"], [3.5])["series"]["docs"][0]
        doc["series_name"] = "IMF test series"
        return doc

    monkeypatch.setattr(dbnomics, "_series_doc", _fake_doc)

    custom = dbnomics.fetch_dbnomics(
        "黄金", AS_OF, code="IMF/IFS/M.US.PCPI_IX", series=_ECB_SERIES,
    )
    assert fetched == [
        "ECB/FM/D.U2.EUR.4F.KR.MRR_FR.LEV", "IMF/IFS/M.US.PCPI_IX",
    ]
    assert len(custom.records) == 2
    # A custom series ID without a curated label uses the upstream name.
    assert "IMF test series" in custom.records[1]["title"]

    fetched.clear()
    instrument = dbnomics.fetch_dbnomics(
        "黄金", AS_OF, code="GLD", series=_ECB_SERIES,
    )
    assert fetched == ["ECB/FM/D.U2.EUR.4F.KR.MRR_FR.LEV"]
    assert len(instrument.records) == 1
    assert not dbnomics.is_series_id("ETH/USDT")


# 13. EIA weekly energy inventories (Tier 1, key-gated) ---------------------

def _eia_rows(count: int = 54) -> list[dict]:
    """Descending weekly rows in the documented v2 response shape;
    keyless calls were live-verified to fail with API_KEY_MISSING."""
    rows = []
    for week in range(count):
        period = AS_OF - timedelta(days=4 + 7 * week)
        rows.append({
            "period": period.isoformat(),
            "series": "WCESTUS1",
            "value": 420_000 + 1_000 * week,  # older weeks are higher
            "units": "MBBL",
        })
    return rows


_CRUDE_SERIES = ((
    "petroleum/stoc/wstk", "WCESTUS1",
    "美国商业原油库存(EIA周度)", "千桶",
),)


def test_eia_requires_key_and_degrades():
    result = eia.fetch_eia("原油", AS_OF, api_key="")

    assert result.records == []
    assert result.degraded
    assert result.failures[0]["item"] == "api_key"


def test_eia_derives_wow_delta_and_one_year_percentile(monkeypatch):
    monkeypatch.setattr(
        eia, "_series_rows",
        lambda route, series_id, api_key, timeout: _eia_rows(),
    )

    result = eia.fetch_eia(
        "原油", AS_OF, api_key="test-key", series=_CRUDE_SERIES,
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["category"] == "market_data_inventory"
    assert record["provider"] == "market_data_eia"
    assert record["source_type"] == "exchange_official"
    assert record["quality_score"] == 0.93
    assert record["published_at"] == (
        AS_OF - timedelta(days=4)
    ).isoformat()
    content = record["content"]
    assert "[数据滞后4天]" in content
    assert "库存读数 420,000千桶" in content
    assert "环比上周 -1,000千桶（-0.24%）" in content
    # Latest week is the lowest of the trailing year: bottom percentile.
    assert "近一年百分位 2%（样本 52 周）" in content
    assert eia.EIA_LAG_NOTE in content
    assert not matches_quote_pattern(
        f"{record['title']}\n{content}"
    )


def test_eia_drops_future_report_weeks(monkeypatch):
    rows = _eia_rows(12)
    rows.insert(0, {
        "period": (AS_OF + timedelta(days=3)).isoformat(),
        "series": "WCESTUS1",
        "value": 999_999,
        "units": "MBBL",
    })
    monkeypatch.setattr(
        eia, "_series_rows",
        lambda route, series_id, api_key, timeout: rows,
    )

    result = eia.fetch_eia(
        "原油", AS_OF, api_key="test-key", series=_CRUDE_SERIES,
    )

    assert len(result.records) == 1
    assert result.records[0]["published_at"] == (
        AS_OF - timedelta(days=4)
    ).isoformat()
    assert "999,999" not in result.records[0]["content"]


def test_eia_degrades_per_series_on_network_failure(monkeypatch):
    def _broken(route, series_id, api_key, timeout):
        raise ConnectionError("api.eia.gov unreachable")

    monkeypatch.setattr(eia, "_series_rows", _broken)

    result = eia.fetch_eia("原油", AS_OF, api_key="test-key")

    assert result.records == []
    assert len(result.failures) == len(eia.DEFAULT_SERIES)
    assert all(
        failure["error_type"] == "ConnectionError"
        for failure in result.failures
    )
    assert result.degraded


def test_eia_error_payload_surfaces_as_value_error(monkeypatch):
    """A 200-class response without `response` (live-verified error
    shape: {"error": {"code": ..., "message": ...}}) must raise."""
    monkeypatch.setattr(
        "requests.get",
        lambda url, params=None, timeout=None: _FakeJsonResponse({
            "error": {
                "code": "API_KEY_INVALID",
                "message": "The API key is invalid.",
            },
        }),
    )

    with pytest.raises(ValueError) as excinfo:
        eia._series_rows(
            "petroleum/stoc/wstk", "WCESTUS1", "bad-key", 5.0
        )
    assert "API_KEY_INVALID" in str(excinfo.value)


# 14. Routing and CLI for the new providers ---------------------------------

def test_router_routes_inventory_to_eia_for_commodity(monkeypatch):
    sentinel = ProviderResult(
        records=[{"category": "market_data_inventory"}]
    )
    captured: dict = {}

    def _fake_fetch_eia(subject, analysis_date, **kwargs):
        captured.update(
            subject=subject, analysis_date=analysis_date, **kwargs
        )
        return sentinel

    monkeypatch.setattr(eia, "fetch_eia", _fake_fetch_eia)

    result = collect_market_data(
        subject="原油",
        asset_class="commodity",
        types={"inventory"},
        analysis_date=AS_OF,
        eia_api_key="test-key",
    )

    assert result.records == sentinel.records
    assert captured["api_key"] == "test-key"
    assert not result.failures

    # Inventory is commodity-only: equity must not call EIA.
    called: list[str] = []
    monkeypatch.setattr(
        eia, "fetch_eia",
        lambda *args, **kwargs: called.append("eia") or sentinel,
    )
    equity_result = collect_market_data(
        subject="GLD",
        asset_class="equity",
        types={"inventory"},
        analysis_date=AS_OF,
    )
    assert called == []
    assert equity_result.records == []


def test_router_macro_tries_fred_and_dbnomics_independently(monkeypatch):
    fred_result = ProviderResult(
        degraded=["fred: FRED_API_KEY 缺失，宏观锚数据跳过"],
        failures=[{"provider": "fred", "item": "api_key",
                   "error_type": "ProviderError", "message": "missing"}],
    )
    dbn_result = ProviderResult(
        records=[{"category": "market_data_macro"}]
    )
    captured: dict = {}

    def _fake_dbnomics(subject, analysis_date, **kwargs):
        captured.update(**kwargs)
        return dbn_result

    monkeypatch.setattr(
        fred, "fetch_fred",
        lambda subject, analysis_date, **kwargs: fred_result,
    )
    monkeypatch.setattr(dbnomics, "fetch_dbnomics", _fake_dbnomics)

    result = collect_market_data(
        subject="黄金",
        asset_class="commodity",
        code="IMF/IFS/M.US.PCPI_IX",
        types={"macro"},
        analysis_date=AS_OF,
    )

    # FRED degraded, DBnomics still delivered — independent fallback.
    assert result.records == dbn_result.records
    assert result.degraded == fred_result.degraded
    assert captured["code"] == "IMF/IFS/M.US.PCPI_IX"


def test_cli_types_enum_includes_inventory():
    from structflow.market_data import DATA_TYPES

    assert "inventory" in DATA_TYPES
    args = build_parser().parse_args([
        "fetch-market-data", "原油",
        "--asset-class", "commodity",
        "--types", "inventory", "macro",
    ])
    assert args.types == ["inventory", "macro"]


# 15. Review minors: errors surfacing, month fallback, natgas, switch ------

def test_dbnomics_top_level_errors_surface_upstream_message(monkeypatch):
    """HTTP 200 with a populated top-level errors list must raise a
    ValueError naming the upstream code, and degrade through fetch."""
    monkeypatch.setattr(
        "requests.get",
        lambda url, params=None, timeout=None: _FakeJsonResponse({
            "_meta": {"version": "22.1.17"},
            "errors": [{
                "code": "SeriesNotFound",
                "message": "Series BIS/WS_CBPOL_D/D.US could not be found",
            }],
            "series": {"docs": [], "limit": 1000,
                       "num_found": 0, "offset": 0},
        }),
    )

    with pytest.raises(ValueError) as excinfo:
        dbnomics._series_doc("BIS/WS_CBPOL_D/D.US", 5.0)
    assert "DBnomics error SeriesNotFound" in str(excinfo.value)
    assert "could not be found" in str(excinfo.value)

    result = dbnomics.fetch_dbnomics("黄金", AS_OF, series=_ECB_SERIES)
    assert result.records == []
    assert result.degraded
    assert "SeriesNotFound" in result.failures[0]["message"]


def test_dbnomics_month_only_periods_fall_back_to_first_of_month(
    monkeypatch,
):
    future_month = f"{AS_OF.year}-{AS_OF.month + 2:02d}"
    doc = _dbnomics_payload(
        ["2026-06", "2026-07", future_month], [2.0, 2.1, 9.9],
        freq="monthly",
    )["series"]["docs"][0]
    del doc["period_start_day"]  # only bare YYYY-MM periods remain
    monkeypatch.setattr(
        dbnomics, "_series_doc", lambda series_id, timeout: doc,
    )

    result = dbnomics.fetch_dbnomics("黄金", AS_OF, series=_ECB_SERIES)

    # The future month resolves to its first day and is filtered; the
    # newest in-window month lands on the first of that month.
    assert len(result.records) == 1
    assert result.records[0]["published_at"] == "2026-07-01"
    assert "读数 2.1%" in result.records[0]["content"]
    # Anything that is neither ISO nor YYYY-MM stays a hard error.
    with pytest.raises(ValueError):
        dbnomics._coerce_period_date("2026Q3")


def test_eia_natgas_inventory_success_path(monkeypatch):
    natgas_series = ((
        "natural-gas/stor/wkly", "NW2_EPG0_SWO_R48_BCF",
        "美国Lower48天然气工作库存(EIA周度)", "十亿立方英尺",
    ),)

    def _natgas_rows(route, series_id, api_key, timeout):
        assert route == "natural-gas/stor/wkly"
        assert series_id == "NW2_EPG0_SWO_R48_BCF"
        rows = []
        for week in range(54):
            period = AS_OF - timedelta(days=4 + 7 * week)
            rows.append({
                "period": period.isoformat(),
                "series": series_id,
                "value": 3_000 - 10 * week,  # older weeks are lower
                "units": "BCF",
            })
        return rows

    monkeypatch.setattr(eia, "_series_rows", _natgas_rows)

    result = eia.fetch_eia(
        "天然气", AS_OF, api_key="test-key", series=natgas_series,
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["category"] == "market_data_inventory"
    assert record["provider"] == "market_data_eia"
    assert record["source_type"] == "exchange_official"
    assert record["quality_score"] == 0.93
    content = record["content"]
    assert "[数据滞后4天]" in content
    assert "库存读数 3,000十亿立方英尺" in content
    assert "环比上周 +10十亿立方英尺（+0.33%）" in content
    # Latest week is the highest of the trailing year: top percentile.
    assert "近一年百分位 100%（样本 52 周）" in content
    assert eia.EIA_LAG_NOTE in content
    assert not matches_quote_pattern(f"{record['title']}\n{content}")


def test_router_macro_skips_dbnomics_when_disabled(monkeypatch):
    fred_result = ProviderResult(
        records=[{"category": "market_data_macro"}]
    )
    called: list[str] = []
    monkeypatch.setattr(
        fred, "fetch_fred",
        lambda subject, analysis_date, **kwargs: (
            called.append("fred") or fred_result
        ),
    )
    monkeypatch.setattr(
        dbnomics, "fetch_dbnomics",
        lambda subject, analysis_date, **kwargs: (
            called.append("dbnomics") or ProviderResult()
        ),
    )

    result = collect_market_data(
        subject="黄金",
        asset_class="commodity",
        types={"macro"},
        analysis_date=AS_OF,
        enable_dbnomics=False,
    )

    assert called == ["fred"]
    assert result.records == fred_result.records
    assert not result.failures
