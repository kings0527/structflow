"""Output validation: cross-check LLM output against collected data."""

from __future__ import annotations

import re
from typing import Optional

from structflow.models import (
    GateResult,
    L1StructureDecomposition,
    L2FlowRiskAnalysis,
    L3ScoringRanking,
)


class OutputValidator:
    """Validates LLM output quality by cross-referencing with collected data."""

    def __init__(self, collected_data: Optional[dict[str, str]] = None):
        self.collected_data = collected_data or {}
        self._all_text = self._flatten_data()

    def _flatten_data(self) -> str:
        """Flatten all collected data into a single searchable string."""
        parts = []
        for key, value in self.collected_data.items():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    parts.append(f"{sub_key}: {sub_value}")
        return " ".join(parts).lower()

    def validate_entities_mentioned(
        self,
        l1: L1StructureDecomposition,
    ) -> GateResult:
        """Check if identified entities are mentioned in collected data."""
        if not self._all_text:
            return GateResult(
                gate_name="EntityGrounding",
                passed=True,
                reason="No collected data to validate against (LLM-only mode)",
            )

        all_entities = []
        for role in l1.roles:
            all_entities.extend(role.entities)

        mentioned = 0
        not_mentioned = []
        for entity in all_entities:
            entity_lower = entity.lower()
            # Check if any part of the entity name appears in collected data
            entity_words = entity_lower.split()
            if any(word in self._all_text for word in entity_words if len(word) > 3):
                mentioned += 1
            else:
                not_mentioned.append(entity)

        total = len(all_entities)
        grounding_ratio = mentioned / total if total > 0 else 0
        passed = grounding_ratio >= 0.5

        reason = (
            f"{mentioned}/{total} entities grounded in collected data ({grounding_ratio:.0%})"
        )
        if not_mentioned:
            reason += f". Not found: {', '.join(not_mentioned[:5])}"

        return GateResult(gate_name="EntityGrounding", passed=passed, reason=reason)

    def validate_score_range(
        self,
        l3: L3ScoringRanking,
    ) -> GateResult:
        """Check if scores are within reasonable ranges and not all identical."""
        industry_scores = [
            l3.industry_score.control_score,
            l3.industry_score.profit_capture_score,
            l3.industry_score.risk_displacement_score,
            l3.industry_score.information_advantage_score,
            l3.industry_score.incentive_alignment_score,
        ]

        # Check for degenerate scores (all same value = LLM didn't think)
        unique_scores = len(set(industry_scores))
        all_same = unique_scores <= 1

        # Check for extreme scores (all 0 or all 10 = LLM didn't differentiate)
        all_extreme = all(s in (0, 10) for s in industry_scores)

        # Check company score variance
        company_health_scores = [c.structural_health for c in l3.companies_ranked]
        health_variance = 0.0
        if len(company_health_scores) > 1:
            mean_health = sum(company_health_scores) / len(company_health_scores)
            health_variance = sum((h - mean_health) ** 2 for h in company_health_scores) / len(company_health_scores)

        passed = not all_same and not all_extreme and health_variance > 0.1
        reason = (
            f"Score diversity: {unique_scores} unique values, "
            f"health variance: {health_variance:.2f}, "
            f"companies ranked: {len(l3.companies_ranked)}"
        )
        if all_same:
            reason += " ⚠ All scores identical — possible LLM laziness"
        if all_extreme:
            reason += " ⚠ All scores extreme (0 or 10) — possible LLM hallucination"

        return GateResult(gate_name="ScoreQuality", passed=passed, reason=reason)

    def validate_flow_completeness(
        self,
        l2: L2FlowRiskAnalysis,
    ) -> GateResult:
        """Check if flow chains are substantive (not trivially short)."""
        cash_nodes = len(l2.cash_flow_chain)
        info_nodes = len(l2.information_asymmetry_nodes)
        risk_nodes = len(l2.risk_accumulation_points)
        value_nodes = len(l2.value_capture_points)

        # Minimum thresholds for meaningful analysis
        min_cash = 2
        min_info = 2
        min_risk = 1
        min_value = 1

        passed = (
            cash_nodes >= min_cash
            and info_nodes >= min_info
            and risk_nodes >= min_risk
            and value_nodes >= min_value
        )

        reason = (
            f"Cash flow: {cash_nodes} nodes, "
            f"Info asymmetry: {info_nodes} nodes, "
            f"Risk points: {risk_nodes}, "
            f"Value capture: {value_nodes}"
        )
        if not passed:
            reason += " ⚠ Flow analysis too shallow"

        return GateResult(gate_name="FlowCompleteness", passed=passed, reason=reason)

    def validate_role_attribution(
        self,
        l1: L1StructureDecomposition,
    ) -> GateResult:
        """Check that power matrix attributes to specific roles, not vague statements."""
        power = l1.power_matrix
        power_fields = [
            power.pricing_power,
            power.entry_control,
            power.data_control,
            power.switching_cost,
            power.standard_control,
        ]

        role_keywords = {"producer", "payer", "mediator", "controller"}
        vague_count = 0
        for field in power_fields:
            field_lower = field.lower()
            has_role_ref = any(role in field_lower for role in role_keywords)
            if not has_role_ref:
                vague_count += 1

        passed = vague_count == 0
        reason = (
            f"All {len(power_fields)} power dimensions attributed to specific roles"
            if passed
            else f"{vague_count}/{len(power_fields)} power dimensions lack role attribution"
        )

        return GateResult(gate_name="RoleAttribution", passed=passed, reason=reason)

    def run_all_validations(
        self,
        l1: L1StructureDecomposition,
        l2: L2FlowRiskAnalysis,
        l3: L3ScoringRanking,
    ) -> list[GateResult]:
        """Run all validation checks and return results."""
        return [
            self.validate_entities_mentioned(l1),
            self.validate_score_range(l3),
            self.validate_flow_completeness(l2),
            self.validate_role_attribution(l1),
        ]
