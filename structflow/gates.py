"""V2.1 Hard Gates — 5 mandatory validation gates for Meta-Generalization Layer.

Gates:
1. Variable Completeness — all 4 variable types (SV/FV/CV/LV) present
2. System Equation — α + β + γ = 1.0
3. Driver Sources — all drivers traceable to SV/FV/CV/LV
4. Regime Identification — valid regime with confidence
5. Alpha Generation — all alpha components present
"""

from __future__ import annotations

from structflow.models import (
    AlphaSignal,
    DistortionAnalysis,
    DriverSet,
    GateResult,
    GateValidationReport,
    RegimeState,
    SystemEquation,
    VariableMapping,
)

VALID_REGIMES = {"expansion", "contraction", "transition", "bubble", "collapse"}
VALID_DRIVER_TYPES = {"macro", "micro", "policy", "behavioral", "financial"}


def gate1_variable_completeness(l1: VariableMapping) -> GateResult:
    """Gate 1: all 4 variable types present (SV, FV, CV, LV), each with >= 3 items."""
    counts = {
        "SV": len(l1.state_variables),
        "FV": len(l1.flow_variables),
        "CV": len(l1.control_variables),
        "LV": len(l1.latent_variables),
    }
    missing = [k for k, v in counts.items() if v == 0]
    too_few = [k for k, v in counts.items() if 0 < v < 3]
    passed = len(missing) == 0 and len(too_few) == 0
    reason = (
        f"SV={counts['SV']}, FV={counts['FV']}, CV={counts['CV']}, LV={counts['LV']}"
    )
    if missing:
        reason += f". MISSING: {', '.join(missing)}"
    if too_few:
        reason += f". TOO FEW (<3): {', '.join(too_few)}"
    return GateResult(gate_name="Gate1_VariableCompleteness", passed=passed, reason=reason)


def gate2_system_equation(l2: SystemEquation) -> GateResult:
    """Gate 2: α + β + γ = 1.0."""
    total = l2.flow_weight + l2.control_weight + l2.latent_weight
    passed = abs(total - 1.0) < 0.05
    reason = f"α={l2.flow_weight:.2f} + β={l2.control_weight:.2f} + γ={l2.latent_weight:.2f} = {total:.2f}"
    if not passed:
        reason += f" — should be 1.0 (tolerance: 0.05)"
    return GateResult(gate_name="Gate2_SystemEquation", passed=passed, reason=reason)


def gate3_driver_sources(l3: DriverSet) -> GateResult:
    """Gate 3: all drivers have valid type and traceable source."""
    if len(l3.drivers) == 0:
        return GateResult(gate_name="Gate3_DriverSources", passed=False, reason="No drivers identified")

    invalid_types = []
    invalid_directions = []
    for d in l3.drivers:
        if d.type not in VALID_DRIVER_TYPES:
            invalid_types.append(f"{d.name}(type={d.type})")
        if d.direction not in ("+", "-"):
            invalid_directions.append(f"{d.name}(direction={d.direction})")

    passed = len(invalid_types) == 0 and len(invalid_directions) == 0
    reason = f"{len(l3.drivers)} drivers checked"
    if invalid_types:
        reason += f". Invalid types: {', '.join(invalid_types[:5])}"
    if invalid_directions:
        reason += f". Invalid directions: {', '.join(invalid_directions[:5])}"
    return GateResult(gate_name="Gate3_DriverSources", passed=passed, reason=reason)


def gate4_regime_identification(l4: RegimeState) -> GateResult:
    """Gate 4: valid regime identified with reasonable confidence."""
    valid_regime = l4.current_regime in VALID_REGIMES
    has_drivers = len(l4.regime_drivers) > 0
    reasonable_confidence = l4.regime_confidence > 0.3
    passed = valid_regime and has_drivers and reasonable_confidence

    issues = []
    if not valid_regime:
        issues.append(f"invalid regime '{l4.current_regime}' (must be one of {VALID_REGIMES})")
    if not has_drivers:
        issues.append("no regime drivers listed")
    if not reasonable_confidence:
        issues.append(f"confidence too low ({l4.regime_confidence:.2f})")

    reason = f"Regime: {l4.current_regime} (confidence={l4.regime_confidence:.2f}), drivers={len(l4.regime_drivers)}"
    if issues:
        reason += f". Issues: {'; '.join(issues)}"
    return GateResult(gate_name="Gate4_RegimeIdentification", passed=passed, reason=reason)


def gate5_alpha_generation(l6: AlphaSignal) -> GateResult:
    """Gate 5: all 5 alpha components present and substantive."""
    fields = {
        "consensus_view": l6.consensus_view,
        "structural_view": l6.structural_view,
        "mispricing": l6.mispricing,
        "alpha_signal": l6.alpha_signal,
    }
    too_short = [name for name, value in fields.items() if not value or len(value.strip()) < 10]
    valid_confidence = 0 <= l6.confidence <= 1
    passed = len(too_short) == 0 and valid_confidence

    reason = f"consensus_view={'✓' if 'consensus_view' not in too_short else '✗'}, structural_view={'✓' if 'structural_view' not in too_short else '✗'}, mispricing={'✓' if 'mispricing' not in too_short else '✗'}, alpha_signal={'✓' if 'alpha_signal' not in too_short else '✗'}, confidence={l6.confidence:.2f}"
    if too_short:
        reason += f". Too short or missing: {', '.join(too_short)}"
    return GateResult(gate_name="Gate5_AlphaGeneration", passed=passed, reason=reason)


def run_all_gates(
    l1: VariableMapping,
    l2: SystemEquation,
    l3: DriverSet,
    l4: RegimeState,
    l6: AlphaSignal,
) -> GateValidationReport:
    """Run all 5 V2.1 gates and return the validation report."""
    gates = [
        gate1_variable_completeness(l1),
        gate2_system_equation(l2),
        gate3_driver_sources(l3),
        gate4_regime_identification(l4),
        gate5_alpha_generation(l6),
    ]
    return GateValidationReport(gates=gates)
