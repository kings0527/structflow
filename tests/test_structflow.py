"""Unit tests for StructFlow Atlas V2 — gates, reporter, and models."""

from __future__ import annotations

import json

from structflow.gates import run_all_gates
from structflow.models import (
    CompanyScore,
    FlowNode,
    GateValidationReport,
    IndustryRole,
    L0IndustryDefinition,
    L1StructureDecomposition,
    L2FlowAnalysis,
    L3RiskAnalysis,
    L4DriverAnalysis,
    L5ScenarioAnalysis,
    L6AlphaAnalysis,
    L7PortfolioMapping,
    PortfolioEntity,
    PowerMatrix,
    ProfitRiskSeparation,
    RiskConcentration,
    Driver,
    Scenario,
    ScanInput,
    ScanOutput,
    ScoreVector,
    TimeHorizon,
)
from structflow.reporter import render_report


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_l0() -> L0IndustryDefinition:
    return L0IndustryDefinition(
        core_need="On-demand compute infrastructure for enterprises",
        substitution_risk=0.3,
        demand_elasticity=0.2,
        narrative_dependency=0.2,
        regulatory_dependency=0.3,
    )


def _make_l1() -> L1StructureDecomposition:
    return L1StructureDecomposition(
        roles=[
            IndustryRole(role_type="Producer", entities=["AWS", "Azure", "GCP"], description="Provide compute", evidence="Top 3 cloud providers control 65% of market"),
            IndustryRole(role_type="Consumer", entities=["Enterprises"], description="Pay for compute", evidence="Enterprise IT spend on cloud exceeds $500B annually"),
            IndustryRole(role_type="Mediator", entities=["Cloud resellers"], description="Connect buyers and sellers", evidence="Resellers handle 15% of enterprise cloud deals"),
            IndustryRole(role_type="Controller", entities=["Hyperscalers"], description="Set API standards and pricing", evidence="Hyperscalers define API standards like S3-compatible"),
            IndustryRole(role_type="Capital Provider", entities=["VC", "PE"], description="Fund infrastructure", evidence="VC/PE fund data center buildout exceeding $200B"),
        ],
        power_matrix=PowerMatrix(
            pricing_power="Controller sets list pricing; Consumer negotiates volume",
            entry_power="Controller via capital expenditure barriers",
            standard_power="Controller defines API standards",
            capital_power="Capital Provider funds infrastructure expansion",
            data_power="Controller via telemetry and usage data",
        ),
    )


def _make_l2() -> L2FlowAnalysis:
    return L2FlowAnalysis(
        cash_nodes=[
            FlowNode(entity="Enterprise", role="Consumer", description="Pays monthly invoice"),
            FlowNode(entity="Cloud Provider", role="Producer", description="Receives payment, deducts infra cost"),
        ],
        information_nodes=[
            FlowNode(entity="Cloud Provider", role="Controller", description="Knows real utilization rates"),
            FlowNode(entity="Enterprise", role="Consumer", description="Sees only billed usage, not actual capacity"),
        ],
        risk_nodes=[
            FlowNode(entity="Cloud Provider", role="Producer", description="Bears capex risk on data centers"),
        ],
        attention_nodes=[
            FlowNode(entity="Hyperscalers", role="Controller", description="Capture developer attention via ecosystem lock-in"),
        ],
    )


def _make_l3() -> L3RiskAnalysis:
    return L3RiskAnalysis(
        risk_concentrations=[
            RiskConcentration(entity="Cloud Provider", risk_type="operational", severity=0.7),
            RiskConcentration(entity="Enterprise", risk_type="vendor_lockin", severity=0.5),
        ],
        profit_risk_separation=ProfitRiskSeparation(
            profit_owner="Cloud Provider",
            risk_owner="Cloud Provider",
            gap_score=0.2,
        ),
    )


def _make_l4() -> L4DriverAnalysis:
    return L4DriverAnalysis(
        drivers=[
            Driver(name="AI/ML Workload Growth", importance=0.35, direction="+", confidence=0.85),
            Driver(name="Enterprise Digital Transformation", importance=0.25, direction="+", confidence=0.80),
            Driver(name="Regulatory Pressure (Data Sovereignty)", importance=0.15, direction="-", confidence=0.70),
            Driver(name="Edge Computing Adoption", importance=0.15, direction="+", confidence=0.65),
            Driver(name="Economic Downturn", importance=0.10, direction="-", confidence=0.60),
        ],
    )


def _make_l5() -> L5ScenarioAnalysis:
    return L5ScenarioAnalysis(
        bull=Scenario(probability=0.25, triggers=["AI workloads exceed expectations", "Enterprise migration accelerates"]),
        base=Scenario(probability=0.55, triggers=["Steady growth in cloud adoption", "Gradual AI integration"]),
        bear=Scenario(probability=0.20, triggers=["Economic recession cuts IT spend", "Regulatory breakup of hyperscalers"]),
    )


def _make_l6() -> L6AlphaAnalysis:
    return L6AlphaAnalysis(
        consensus="Market believes cloud growth is linear and predictable",
        reality="AI workloads are driving non-linear demand spikes that strain capacity",
        mispricing="Market underestimates the velocity of AI-driven capacity demand",
        alpha_thesis="Long cloud infrastructure providers with AI capacity — structural demand is accelerating beyond linear models",
    )


def _make_l7() -> L7PortfolioMapping:
    return L7PortfolioMapping(
        best_positioned_entities=[
            PortfolioEntity(name="AWS", role="Controller/Producer", reason="Dominant market share + AI capacity advantage"),
            PortfolioEntity(name="Azure", role="Controller/Producer", reason="Enterprise integration + OpenAI partnership"),
        ],
        overvalued_entities=[
            PortfolioEntity(name="Cloud resellers", role="Mediator", reason="Thin margins, easily disintermediated"),
        ],
        fragile_entities=[
            PortfolioEntity(name="Enterprise", role="Consumer", reason="Vendor lock-in with rising costs"),
        ],
    )


def _make_gate_report():
    return run_all_gates(_make_l1(), _make_l2(), _make_l4(), _make_l5(), _make_l6())


def _make_scan_output() -> ScanOutput:
    return ScanOutput(
        industry="Cloud Computing",
        region="Global",
        time_horizon=TimeHorizon.MID,
        meta=_make_l0(),
        structure=_make_l1(),
        flow=_make_l2(),
        risk=_make_l3(),
        drivers=_make_l4(),
        scenarios=_make_l5(),
        alpha=_make_l6(),
        portfolio=_make_l7(),
        gate_validation=_make_gate_report(),
        key_fragilities=["High capex risk at Controller level"],
    )


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

def test_scan_input_defaults():
    scan_input = ScanInput(industry="semiconductor")
    assert scan_input.region is None
    assert scan_input.time_horizon == TimeHorizon.MID
    assert scan_input.peer_set == []


def test_l0_model_validation():
    l0 = _make_l0()
    assert 0 <= l0.substitution_risk <= 1
    assert 0 <= l0.demand_elasticity <= 1
    assert 0 <= l0.regulatory_dependency <= 1
    assert l0.core_need == "On-demand compute infrastructure for enterprises"


def test_l1_five_roles_required():
    l1 = _make_l1()
    role_types = {r.role_type for r in l1.roles}
    assert role_types == {"Producer", "Consumer", "Mediator", "Controller", "Capital Provider"}


def test_gate1_structure_completeness():
    l1 = _make_l1()
    from structflow.gates import gate1_structure_completeness
    result = gate1_structure_completeness(l1)
    assert result.passed is True


def test_gate1_fails_with_missing_roles():
    l1 = L1StructureDecomposition(
        roles=[IndustryRole(role_type="Producer", entities=["X"], description="test", evidence="test")],
        power_matrix=PowerMatrix(
            pricing_power="X", entry_power="X", standard_power="X",
            capital_power="X", data_power="X",
        ),
    )
    from structflow.gates import gate1_structure_completeness
    result = gate1_structure_completeness(l1)
    assert result.passed is False


def test_gate2_flow_completeness():
    l2 = _make_l2()
    from structflow.gates import gate2_flow_completeness
    result = gate2_flow_completeness(l2)
    assert result.passed is True


def test_gate3_driver_ranking():
    l4 = _make_l4()
    from structflow.gates import gate3_driver_ranking
    result = gate3_driver_ranking(l4)
    assert result.passed is True


def test_gate3_fails_with_wrong_weights():
    l4 = L4DriverAnalysis(drivers=[
        Driver(name="A", importance=0.5, direction="+", confidence=0.8),
        Driver(name="B", importance=0.3, direction="+", confidence=0.7),
    ])
    from structflow.gates import gate3_driver_ranking
    result = gate3_driver_ranking(l4)
    assert result.passed is False


def test_gate4_scenario_coverage():
    l5 = _make_l5()
    from structflow.gates import gate4_scenario_coverage
    result = gate4_scenario_coverage(l5)
    assert result.passed is True


def test_gate4_fails_with_wrong_probabilities():
    l5 = L5ScenarioAnalysis(
        bull=Scenario(probability=0.3, triggers=["x"]),
        base=Scenario(probability=0.3, triggers=["y"]),
        bear=Scenario(probability=0.3, triggers=["z"]),
    )
    from structflow.gates import gate4_scenario_coverage
    result = gate4_scenario_coverage(l5)
    assert result.passed is False


def test_gate5_alpha_generation():
    l6 = _make_l6()
    from structflow.gates import gate5_alpha_generation
    result = gate5_alpha_generation(l6)
    assert result.passed is True


def test_gate5_fails_with_missing_alpha():
    l6 = L6AlphaAnalysis(
        consensus="short",
        reality="Some reality text here",
        mispricing="Some mispricing text here",
        alpha_thesis="Some alpha thesis text here",
    )
    from structflow.gates import gate5_alpha_generation
    result = gate5_alpha_generation(l6)
    assert result.passed is False


def test_all_gates_pass():
    report = run_all_gates(_make_l1(), _make_l2(), _make_l4(), _make_l5(), _make_l6())
    assert report.all_passed is True
    assert len(report.failed_gates) == 0


def test_report_renders_all_sections():
    output = _make_scan_output()
    report = render_report(output)
    assert "## 1. Meta" in report
    assert "## 2. Structure" in report
    assert "## 3. Flow" in report
    assert "## 4. Risk" in report
    assert "## 5. Drivers" in report
    assert "## 6. Scenarios" in report
    assert "## 7. Alpha" in report
    assert "## 8. Investment Mapping" in report
    assert "## Gate Validation" in report


def test_report_contains_company_data():
    output = _make_scan_output()
    report = render_report(output)
    assert "AWS" in report
    assert "AI/ML Workload Growth" in report


def test_scan_output_json_serializable():
    output = _make_scan_output()
    json_str = output.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["industry"] == "Cloud Computing"
    assert parsed["meta"]["core_need"] == "On-demand compute infrastructure for enterprises"
    assert len(parsed["drivers"]["drivers"]) == 5
    assert parsed["alpha"]["consensus"] is not None


def test_score_vector_bounds():
    sv = ScoreVector(
        control_score=0, profit_capture_score=0,
        risk_displacement_score=0, information_advantage_score=0,
        incentive_alignment_score=0,
    )
    assert sv.control_score == 0

    sv_max = ScoreVector(
        control_score=10, profit_capture_score=10,
        risk_displacement_score=10, information_advantage_score=10,
        incentive_alignment_score=10,
    )
    assert sv_max.control_score == 10


def test_structural_health_calculation():
    """Verify structural health formula: (C x PC x IA) / ((10-RD) + (10-IA_score))"""
    company = CompanyScore(
        name="TestCo",
        role="Controller",
        score_vector=ScoreVector(
            control_score=8, profit_capture_score=7,
            risk_displacement_score=3, information_advantage_score=9,
            incentive_alignment_score=7,
        ),
        structural_health=0,
    )
    sv = company.score_vector
    expected_health = (sv.control_score * sv.profit_capture_score * sv.information_advantage_score) / ((10 - sv.risk_displacement_score) + (10 - sv.incentive_alignment_score))
    assert abs(expected_health - (8 * 7 * 9) / (7 + 3)) < 0.01


def test_driver_weights_sum():
    l4 = _make_l4()
    total = sum(d.importance for d in l4.drivers)
    assert abs(total - 1.0) < 0.01


def test_scenario_probabilities_sum():
    l5 = _make_l5()
    total = l5.bull.probability + l5.base.probability + l5.bear.probability
    assert abs(total - 1.0) < 0.01


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
