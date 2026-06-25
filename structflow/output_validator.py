"""V2.2 Output validation — Cross-Layer Binding + nonlinear constraints.

Key V2.2 validator: CrossLayerBinding — every L5/L6 statement MUST trace to
≥1 L2 driver + ≥1 L1 variable. If not traceable → FAILURE.
"""

from __future__ import annotations

import re
from typing import Optional

from structflow.models import (
    AlphaEngine,
    DistortionEngine,
    DriverSpace,
    FlowFeedbackSystem,
    GateResult,
    InvestmentMapping,
    RegimeEngine,
    VariableMapping,
)

VALID_DRIVER_CATEGORIES = {"macro", "micro", "policy", "behavioral", "financial", "structural"}
VALID_REGIMES = {"expansion", "contraction", "transition", "bubble", "collapse", "shock"}
VALID_VAR_MAPS = {"SV", "FV", "CV", "LV"}


class OutputValidator:
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

    # ── Variable Completeness ─────────────────────────
    def validate_variable_completeness(self, l1: VariableMapping) -> GateResult:
        counts = {"SV": len(l1.state_variables), "FV": len(l1.flow_variables),
                  "CV": len(l1.control_variables), "LV": len(l1.latent_variables)}
        too_few = [k for k, v in counts.items() if v < 3]
        passed = len(too_few) == 0
        reason = f"SV={counts['SV']}, FV={counts['FV']}, CV={counts['CV']}, LV={counts['LV']}"
        if too_few:
            reason += f" — too few: {', '.join(too_few)}"
        return GateResult(gate_name="VariableCompleteness", passed=passed, reason=reason)

    # ── Driver Binding ────────────────────────────────
    def validate_driver_binding(self, l2: DriverSpace) -> GateResult:
        if not l2.drivers:
            return GateResult(gate_name="DriverBinding", passed=False, reason="No drivers")
        issues = []
        for d in l2.drivers:
            if d.maps_to_variable not in VALID_VAR_MAPS:
                issues.append(f"{d.name}: invalid maps_to_variable")
            if d.category not in VALID_DRIVER_CATEGORIES:
                issues.append(f"{d.name}: invalid category")
            if d.direction not in ("+", "-", "nonlinear"):
                issues.append(f"{d.name}: invalid direction")
        passed = len(issues) == 0
        reason = f"{len(l2.drivers)} drivers checked"
        if issues:
            reason += f". Issues: {'; '.join(issues[:5])}"
        return GateResult(gate_name="DriverBinding", passed=passed, reason=reason)

    # ── Feedback Completeness ─────────────────────────
    def validate_feedback_completeness(self, l3: FlowFeedbackSystem) -> GateResult:
        loops = l3.feedback_loops
        issues = []
        if len(loops) < 3:
            issues.append(f"only {len(loops)} loops (min 3)")
        if not any(l.type == "reinforcing" for l in loops):
            issues.append("no reinforcing loop")
        if not any(l.type == "balancing" for l in loops):
            issues.append("no balancing loop")
        passed = len(issues) == 0
        reason = f"{len(loops)} loops"
        if issues:
            reason += f". Issues: {'; '.join(issues)}"
        return GateResult(gate_name="FeedbackCompleteness", passed=passed, reason=reason)

    # ── Regime Validation ─────────────────────────────
    def validate_regime(self, l4: RegimeEngine) -> GateResult:
        valid = l4.current_regime in VALID_REGIMES
        valid_next = l4.transition_probability.next_regime in VALID_REGIMES
        passed = valid and valid_next
        reason = f"Regime: {l4.current_regime}, next: {l4.transition_probability.next_regime}"
        if not valid:
            reason += " — invalid current_regime"
        if not valid_next:
            reason += " — invalid next_regime"
        return GateResult(gate_name="RegimeValidation", passed=passed, reason=reason)

    # ── Distortion Validation ─────────────────────────
    def validate_distortion(self, l5: DistortionEngine) -> GateResult:
        issues = []
        if not l5.market_belief or len(l5.market_belief.strip()) < 10:
            issues.append("market_belief too short")
        if not l5.structural_truth or len(l5.structural_truth.strip()) < 10:
            issues.append("structural_truth too short")
        if len(l5.mispricing_sources) == 0:
            issues.append("no mispricing_sources")
        passed = len(issues) == 0
        reason = f"score={l5.distortion_score:.2f}, sources={len(l5.mispricing_sources)}"
        if issues:
            reason += f". Issues: {'; '.join(issues)}"
        return GateResult(gate_name="DistortionValidation", passed=passed, reason=reason)

    # ── Alpha Completeness ────────────────────────────
    def validate_alpha_completeness(self, l6: AlphaEngine) -> GateResult:
        fields = {"consensus_view": l6.consensus_view, "structural_view": l6.structural_view,
                  "mispricing": l6.mispricing, "alpha_signal": l6.alpha_signal}
        too_short = [n for n, v in fields.items() if not v or len(v.strip()) < 10]
        valid_dir = l6.direction in ("long", "short", "neutral")
        passed = len(too_short) == 0 and valid_dir
        reason = f"direction={l6.direction}{'✓' if valid_dir else '✗'}, confidence={l6.confidence:.2f}"
        if too_short:
            reason += f". Too short: {', '.join(too_short)}"
        return GateResult(gate_name="AlphaCompleteness", passed=passed, reason=reason)

    # ── De-entity Check ───────────────────────────────
    def validate_de_entity(self, l1: VariableMapping) -> GateResult:
        all_vars = (l1.state_variables + l1.flow_variables + l1.control_variables + l1.latent_variables)
        company_patterns = [r'\b(Inc|Corp|Ltd|LLC|Co\.|AG|SA|NV|PLC|GmbH|Group|Holdings?)\b']
        company_like = [v for v in all_vars if any(re.search(p, v) for p in company_patterns)]
        passed = len(company_like) == 0
        reason = f"{len(all_vars)} variables checked"
        if company_like:
            reason += f". Possible companies: {', '.join(company_like[:5])}"
        return GateResult(gate_name="DeEntityCheck", passed=passed, reason=reason)

    # ── De-narrative Check ────────────────────────────
    def validate_de_narrative(self, l1: VariableMapping) -> GateResult:
        narrative_kw = ["narrative", "story", "hype", "buzz", "sentiment"]
        misplaced = [v for v in (l1.state_variables + l1.flow_variables + l1.control_variables)
                     if any(kw in v.lower() for kw in narrative_kw)]
        passed = len(misplaced) == 0
        reason = "Narrative confined to LV" if passed else f"Narrative in SV/FV/CV: {', '.join(misplaced[:5])}"
        return GateResult(gate_name="DeNarrativeCheck", passed=passed, reason=reason)

    # ── Cross-Layer Binding (CRITICAL V2.2) ───────────
    @staticmethod
    def _strip_parenthetical(text: str) -> str:
        return re.sub(r'[（(].*?[)）]', '', text).strip()

    @staticmethod
    def _extract_tokens(text: str) -> set[str]:
        """Extract tokens for fuzzy matching.

        For English: split by spaces and delimiters.
        For Chinese: also extract 2-character bigrams (since Chinese has no spaces).
        """
        cleaned = OutputValidator._strip_parenthetical(text).lower()
        tokens = set()
        # Standard token splitting (works for English and mixed text)
        for part in re.split(r'[\s,，、；;/]+', cleaned):
            part = part.strip()
            if len(part) >= 2:
                tokens.add(part)
        # Chinese bigram extraction: extract all 2-char substrings from Chinese text
        # This allows matching '代币化现实世界资产增速' with '代币化现实世界资产（RWA）增速'
        # by sharing bigrams like '代币', '币化', '现实', '世界', '资产', '增速'
        zh_segments = re.findall(r'[\u4e00-\u9fff]+', cleaned)
        for seg in zh_segments:
            if len(seg) >= 2:
                for i in range(len(seg) - 1):
                    tokens.add(seg[i:i+2])
        return tokens

    def validate_cross_layer_binding(
        self, l1: VariableMapping, l2: DriverSpace, l5: DistortionEngine,
        l6: AlphaEngine, l7: Optional[InvestmentMapping] = None,
    ) -> GateResult:
        """V2.2 CRITICAL: Every L5/L6 statement MUST trace to ≥1 L2 driver + ≥1 L1 variable."""
        all_l1_vars = [v.lower() for v in (l1.state_variables + l1.flow_variables + l1.control_variables + l1.latent_variables)]
        all_l1_tokens = [self._extract_tokens(v) for v in all_l1_vars]
        all_l2_names = [d.name.lower() for d in l2.drivers]
        all_l2_tokens = [self._extract_tokens(d.name) for d in l2.drivers]

        def check_binding(text: str) -> tuple[bool, bool]:
            """Returns (traces_to_l1, traces_to_l2).
            Uses fuzzy matching: substring + token overlap + Chinese bigram overlap.
            """
            text_lower = text.lower()
            text_stripped = OutputValidator._strip_parenthetical(text_lower)
            text_tokens = OutputValidator._extract_tokens(text)
            # Check L1: substring match (including stripped), then token/bigram overlap
            traces_l1 = any(text_lower in v or v in text_lower for v in all_l1_vars)
            if not traces_l1 and text_stripped:
                traces_l1 = any(text_stripped in OutputValidator._strip_parenthetical(v) or
                               OutputValidator._strip_parenthetical(v) in text_stripped
                               for v in all_l1_vars)
            if not traces_l1 and text_tokens:
                for v, tokens in zip(all_l1_vars, all_l1_tokens):
                    if tokens and (text_tokens & tokens):
                        traces_l1 = True
                        break
            # Check L2: same approach
            traces_l2 = any(text_lower in n or n in text_lower for n in all_l2_names)
            if not traces_l2 and text_stripped:
                traces_l2 = any(text_stripped in OutputValidator._strip_parenthetical(n) or
                               OutputValidator._strip_parenthetical(n) in text_stripped
                               for n in all_l2_names)
            if not traces_l2 and text_tokens:
                for n, tokens in zip(all_l2_names, all_l2_tokens):
                    if tokens and (text_tokens & tokens):
                        traces_l2 = True
                        break
            return traces_l1, traces_l2

        # Check L5 mispricing_sources
        unbound = []
        for src in l5.mispricing_sources:
            t1, t2 = check_binding(src)
            if not t1 or not t2:
                unbound.append(f"L5:'{src[:40]}' (L1={'✓' if t1 else '✗'}, L2={'✓' if t2 else '✗'})")

        # Check L6 alpha_signal
        t1, t2 = check_binding(l6.alpha_signal)
        if not t1 or not t2:
            unbound.append(f"L6:alpha_signal (L1={'✓' if t1 else '✗'}, L2={'✓' if t2 else '✗'})")

        passed = len(unbound) == 0
        reason = "All L5/L6 statements trace to L1+L2" if passed else f"{len(unbound)} unbound: {'; '.join(unbound[:3])}"
        return GateResult(gate_name="CrossLayerBinding", passed=passed, reason=reason)

    # ── L6-L7 Consistency (V2.2 fix) ──────────────────────
    def validate_l7_consistency(
        self, l6: AlphaEngine, l7: Optional[InvestmentMapping] = None,
    ) -> GateResult:
        """Check L7 investment mapping is consistent with L6 alpha direction.

        - If L6 is 'long': best_positioned should have assets, overvalued should have short candidates
        - If L6 is 'short': overvalued should have assets to short, best_positioned should have hedge/short candidates
        - If L6 is 'neutral': no strong direction constraint
        """
        if not l7:
            return GateResult(gate_name="L7Consistency", passed=True, reason="L7 not generated (optional)")

        direction = l6.direction
        issues = []

        if direction == "long":
            # best_positioned should exist (long candidates)
            if len(l7.best_positioned) == 0:
                issues.append("L6=long but no best_positioned assets")
            # overvalued should exist (short candidates / avoid)
            if len(l7.overvalued) == 0:
                issues.append("L6=long but no overvalued assets to avoid")
        elif direction == "short":
            # overvalued should exist (short candidates)
            if len(l7.overvalued) == 0:
                issues.append("L6=short but no overvalued assets to short")

        # Check risk_profile is not empty for best_positioned
        empty_risk = [a.asset for a in l7.best_positioned if not a.risk_profile or len(a.risk_profile.strip()) < 5]
        if empty_risk:
            issues.append(f"Empty risk_profile: {', '.join(empty_risk[:3])}")

        passed = len(issues) == 0
        reason = f"L6={direction}, L7: best={len(l7.best_positioned)}, overvalued={len(l7.overvalued)}, fragile={len(l7.fragile)}"
        if issues:
            reason += f". Issues: {'; '.join(issues)}"
        return GateResult(gate_name="L7Consistency", passed=passed, reason=reason)

    # ── Run All ────────────────────────────────────────
    def run_all_validations(
        self, l1: VariableMapping, l2: DriverSpace, l3: FlowFeedbackSystem,
        l4: RegimeEngine, l5: DistortionEngine, l6: AlphaEngine,
        l7: Optional[InvestmentMapping] = None,
    ) -> list[GateResult]:
        results = [
            self.validate_variable_completeness(l1),
            self.validate_driver_binding(l2),
            self.validate_feedback_completeness(l3),
            self.validate_regime(l4),
            self.validate_distortion(l5),
            self.validate_alpha_completeness(l6),
            self.validate_de_entity(l1),
            self.validate_de_narrative(l1),
            self.validate_cross_layer_binding(l1, l2, l5, l6, l7),
            self.validate_l7_consistency(l6, l7),
        ]
        return results
