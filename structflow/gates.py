"""V2.2 Hard Gates — 5 mandatory validation gates for Nonlinear Regime System.

1. Variable Completeness — SV/FV/CV/LV each ≥ 3
2. Driver Binding — every driver maps to SV/FV/CV/LV
3. Feedback Completeness — ≥ 3 loops, ≥ 1 reinforcing + ≥ 1 balancing
4. Regime Engine — valid regime + transition_probability
5. Alpha Generation — all components + direction
"""

from __future__ import annotations

from structflow.models import (
    AlphaEngine,
    DriverSpace,
    FlowFeedbackSystem,
    GateResult,
    GateValidationReport,
    RegimeEngine,
    VariableMapping,
)

VALID_REGIMES = {"expansion", "contraction", "transition", "bubble", "collapse", "shock"}
VALID_DRIVER_CATEGORIES = {"macro", "micro", "policy", "behavioral", "financial", "structural"}
VALID_DIRECTIONS = {"+", "-", "nonlinear"}
VALID_VAR_MAPS = {"SV", "FV", "CV", "LV"}
VALID_ALPHA_DIRECTIONS = {"long", "short", "neutral"}


def gate1_variable_completeness(l1: VariableMapping) -> GateResult:
    counts = {"SV": len(l1.state_variables), "FV": len(l1.flow_variables),
              "CV": len(l1.control_variables), "LV": len(l1.latent_variables)}
    too_few = [k for k, v in counts.items() if v < 3]
    passed = len(too_few) == 0
    reason = f"SV={counts['SV']}, FV={counts['FV']}, CV={counts['CV']}, LV={counts['LV']}"
    if too_few:
        reason += f". TOO FEW: {', '.join(too_few)}"
    return GateResult(gate_name="Gate1_VariableCompleteness", passed=passed, reason=reason)


def gate2_driver_binding(l2: DriverSpace) -> GateResult:
    if not l2.drivers:
        return GateResult(gate_name="Gate2_DriverBinding", passed=False, reason="No drivers")
    issues = []
    for d in l2.drivers:
        if d.maps_to_variable not in VALID_VAR_MAPS:
            issues.append(f"{d.name}: invalid maps_to_variable '{d.maps_to_variable}'")
        if d.category not in VALID_DRIVER_CATEGORIES:
            issues.append(f"{d.name}: invalid category '{d.category}'")
        if d.direction not in VALID_DIRECTIONS:
            issues.append(f"{d.name}: invalid direction '{d.direction}'")
    passed = len(issues) == 0
    reason = f"{len(l2.drivers)} drivers checked"
    if issues:
        reason += f". Issues: {'; '.join(issues[:5])}"
    return GateResult(gate_name="Gate2_DriverBinding", passed=passed, reason=reason)


def gate3_feedback_completeness(l3: FlowFeedbackSystem) -> GateResult:
    loops = l3.feedback_loops
    if len(loops) < 3:
        return GateResult(gate_name="Gate3_FeedbackCompleteness", passed=False,
                          reason=f"Only {len(loops)} loops (min 3 required)")
    has_reinforcing = any(l.type == "reinforcing" for l in loops)
    has_balancing = any(l.type == "balancing" for l in loops)
    passed = has_reinforcing and has_balancing
    reason = f"{len(loops)} loops: reinforcing={'✓' if has_reinforcing else '✗'}, balancing={'✓' if has_balancing else '✗'}"
    return GateResult(gate_name="Gate3_FeedbackCompleteness", passed=passed, reason=reason)


def gate4_regime_engine(l4: RegimeEngine) -> GateResult:
    valid_regime = l4.current_regime in VALID_REGIMES
    valid_next = l4.transition_probability.next_regime in VALID_REGIMES
    valid_prob = 0 <= l4.transition_probability.probability <= 1
    passed = valid_regime and valid_next and valid_prob
    reason = f"Regime: {l4.current_regime}, next: {l4.transition_probability.next_regime} (p={l4.transition_probability.probability:.2f})"
    if not valid_regime:
        reason += f". Invalid current_regime"
    if not valid_next:
        reason += f". Invalid next_regime"
    return GateResult(gate_name="Gate4_RegimeEngine", passed=passed, reason=reason)


def gate5_alpha_generation(l6: AlphaEngine) -> GateResult:
    fields = {"consensus_view": l6.consensus_view, "structural_view": l6.structural_view,
              "mispricing": l6.mispricing, "alpha_signal": l6.alpha_signal}
    too_short = [n for n, v in fields.items() if not v or len(v.strip()) < 10]
    valid_direction = l6.direction in VALID_ALPHA_DIRECTIONS
    passed = len(too_short) == 0 and valid_direction
    reason = f"components={'✓' if not too_short else '✗'}, direction={l6.direction}{'✓' if valid_direction else '✗'}, confidence={l6.confidence:.2f}"
    if too_short:
        reason += f". Too short: {', '.join(too_short)}"
    return GateResult(gate_name="Gate5_AlphaGeneration", passed=passed, reason=reason)


def run_all_gates(l1: VariableMapping, l2: DriverSpace, l3: FlowFeedbackSystem,
                  l4: RegimeEngine, l6: AlphaEngine) -> GateValidationReport:
    return GateValidationReport(gates=[
        gate1_variable_completeness(l1),
        gate2_driver_binding(l2),
        gate3_feedback_completeness(l3),
        gate4_regime_engine(l4),
        gate5_alpha_generation(l6),
    ])
