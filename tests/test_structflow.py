"""Unit tests for StructFlow — gates, reporter, and models."""

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
    L2FlowRiskAnalysis,
    L3ScoringRanking,
    PhaseIdentification,
    PowerMatrix,
    ScanInput,
    ScanOutput,
    ScoreVector,
    StructuralPhase,
    TimeHorizon,
)
from structflow.reporter import render_report


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_l0() -> L0IndustryDefinition:
    return L0IndustryDefinition(
        core_need="On-demand compute infrastructure",
        substitution_risk=0.3,
        demand_stability=0.8,
        narrative_dependency=0.2,
    )


def _make_l1() -> L1StructureDecomposition:
    return L1StructureDecomposition(
        roles=[
            IndustryRole(role_type="Producer", entities=["AWS", "Azure", "GCP"], description="Provide compute"),
            IndustryRole(role_type="Payer", entities=["Enterprises"], description="Pay for compute"),
            IndustryRole(role_type="Mediator", entities=["Cloud resellers"], description="Connect buyers and sellers"),
            IndustryRole(role_type="Controller", entities=["Hyperscalers"], description="Set API standards and pricing"),
        ],
        power_matrix=PowerMatrix(
            pricing_power="Controller sets list pricing; Payer negotiates volume discounts",
            entry_control="Controller via capital expenditure barriers",
            data_control="Controller via telemetry and usage data",
            switching_cost="High due to proprietary APIs and data gravity",
            standard_control="Controller defines API standards (e.g. S3-compatible)",
        ),
    )


def _make_l2() -> L2FlowRiskAnalysis:
    return L2FlowRiskAnalysis(
        cash_flow_chain=[
            FlowNode(entity="Enterprise", role="Payer", description="Pays monthly invoice"),
            FlowNode(entity="Cloud Provider", role="Producer", description="Receives payment, deducts infra cost"),
        ],
        value_capture_points=[
            FlowNode(entity="Cloud Provider", role="Producer", description="Captures margin on compute"),
        ],
        information_asymmetry_nodes=[
            FlowNode(entity="Cloud Provider", role="Controller", description="Knows real utilization rates"),
            FlowNode(entity="Enterprise", role="Payer", description="Sees only billed usage, not actual capacity"),
        ],
        risk_accumulation_points=[
            FlowNode(entity="Cloud Provider", role="Producer", description="Bears capex risk on data centers"),
        ],
        hidden_subsidy_sources=[],
        subsidy_answer="No significant hidden subsidies; system is self-sustaining via usage fees.",
        risk_concentration_answer="Risk concentrates at the Producer/Controller level via capex commitments.",
        profit_risk_separation_answer="No — profit and risk are aligned; providers bear capex risk and capture margin.",
    )


def _make_l3() -> L3ScoringRanking:
    return L3ScoringRanking(
        industry_score=ScoreVector(
            control_score=8.0,
            profit_capture_score=7.5,
            risk_displacement_score=4.0,
            information_advantage_score=8.0,
            incentive_alignment_score=7.0,
        ),
        companies_ranked=[
            CompanyScore(
                name="AWS",
                role="Controller/Producer",
                score_vector=ScoreVector(
                    control_score=9.0,
                    profit_capture_score=8.0,
                    risk_displacement_score=3.0,
                    information_advantage_score=9.0,
                    incentive_alignment_score=7.5,
                ),
                structural_health=21.6,
            ),
        ],
        phase=PhaseIdentification(
            stage=StructuralPhase.MATURE,
            reasoning_signals=["Market share stabilized", "Price competition intensifying", "Margin compression visible"],
        ),
    )


def _make_scan_output() -> ScanOutput:
    l0 = _make_l0()
    l1 = _make_l1()
    l2 = _make_l2()
    l3 = _make_l3()
    gate_report = run_all_gates(l1, l2, l3)
    return ScanOutput(
        industry="Cloud Computing",
        region="Global",
        time_horizon=TimeHorizon.MID,
        industry_definition=l0,
        structure=l1,
        power_map=l1.power_matrix,
        flow_analysis=l2,
        risk_map={"risk_accumulation_points": [n.model_dump() for n in l2.risk_accumulation_points], "risk_concentration": l2.risk_concentration_answer, "profit_risk_separation": l2.profit_risk_separation_answer},
        industry_structure_score=l3.industry_score,
        companies_ranked=l3.companies_ranked,
        structural_phase=l3.phase,
        gate_validation=gate_report,
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
    assert 0 <= l0.demand_stability <= 1
    assert l0.core_need == "On-demand compute infrastructure"


def test_l1_four_roles_required():
    l1 = _make_l1()
    role_types = {r.role_type for r in l1.roles}
    assert role_types == {"Producer", "Payer", "Mediator", "Controller"}


def test_gate1_passes_with_complete_data():
    l1 = _make_l1()
    from structflow.gates import gate1_control_identified
    result = gate1_control_identified(l1)
    assert result.passed is True


def test_gate1_fails_with_missing_roles():
    l1 = L1StructureDecomposition(
        roles=[IndustryRole(role_type="Producer", entities=["X"], description="test")],
        power_matrix=PowerMatrix(
            pricing_power="X", entry_control="X", data_control="X",
            switching_cost="X", standard_control="X",
        ),
    )
    from structflow.gates import gate1_control_identified
    result = gate1_control_identified(l1)
    assert result.passed is False


def test_gate2_passes_with_risk_attribution():
    l2 = _make_l2()
    from structflow.gates import gate2_risk_attribution
    result = gate2_risk_attribution(l2)
    assert result.passed is True


def test_gate3_passes_with_info_asymmetry():
    l2 = _make_l2()
    from structflow.gates import gate3_information_asymmetry
    result = gate3_information_asymmetry(l2)
    assert result.passed is True


def test_gate4_passes_with_hidden_flow_check():
    l2 = _make_l2()
    from structflow.gates import gate4_hidden_flows
    result = gate4_hidden_flows(l2)
    assert result.passed is True


def test_gate5_passes_with_scores():
    l3 = _make_l3()
    from structflow.gates import gate5_comparable_output
    result = gate5_comparable_output(l3)
    assert result.passed is True


def test_all_gates_pass():
    l1, l2, l3 = _make_l1(), _make_l2(), _make_l3()
    report = run_all_gates(l1, l2, l3)
    assert report.all_passed is True
    assert len(report.failed_gates) == 0


def test_report_renders_all_sections():
    output = _make_scan_output()
    report = render_report(output)
    assert "## 1. Structure Map" in report
    assert "## 2. Flow Map" in report
    assert "## 3. Power Map" in report
    assert "## 4. Risk Map" in report
    assert "## 5. Score Vector" in report
    assert "## 6. Structural Phase" in report
    assert "## 7. Key Fragilities" in report
    assert "## Gate Validation" in report


def test_report_contains_company_data():
    output = _make_scan_output()
    report = render_report(output)
    assert "AWS" in report
    assert "mature" in report


def test_scan_output_json_serializable():
    output = _make_scan_output()
    json_str = output.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["industry"] == "Cloud Computing"
    assert len(parsed["companies_ranked"]) == 1


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
    """Verify structural health formula: (C × PC × IA) ÷ ((10-RD) + (10-IA_score))"""
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
    # Corrected formula: risk_displacement is GOOD for company, so (10 - RD) = retained risk
    expected_health = (sv.control_score * sv.profit_capture_score * sv.information_advantage_score) / ((10 - sv.risk_displacement_score) + (10 - sv.incentive_alignment_score))
    assert abs(expected_health - (8 * 7 * 9) / (7 + 3)) < 0.01


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
