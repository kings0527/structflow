from datetime import date

from structflow.coverage_contract import CoverageValidator
from structflow.evidence import EvidenceRecord, EvidenceStore, infer_source_type
from structflow.financial_consistency import FinancialConsistencyValidator
from structflow.input_resolver import (
    EntityProfile,
    FinancialFact,
    InputKind,
    MarketSnapshot,
    MaterialSegment,
)
from structflow.investment_validation import InvestmentValidator
from structflow.market_snapshot import resolve_consensus_market_snapshot
from structflow.models import (
    AlphaEngine,
    AssetMapping,
    Driver,
    InvestmentMapping,
    MetaSystemDefinition,
    VariableMapping,
)
from structflow.temporal_grounding import TemporalGroundingValidator


def _record(
    source_id_seed: str,
    title: str,
    url: str,
    content: str = "",
    published_at: str | None = "2030-01-10",
) -> EvidenceRecord:
    return EvidenceRecord(
        category="market_data_price",
        provider="fixture",
        query=source_id_seed,
        title=title,
        url=url,
        content=content,
        published_at=published_at,
        source_type="news",
        relevance_score=0.9,
        quality_score=0.8,
        freshness_score=0.9,
    )


def _profile() -> EntityProfile:
    return EntityProfile(
        input_kind=InputKind.COMPANY,
        canonical_name="示例能源股份有限公司",
        ticker="123456.XY",
        jurisdiction="XY",
        latest_reporting_period="2029全年",
        material_segments=[
            MaterialSegment(
                name="动力设备",
                revenue_share=0.6,
                materiality_reason="主要收入来源",
                evidence_ids=["src_filing"],
            ),
            MaterialSegment(
                name="资源服务",
                revenue_share=0.4,
                materiality_reason="第二收入来源",
                evidence_ids=["src_filing"],
            ),
        ],
        required_system_dimensions=["原料价格", "资本开支周期"],
        evidence_ids=["src_filing"],
    )


def _alpha(**updates) -> AlphaEngine:
    values = {
        "consensus_view": "市场预期需求改善",
        "structural_view": "现金流与订单仍需确认",
        "mispricing": "市场可能低估资产负债表约束",
        "alpha_signal": "条件性中性信号，等待可验证触发条件",
        "direction": "neutral",
        "confidence": 0.5,
    }
    values.update(updates)
    return AlphaEngine(**values)


def test_evidence_store_rejects_impossible_future_observations():
    store = EvidenceStore(analysis_date=date(2030, 1, 10))
    store.add(_record("past", "示例能源 123456 新闻", "https://a.example/past"))
    store.add(
        _record(
            "future",
            "示例能源 123456 未来新闻",
            "https://b.example/future",
            published_at="2030-01-11",
        )
    )

    assert store.unique_source_count == 1
    assert store.records()[0].query == "past"


def test_consensus_quote_ignores_ai_outlier_and_requires_independent_domains():
    records = [
        _record(
            "quote-a",
            "示例能源 123456 2030-01-10 收盘价42.00元",
            "https://quotes-a.example/123456",
        ),
        _record(
            "quote-b",
            "示例能源 123456 2030-01-10 最新价42.20元",
            "https://quotes-b.example/123456",
        ),
        _record(
            "ai-outlier",
            "示例能源 123456 2030-01-10 Close: CNY 420.00",
            "https://generated.example/report",
            content="AI-powered multi-agent stock analysis; LLM Model demo",
        ),
    ]

    snapshot = resolve_consensus_market_snapshot(
        records, _profile(), "2030-01-11"
    )

    assert snapshot is not None
    assert snapshot.price == 42.1
    assert len(snapshot.source_ids) == 2


def test_single_quote_cannot_create_consensus_snapshot():
    snapshot = resolve_consensus_market_snapshot(
        [
            _record(
                "single",
                "示例能源 123456 2030-01-10 收盘价42.00元",
                "https://quotes.example/123456",
            )
        ],
        _profile(),
        "2030-01-11",
    )
    assert snapshot is None


def test_generated_research_is_demoted_without_domain_hardcoding():
    assert infer_source_type(
        "https://unknown.example/report",
        "Daily report",
        "AI-powered analysis, LLM Model x, TRADE DECISION SELL",
    ) == "ai_generated"


def test_coverage_uses_binding_ids_not_company_specific_text():
    profile = _profile()
    meta = MetaSystemDefinition(
        system_type="综合基础设施系统",
        core_function="提供设备与资源服务",
        system_boundary="覆盖全部重大经营活动和外部约束",
        failure_mode="现金流约束导致投资收缩",
        covered_segment_ids=["SEG-001", "SEG-002"],
        covered_dimension_ids=["DIM-001", "DIM-002"],
    )
    variables = VariableMapping(
        state_variables=["设备产能", "资源储量", "资本存量"],
        flow_variables=["订单流", "销售流", "现金流"],
        control_variables=["采购价格", "投资强度", "信用条件"],
        latent_variables=["需求预期", "风险偏好", "政策预期"],
        covered_segment_ids=["SEG-001", "SEG-002"],
        covered_dimension_ids=["DIM-001", "DIM-002"],
    )
    validator = CoverageValidator()

    assert validator.validate_l0(meta, profile).passed
    assert validator.validate_l1(variables, profile).passed
    assert not validator.validate_l1(
        variables.model_copy(update={"covered_dimension_ids": ["DIM-001"]}),
        profile,
    ).passed


def test_driver_localized_enums_are_normalized_at_schema_boundary():
    driver = Driver(
        name="需求变化",
        category="宏观",
        maps_to_variable="FV",
        direction="正向",
        elasticity=0.5,
        volatility=0.4,
        lag="mid",
        regime_dependency=0.3,
    )
    assert driver.category == "macro"
    assert driver.direction == "+"


def test_price_in_prose_requires_structured_grounding():
    profile = _profile().model_copy(
        update={
            "market_snapshot": MarketSnapshot(
                price=42.1,
                as_of="2030-01-10",
                source_id="src_a",
                source_ids=["src_a", "src_b"],
                stale_days=1,
                confidence=0.85,
            )
        }
    )
    alpha = _alpha(
        alpha_signal="当前股价（2030-01-10收盘约42.1元）仅是观察值"
    )

    assert not TemporalGroundingValidator().validate_alpha(
        alpha, profile, "2030-01-11"
    ).passed


def test_structured_price_must_match_consensus_and_cutoff():
    profile = _profile().model_copy(
        update={
            "market_snapshot": MarketSnapshot(
                price=42.1,
                as_of="2030-01-10",
                source_id="src_a",
                source_ids=["src_a", "src_b"],
                stale_days=1,
                confidence=0.85,
            )
        }
    )
    alpha = _alpha(
        alpha_signal="当前股价42.1元仅作为状态观测",
        observed_price=42.1,
        price_as_of="2030-01-10",
        price_evidence_ids=["src_a", "src_b"],
    )

    assert TemporalGroundingValidator().validate_alpha(
        alpha, profile, "2030-01-11"
    ).passed
    assert not TemporalGroundingValidator().validate_alpha(
        alpha.model_copy(update={"price_as_of": "2030-01-12"}),
        profile,
        "2030-01-11",
    ).passed


def test_financial_gate_rejects_future_period_and_wrong_unit_conversion():
    profile = _profile().model_copy(
        update={
            "latest_reporting_period": "2030Q1",
            "latest_financial_facts": [
                FinancialFact(
                    metric="营业收入",
                    period="2030Q1",
                    value=10_000_000_000,
                    unit="CNY",
                    reported_value=10,
                    reported_unit="亿元",
                    evidence_ids=["src_filing"],
                )
            ],
        }
    )
    result = FinancialConsistencyValidator().validate(
        profile, "2029-12-31"
    )
    assert not result.passed
    assert "after cutoff" in result.reason or "future period" in result.reason
    assert "unit conversion mismatch" in result.reason


def test_financial_gate_accepts_base_currency_unit_alias():
    profile = _profile().model_copy(
        update={
            "latest_financial_facts": [
                FinancialFact(
                    metric="营业收入",
                    period="2029全年",
                    value=1_000_000_000,
                    unit="元",
                    reported_value=10,
                    reported_unit="亿元",
                    evidence_ids=["src_filing"],
                )
            ]
        }
    )

    assert FinancialConsistencyValidator().validate(
        profile, "2030-01-11"
    ).passed


def test_nontradable_business_unit_cannot_be_an_investment_candidate():
    mapping = InvestmentMapping(
        best_positioned=[],
        overvalued=[
            AssetMapping(
                asset="示例能源设备事业部",
                asset_type="business_unit",
                is_tradable=False,
                role="FV_bottleneck",
                exposure=0.8,
                sensitivity_to_drivers=["需求变化"],
                risk_profile="订单下降",
                evidence_ids=["src_filing"],
                verification_status="partial",
            )
        ],
        fragile=[],
    )

    assert not InvestmentValidator().validate(
        mapping,
        _profile(),
        "2030-01-11",
        {"src_filing"},
    ).passed
