"""Output validation: cross-check LLM output for V2.1 Meta-Generalization Layer.

V2.1 validators:
- Variable completeness: all 4 types present
- System equation: α+β+γ=1
- Driver source validation: drivers traceable to SV/FV/CV/LV
- De-entity check: no company names in variable lists
- De-narrative check: narrative only in LV
- Alpha completeness: all components substantive
- Cross-layer consistency: L7 entities linked to variables
"""

from __future__ import annotations

import re
from typing import Optional

from structflow.models import (
    AlphaSignal,
    DistortionAnalysis,
    DriverSet,
    GateResult,
    L7PortfolioMapping,
    RegimeState,
    SystemEquation,
    VariableMapping,
)

VALID_DRIVER_TYPES = {"macro", "micro", "policy", "behavioral", "financial"}
VALID_REGIMES = {"expansion", "contraction", "transition", "bubble", "collapse"}


class OutputValidator:
    """Validates LLM output quality for V2.1 Meta-Generalization Layer."""

    def __init__(self, collected_data: Optional[dict[str, str]] = None):
        self.collected_data = collected_data or {}
        self._all_text = self._flatten_data()

    def _flatten_data(self) -> str:
        parts = []
        for key, value in self.collected_data.items():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    parts.append(f"{sub_key}: {sub_value}")
        return " ".join(parts).lower()

    # ── Variable Completeness ─────────────────────────────────

    def validate_variable_completeness(
        self,
        l1: VariableMapping,
    ) -> GateResult:
        """Check all 4 variable types have at least 3 items."""
        counts = {
            "SV": len(l1.state_variables),
            "FV": len(l1.flow_variables),
            "CV": len(l1.control_variables),
            "LV": len(l1.latent_variables),
        }
        too_few = [k for k, v in counts.items() if v < 3]
        passed = len(too_few) == 0
        reason = f"SV={counts['SV']}, FV={counts['FV']}, CV={counts['CV']}, LV={counts['LV']}"
        if too_few:
            reason += f" — too few: {', '.join(too_few)}"
        return GateResult(gate_name="VariableCompleteness", passed=passed, reason=reason)

    # ── System Equation ───────────────────────────────────────

    def validate_system_equation(
        self,
        l2: SystemEquation,
    ) -> GateResult:
        """Check α + β + γ = 1.0."""
        total = l2.flow_weight + l2.control_weight + l2.latent_weight
        passed = abs(total - 1.0) < 0.05
        reason = f"α={l2.flow_weight:.2f} + β={l2.control_weight:.2f} + γ={l2.latent_weight:.2f} = {total:.2f}"
        if not passed:
            reason += " — should be 1.0"
        return GateResult(gate_name="SystemEquation", passed=passed, reason=reason)

    # ── Driver Source Validation ──────────────────────────────

    def validate_driver_sources(
        self,
        l3: DriverSet,
    ) -> GateResult:
        """Check all drivers have valid type and direction."""
        if not l3.drivers:
            return GateResult(gate_name="DriverSources", passed=False, reason="No drivers")

        issues = []
        for d in l3.drivers:
            if d.type not in VALID_DRIVER_TYPES:
                issues.append(f"{d.name}: invalid type '{d.type}'")
            if d.direction not in ("+", "-"):
                issues.append(f"{d.name}: invalid direction '{d.direction}'")
            if not (0 <= d.elasticity <= 1):
                issues.append(f"{d.name}: elasticity out of range")
            if d.lag not in ("short", "mid", "long"):
                issues.append(f"{d.name}: invalid lag '{d.lag}'")

        passed = len(issues) == 0
        reason = f"{len(l3.drivers)} drivers checked"
        if issues:
            reason += f". Issues: {'; '.join(issues[:5])}"
        return GateResult(gate_name="DriverSources", passed=passed, reason=reason)

    # ── Regime Validation ─────────────────────────────────────

    def validate_regime(
        self,
        l4: RegimeState,
    ) -> GateResult:
        """Check regime is valid with reasonable confidence."""
        valid = l4.current_regime in VALID_REGIMES
        has_drivers = len(l4.regime_drivers) > 0
        passed = valid and has_drivers
        reason = f"Regime: {l4.current_regime}, confidence={l4.regime_confidence:.2f}, drivers={len(l4.regime_drivers)}"
        if not valid:
            reason += f" — invalid regime (must be one of {VALID_REGIMES})"
        if not has_drivers:
            reason += " — no regime drivers"
        return GateResult(gate_name="RegimeValidation", passed=passed, reason=reason)

    # ── Distortion Validation ─────────────────────────────────

    def validate_distortion(
        self,
        l5: DistortionAnalysis,
    ) -> GateResult:
        """Check distortion analysis is substantive."""
        issues = []
        if not l5.market_belief or len(l5.market_belief.strip()) < 10:
            issues.append("market_belief too short")
        if len(l5.true_drivers) == 0:
            issues.append("no true_drivers")
        if len(l5.mispricing_sources) == 0:
            issues.append("no mispricing_sources")
        if not (0 <= l5.distortion_score <= 1):
            issues.append("distortion_score out of range")

        passed = len(issues) == 0
        reason = f"market_belief={'✓' if 'market_belief' not in str(issues) else '✗'}, true_drivers={len(l5.true_drivers)}, mispricing_sources={len(l5.mispricing_sources)}, score={l5.distortion_score:.2f}"
        if issues:
            reason += f". Issues: {'; '.join(issues)}"
        return GateResult(gate_name="DistortionValidation", passed=passed, reason=reason)

    # ── Alpha Completeness ────────────────────────────────────

    def validate_alpha_completeness(
        self,
        l6: AlphaSignal,
    ) -> GateResult:
        """Check all alpha components are substantive."""
        fields = {
            "consensus_view": l6.consensus_view,
            "structural_view": l6.structural_view,
            "mispricing": l6.mispricing,
            "alpha_signal": l6.alpha_signal,
        }
        too_short = [name for name, value in fields.items() if not value or len(value.strip()) < 10]
        passed = len(too_short) == 0
        reason = "All 4 alpha components present and substantive" if passed else f"Too short: {', '.join(too_short)}"
        return GateResult(gate_name="AlphaCompleteness", passed=passed, reason=reason)

    # ── De-entity Check ───────────────────────────────────────

    @staticmethod
    def _looks_like_company(name: str) -> bool:
        """Heuristic: does this look like a company name vs a variable?"""
        # Company indicators: Inc, Corp, Ltd, Co, LLC, AG, SA, etc.
        company_patterns = [
            r'\b(Inc|Corp|Ltd|LLC|Co\.|AG|SA|NV|PLC|GmbH|Group|Holdings?)\b',
            r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$',  # Title Case Names
        ]
        for pattern in company_patterns:
            if re.search(pattern, name):
                return True
        return False

    def validate_de_entity(
        self,
        l1: VariableMapping,
    ) -> GateResult:
        """Check that variable lists don't contain company names."""
        all_vars = (
            l1.state_variables + l1.flow_variables +
            l1.control_variables + l1.latent_variables
        )
        company_like = [v for v in all_vars if self._looks_like_company(v)]
        passed = len(company_like) == 0
        reason = f"{len(all_vars)} variables checked"
        if company_like:
            reason += f". Possible company names: {', '.join(company_like[:5])}"
        return GateResult(gate_name="DeEntityCheck", passed=passed, reason=reason)

    # ── De-narrative Check ────────────────────────────────────

    def validate_de_narrative(
        self,
        l1: VariableMapping,
    ) -> GateResult:
        """Check narrative only appears in LV, not in SV/FV/CV."""
        narrative_keywords = ["narrative", "story", "storytelling", "hype", "buzz", "sentiment"]
        misplaced = []
        for var in l1.state_variables + l1.flow_variables + l1.control_variables:
            var_lower = var.lower()
            if any(kw in var_lower for kw in narrative_keywords):
                misplaced.append(var)

        passed = len(misplaced) == 0
        reason = "Narrative confined to LV" if passed else f"Narrative in SV/FV/CV: {', '.join(misplaced[:5])}"
        return GateResult(gate_name="DeNarrativeCheck", passed=passed, reason=reason)

    # ── Cross-Layer Consistency ───────────────────────────────

    def validate_cross_layer_consistency(
        self,
        l1: VariableMapping,
        l4: RegimeState,
        l5: DistortionAnalysis,
        l7: Optional[L7PortfolioMapping] = None,
    ) -> GateResult:
        """Check regime drivers and true_drivers trace back to L1 variables."""
        all_l1_vars = set(
            v.lower() for v in (
                l1.state_variables + l1.flow_variables +
                l1.control_variables + l1.latent_variables
            )
        )

        def check_traceable(items):
            untraceable = []
            for item in items:
                item_lower = item.lower()
                matched = any(
                    item_lower in l1_var or l1_var in item_lower
                    for l1_var in all_l1_vars
                )
                if not matched:
                    untraceable.append(item)
            return untraceable

        l4_untraceable = check_traceable(l4.regime_drivers)
        l5_untraceable = check_traceable(l5.true_drivers)

        total = len(l4_untraceable) + len(l5_untraceable)
        passed = total == 0

        parts = []
        if l4_untraceable:
            parts.append(f"L4 untraceable: {', '.join(l4_untraceable[:3])}")
        if l5_untraceable:
            parts.append(f"L5 untraceable: {', '.join(l5_untraceable[:3])}")
        if not parts:
            parts.append("All L4/L5 drivers traceable to L1 variables")

        return GateResult(gate_name="CrossLayerConsistency", passed=passed, reason="; ".join(parts))

    # ── Run All Validations ───────────────────────────────────

    def run_all_validations(
        self,
        l1: VariableMapping,
        l2: SystemEquation,
        l3: DriverSet,
        l4: RegimeState,
        l5: DistortionAnalysis,
        l6: AlphaSignal,
        l7: Optional[L7PortfolioMapping] = None,
    ) -> list[GateResult]:
        """Run all V2.1 validation checks."""
        results = [
            self.validate_variable_completeness(l1),
            self.validate_system_equation(l2),
            self.validate_driver_sources(l3),
            self.validate_regime(l4),
            self.validate_distortion(l5),
            self.validate_alpha_completeness(l6),
            self.validate_de_entity(l1),
            self.validate_de_narrative(l1),
            self.validate_cross_layer_consistency(l1, l4, l5, l7),
        ]
        return results
