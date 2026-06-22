"""V2 Hard Gates — 5 mandatory validation gates for Structural Alpha Discovery Engine."""

from __future__ import annotations

from structflow.models import (
    GateResult,
    GateValidationReport,
    L1StructureDecomposition,
    L2FlowAnalysis,
    L4DriverAnalysis,
    L5ScenarioAnalysis,
    L6AlphaAnalysis,
)

# V2 mandatory roles
REQUIRED_ROLES = {"Producer", "Consumer", "Mediator", "Controller", "Capital Provider"}


def gate1_structure_completeness(l1: L1StructureDecomposition) -> GateResult:
    """Gate 1: Structure Completeness — all 5 roles must be present."""
    found_roles = {role.role_type for role in l1.roles}
    missing = REQUIRED_ROLES - found_roles
    passed = len(missing) == 0

    # Also check power matrix is filled
    power = l1.power_matrix
    power_fields = [
        power.pricing_power, power.entry_power, power.standard_power,
        power.capital_power, power.data_power,
    ]
    all_power_filled = all(f.strip() for f in power_fields)

    passed = passed and all_power_filled
    reason = (
        f"All 5 roles present ({', '.join(sorted(found_roles))}), power matrix complete."
        if passed
        else f"Missing roles: {missing}. Power fields filled: {all_power_filled}"
    )
    return GateResult(gate_name="Gate1_StructureCompleteness", passed=passed, reason=reason)


def gate2_flow_completeness(l2: L2FlowAnalysis) -> GateResult:
    """Gate 2: Flow Completeness — all 4 flows must be present (Cash, Info, Risk, Attention)."""
    flows = {
        "Cash": l2.cash_nodes,
        "Information": l2.information_nodes,
        "Risk": l2.risk_nodes,
        "Attention": l2.attention_nodes,
    }
    missing = [name for name, nodes in flows.items() if len(nodes) == 0]
    passed = len(missing) == 0
    reason = (
        f"All 4 flows present: Cash={len(flows['Cash'])}, Info={len(flows['Information'])}, "
        f"Risk={len(flows['Risk'])}, Attention={len(flows['Attention'])}"
        if passed
        else f"Missing flows: {', '.join(missing)}"
    )
    return GateResult(gate_name="Gate2_FlowCompleteness", passed=passed, reason=reason)


def gate3_driver_ranking(l4: L4DriverAnalysis) -> GateResult:
    """Gate 3: Driver Ranking — importance weights must sum to 1.0 (100%)."""
    total = sum(d.importance for d in l4.drivers)
    # Allow small floating point tolerance
    passed = abs(total - 1.0) < 0.05
    reason = (
        f"Driver weights sum: {total:.2f} ({len(l4.drivers)} drivers). "
        f"Drivers: {', '.join(f'{d.name}={d.importance:.0%}' for d in l4.drivers)}"
    )
    return GateResult(gate_name="Gate3_DriverRanking", passed=passed, reason=reason)


def gate4_scenario_coverage(l5: L5ScenarioAnalysis) -> GateResult:
    """Gate 4: Scenario Coverage — Bull, Base, Bear all present, probabilities sum to 1.0."""
    total_prob = l5.bull.probability + l5.base.probability + l5.bear.probability
    has_triggers = all(
        len(s.triggers) > 0 for s in [l5.bull, l5.base, l5.bear]
    )
    passed = abs(total_prob - 1.0) < 0.05 and has_triggers
    reason = (
        f"Scenarios: Bull={l5.bull.probability:.0%}, Base={l5.base.probability:.0%}, "
        f"Bear={l5.bear.probability:.0%} (sum={total_prob:.2f}). All have triggers: {has_triggers}"
    )
    return GateResult(gate_name="Gate4_ScenarioCoverage", passed=passed, reason=reason)


def gate5_alpha_generation(l6: L6AlphaAnalysis) -> GateResult:
    """Gate 5: Alpha Generation — Consensus, Reality, Mispricing, Alpha all present."""
    fields = {
        "consensus": l6.consensus,
        "reality": l6.reality,
        "mispricing": l6.mispricing,
        "alpha_thesis": l6.alpha_thesis,
    }
    missing = [name for name, value in fields.items() if not value or len(value.strip()) < 10]
    passed = len(missing) == 0
    reason = (
        "All 4 alpha components present: consensus, reality, mispricing, alpha_thesis."
        if passed
        else f"Missing or too short: {', '.join(missing)}"
    )
    return GateResult(gate_name="Gate5_AlphaGeneration", passed=passed, reason=reason)


def run_all_gates(
    l1: L1StructureDecomposition,
    l2: L2FlowAnalysis,
    l4: L4DriverAnalysis,
    l5: L5ScenarioAnalysis,
    l6: L6AlphaAnalysis,
) -> GateValidationReport:
    """Run all 5 V2 gates and return the validation report."""
    gates = [
        gate1_structure_completeness(l1),
        gate2_flow_completeness(l2),
        gate3_driver_ranking(l4),
        gate4_scenario_coverage(l5),
        gate5_alpha_generation(l6),
    ]
    return GateValidationReport(gates=gates)
