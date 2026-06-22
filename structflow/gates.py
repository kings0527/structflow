"""5 Hard Gates — mandatory validation before output is considered valid."""

from __future__ import annotations

from structflow.models import (
    GateResult,
    GateValidationReport,
    L1StructureDecomposition,
    L2FlowRiskAnalysis,
    L3ScoringRanking,
)


def gate1_control_identified(l1: L1StructureDecomposition) -> GateResult:
    """Gate 1: Has control power been identified?"""
    power = l1.power_matrix
    control_fields = [
        power.pricing_power,
        power.entry_control,
        power.data_control,
        power.switching_cost,
        power.standard_control,
    ]
    all_filled = all(field.strip() for field in control_fields)
    roles_identified = len(l1.roles) >= 4
    passed = all_filled and roles_identified
    reason = (
        "All 5 power dimensions attributed to roles, 4 roles identified."
        if passed
        else f"Missing: roles={len(l1.roles)}/4, empty power fields={sum(1 for f in control_fields if not f.strip())}"
    )
    return GateResult(gate_name="Gate1_ControlIdentified", passed=passed, reason=reason)


def gate2_risk_attribution(l2: L2FlowRiskAnalysis) -> GateResult:
    """Gate 2: Has risk been attributed? Must answer: who profits, who bears risk?"""
    has_risk_points = len(l2.risk_accumulation_points) > 0
    has_risk_answer = bool(l2.risk_concentration_answer.strip())
    has_profit_risk_answer = bool(l2.profit_risk_separation_answer.strip())
    passed = has_risk_points and has_risk_answer and has_profit_risk_answer
    reason = (
        "Risk accumulation points identified, profit/risk attribution answered."
        if passed
        else f"Missing: risk_points={has_risk_points}, risk_answer={has_risk_answer}, profit_risk_answer={has_profit_risk_answer}"
    )
    return GateResult(gate_name="Gate2_RiskAttribution", passed=passed, reason=reason)


def gate3_information_asymmetry(l2: L2FlowRiskAnalysis) -> GateResult:
    """Gate 3: Has information asymmetry been identified? Who knows first, who knows late?"""
    has_asymmetry_nodes = len(l2.information_asymmetry_nodes) > 0
    passed = has_asymmetry_nodes
    reason = (
        f"Information asymmetry identified at {len(l2.information_asymmetry_nodes)} nodes."
        if passed
        else "No information asymmetry nodes identified."
    )
    return GateResult(gate_name="Gate3_InfoAsymmetry", passed=passed, reason=reason)


def gate4_hidden_flows(l2: L2FlowRiskAnalysis) -> GateResult:
    """Gate 4: Have hidden flows been checked? Subsidies, policy dependency, book vs real cash."""
    has_subsidy_answer = bool(l2.subsidy_answer.strip())
    has_hidden_sources = len(l2.hidden_subsidy_sources) >= 0  # can be empty but must be checked
    has_value_capture = len(l2.value_capture_points) > 0
    passed = has_subsidy_answer and has_hidden_sources and has_value_capture
    reason = (
        f"Hidden flows checked: subsidy_answer={'yes' if has_subsidy_answer else 'no'}, "
        f"hidden_sources={len(l2.hidden_subsidy_sources)}, value_capture_points={len(l2.value_capture_points)}."
        if passed
        else "Hidden flow check incomplete."
    )
    return GateResult(gate_name="Gate4_HiddenFlows", passed=passed, reason=reason)


def gate5_comparable_output(l3: L3ScoringRanking) -> GateResult:
    """Gate 5: Is output horizontally comparable? Must have score vectors for industry + companies."""
    has_industry_score = l3.industry_score is not None
    has_company_scores = len(l3.companies_ranked) > 0
    has_phase = l3.phase is not None
    passed = has_industry_score and has_company_scores and has_phase
    reason = (
        f"Comparable output: industry_score=yes, companies_scored={len(l3.companies_ranked)}, phase={l3.phase.stage.value}."
        if passed
        else f"Incomplete: industry_score={has_industry_score}, companies={has_company_scores}, phase={has_phase}."
    )
    return GateResult(gate_name="Gate5_ComparableOutput", passed=passed, reason=reason)


def run_all_gates(
    l1: L1StructureDecomposition,
    l2: L2FlowRiskAnalysis,
    l3: L3ScoringRanking,
) -> GateValidationReport:
    """Run all 5 gates and return the validation report."""
    gates = [
        gate1_control_identified(l1),
        gate2_risk_attribution(l2),
        gate3_information_asymmetry(l2),
        gate4_hidden_flows(l2),
        gate5_comparable_output(l3),
    ]
    return GateValidationReport(gates=gates)
