from datetime import datetime, timezone

from structflow.data_collector import DataCollector
from structflow.evidence import (
    EvidenceRecord,
    EvidenceStore,
    infer_source_type,
)
from structflow.input_resolver import (
    EntityProfile,
    InputKind,
    MarketSnapshot,
    MaterialSegment,
    resolve_market_snapshot,
)
from structflow.models import (
    AlphaEngine,
    Driver,
    DriverSpace,
    GateResult,
    MetaSystemDefinition,
    RegimeEngine,
    RegimeTransition,
    VariableMapping,
)
from structflow.research_gates import ResearchValidator
from structflow.retry_guard import RetryGuard


def _alpha(text: str, price_text: str = "") -> AlphaEngine:
    return AlphaEngine(
        consensus_view="市场存在分歧",
        structural_view=f"{text} {price_text}".strip(),
        mispricing="定价尚未反映现金流风险",
        alpha_signal="条件性正向结构信号，失效条件明确",
        direction="long",
        confidence=0.6,
        supporting_evidence_ids=["src_current", "src_filing"],
        contradicting_evidence_ids=["src_counter"],
    )


def _profile() -> EntityProfile:
    return EntityProfile(
        input_kind=InputKind.COMPANY,
        canonical_name="特变电工股份有限公司",
        ticker="600089",
        jurisdiction="中国",
        latest_reporting_period="2026Q1",
        material_segments=[
            MaterialSegment(
                name="电气设备产品",
                revenue_share=0.28,
                materiality_reason="主要收入来源",
                evidence_ids=["src_filing"],
            ),
            MaterialSegment(
                name="煤炭产品",
                revenue_share=0.17,
                materiality_reason="主要利润来源",
                evidence_ids=["src_filing"],
            ),
        ],
        required_system_dimensions=[
            "电气设备", "煤炭", "资本开支与融资"
        ],
        financial_quality_flags=[
            "归母利润包含大额公允价值收益",
            "扣非利润与归母利润方向不同",
        ],
        market_snapshot=MarketSnapshot(
            price=20.05,
            currency="CNY",
            as_of="2026-07-08",
            source_id="src_current",
            stale_days=2,
            confidence=0.8,
        ),
    )


def test_anysearch_results_are_split_and_dated():
    collector = object.__new__(DataCollector)
    raw = """
## Search Results (2 results)

### 1. 特变电工股份有限公司2026年第一季度报告
- **URL**: https://static.cninfo.com.cn/report.pdf
- Published: 2026-04-30T08:00:00+08:00 公司代码：600089

### 2. 特变电工7月8日收盘
- **URL**: https://example.com/price
- Published: 2026-07-08T15:10:00+08:00 报20.05元/股
"""
    records = collector._evidence_from_anysearch(
        raw, "market_data_price", "current price"
    )
    assert len(records) == 2
    assert records[0].source_type == "company_filing"
    assert records[1].published_at.startswith("2026-07-08")


def test_source_classifier_demotes_community_content():
    assert infer_source_type(
        "https://caifuhao.eastmoney.com/news/1",
        "估值研究",
        "建议买入",
    ) == "social"


def test_market_snapshot_prefers_dated_observation():
    store = EvidenceStore()
    store.add(EvidenceRecord(
        category="market_data_price",
        provider="tavily",
        query="price",
        title="Trading page",
        url="https://example.com/live",
        content="当前价格为22.01 CNY",
        quality_score=0.8,
        relevance_score=0.9,
        freshness_score=0.25,
    ))
    store.add(EvidenceRecord(
        category="contradiction_downside",
        provider="anysearch",
        query="downside",
        title="特变电工7月8日收盘",
        url="https://example.com/20260708",
        content="2026年7月8日，截至发稿，报20.05元/股",
        published_at="2026-07-08",
        quality_score=0.6,
        relevance_score=0.6,
        freshness_score=1.0,
    ))
    snapshot = resolve_market_snapshot(
        store,
        now=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    assert snapshot is not None
    assert snapshot.price == 20.05
    assert snapshot.as_of == "2026-07-08"


def test_material_segment_gate_rejects_narrow_l0():
    meta = MetaSystemDefinition(
        system_type="制造业供应链系统",
        core_function="制造输变电设备",
        system_boundary="包括变压器制造和交付",
        failure_mode="原材料上涨导致设备利润下降",
    )
    result = ResearchValidator().validate_material_segment_coverage(
        meta, _profile()
    )
    assert result.passed is False
    assert "煤炭产品" in result.reason


def test_variable_and_driver_gates_reject_missing_material_segments():
    variables = VariableMapping(
        state_variables=["输变电设备产能"],
        flow_variables=["变压器订单"],
        control_variables=["电网投资强度"],
        latent_variables=["设备需求预期"],
    )
    drivers = DriverSpace(
        drivers=[
            Driver(
                name="电网资本开支",
                category="structural",
                maps_to_variable="FV",
                direction="+",
                elasticity=0.8,
                volatility=0.3,
                lag="mid",
                regime_dependency=0.4,
            )
        ]
    )
    validator = ResearchValidator()

    assert validator.validate_variable_segment_coverage(
        variables, _profile()
    ).passed is False
    assert validator.validate_driver_segment_coverage(
        drivers, _profile()
    ).passed is False


def test_temporal_gate_rejects_wrong_current_price():
    result = ResearchValidator().validate_temporal_grounding(
        _alpha("利润质量需要验证", "当前股价22.01元"),
        _profile(),
    )
    assert result.passed is False
    assert "22.01" in result.reason


def test_advice_gate_rejects_target_and_recommendation():
    alpha = _alpha("建议做多，目标价33.31元")
    result = ResearchValidator().validate_advice_boundary(alpha)
    assert result.passed is False


def test_financial_quality_gate_requires_adjusted_or_cash_view():
    result = ResearchValidator().validate_financial_quality(
        _alpha("归母净利润同比增长"),
        _profile(),
    )
    assert result.passed is False


def test_contraction_long_requires_reconciliation():
    regime = RegimeEngine(
        current_regime="transition",
        confidence=0.7,
        transition_probability=RegimeTransition(
            next_regime="contraction",
            probability=0.5,
        ),
    )
    result = (
        ResearchValidator()
        .validate_regime_alpha_reconciliation(
            regime,
            _alpha("设备需求增长"),
        )
    )
    assert result.passed is False


def test_hard_gate_always_triggers_retry():
    guard = RetryGuard(max_retries=1, min_pass_rate=0.75)
    gates = [
        GateResult(gate_name="Shape", passed=True, reason="ok"),
        GateResult(
            gate_name="Hard_TemporalGrounding",
            passed=False,
            reason="stale",
        ),
        GateResult(gate_name="Schema", passed=True, reason="ok"),
        GateResult(gate_name="Binding", passed=True, reason="ok"),
    ]
    assert guard.should_retry(gates) is True
