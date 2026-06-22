"""Output validation: cross-check LLM output against collected data and across layers."""

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
    """Validates LLM output quality by cross-referencing with collected data
    and checking consistency across analysis layers."""

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

    # ── Entity Grounding ──────────────────────────────────────────

    def validate_entities_mentioned(
        self,
        l1: L1StructureDecomposition,
    ) -> GateResult:
        """Check if identified entities are mentioned in collected data.

        Tightened rules:
        - Threshold raised from 50% to 70%.
        - Word-length filter lowered from >3 to >2 (catches 'AWS', 'GCP').
        - In LLM-only mode (no data), still passes but with a warning.
        """
        if not self._all_text:
            return GateResult(
                gate_name="EntityGrounding",
                passed=True,
                reason="No collected data to validate against (LLM-only mode) — grounding not verified",
            )

        all_entities = []
        for role in l1.roles:
            all_entities.extend(role.entities)

        mentioned = 0
        not_mentioned = []
        for entity in all_entities:
            entity_lower = entity.lower()
            entity_words = entity_lower.split()
            # Match if the full entity name appears, or any word (len > 2) appears
            if entity_lower in self._all_text:
                mentioned += 1
            elif any(word in self._all_text for word in entity_words if len(word) > 2):
                mentioned += 1
            else:
                not_mentioned.append(entity)

        total = len(all_entities)
        grounding_ratio = mentioned / total if total > 0 else 0
        passed = grounding_ratio >= 0.7  # raised from 0.5

        reason = (
            f"{mentioned}/{total} entities grounded in collected data ({grounding_ratio:.0%})"
        )
        if not_mentioned:
            reason += f". Not found: {', '.join(not_mentioned[:5])}"

        return GateResult(gate_name="EntityGrounding", passed=passed, reason=reason)

    # ── Score Quality ─────────────────────────────────────────────

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

        # Check for duplicate company scores (all companies identical)
        company_score_tuples = []
        for c in l3.companies_ranked:
            sv = c.score_vector
            company_score_tuples.append((
                sv.control_score, sv.profit_capture_score,
                sv.risk_displacement_score, sv.information_advantage_score,
                sv.incentive_alignment_score,
            ))
        all_companies_same = len(set(company_score_tuples)) <= 1 and len(company_score_tuples) > 1

        passed = not all_same and not all_extreme and health_variance > 0.1 and not all_companies_same
        reason = (
            f"Score diversity: {unique_scores} unique industry values, "
            f"health variance: {health_variance:.2f}, "
            f"companies ranked: {len(l3.companies_ranked)}, "
            f"unique company score sets: {len(set(company_score_tuples))}"
        )
        if all_same:
            reason += " ⚠ All scores identical — possible LLM laziness"
        if all_extreme:
            reason += " ⚠ All scores extreme (0 or 10) — possible LLM hallucination"
        if all_companies_same:
            reason += " ⚠ All companies have identical score vectors — no differentiation"

        return GateResult(gate_name="ScoreQuality", passed=passed, reason=reason)

    # ── Flow Completeness ─────────────────────────────────────────

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

    # ── Role Attribution ──────────────────────────────────────────

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

    # ── Cross-Layer Consistency ───────────────────────────────────

    def validate_cross_layer_consistency(
        self,
        l1: L1StructureDecomposition,
        l2: L2FlowRiskAnalysis,
        l3: L3ScoringRanking,
    ) -> GateResult:
        """Check that entities referenced in L2/L3 exist in L1's role entities.

        This catches hallucinated entities that appear in later layers but were
        never identified in the structure decomposition.
        """
        # Collect all L1 entities
        l1_entities = set()
        l1_entity_lower = set()
        for role in l1.roles:
            for entity in role.entities:
                l1_entities.add(entity)
                l1_entity_lower.add(entity.lower())

        # Collect L2 flow entities
        l2_entities = set()
        for flow_list in (
            l2.cash_flow_chain,
            l2.value_capture_points,
            l2.information_asymmetry_nodes,
            l2.risk_accumulation_points,
            l2.hidden_subsidy_sources,
        ):
            for node in flow_list:
                l2_entities.add(node.entity)

        # Collect L3 company names
        l3_entities = set()
        for company in l3.companies_ranked:
            l3_entities.add(company.name)

        # Check L2 entities against L1 (allow partial match — L2 may use
        # shortened names or role descriptions)
        l2_orphan = []
        for entity in l2_entities:
            entity_lower = entity.lower()
            # Check if any L1 entity is a substring of this L2 entity or vice versa
            matched = any(
                entity_lower in l1_e or l1_e in entity_lower
                for l1_e in l1_entity_lower
            )
            if not matched:
                l2_orphan.append(entity)

        # Check L3 companies against L1
        l3_orphan = []
        for entity in l3_entities:
            entity_lower = entity.lower()
            matched = any(
                entity_lower in l1_e or l1_e in entity_lower
                for l1_e in l1_entity_lower
            )
            if not matched:
                l3_orphan.append(entity)

        total_orphan = len(l2_orphan) + len(l3_orphan)
        passed = total_orphan == 0

        reason_parts = []
        if l2_orphan:
            reason_parts.append(f"L2 orphans: {', '.join(l2_orphan[:5])}")
        if l3_orphan:
            reason_parts.append(f"L3 orphans: {', '.join(l3_orphan[:5])}")
        if not reason_parts:
            reason_parts.append("All L2/L3 entities traceable to L1 roles")

        return GateResult(
            gate_name="CrossLayerConsistency",
            passed=passed,
            reason="; ".join(reason_parts),
        )

    # ── Run All ───────────────────────────────────────────────────

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
            self.validate_cross_layer_consistency(l1, l2, l3),
        ]
