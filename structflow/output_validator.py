"""Output validation: cross-check LLM output against collected data and across layers.

V2: validates L0-L7 with updated role types, 4 flows, driver weights,
scenario probabilities, and alpha completeness.
"""

from __future__ import annotations

import re
from typing import Optional

from structflow.models import (
    GateResult,
    L1StructureDecomposition,
    L2FlowAnalysis,
    L3RiskAnalysis,
    L4DriverAnalysis,
    L5ScenarioAnalysis,
    L6AlphaAnalysis,
    L7PortfolioMapping,
)


# V2 role types (5 roles)
V2_ROLE_TYPES = ("producer", "consumer", "mediator", "controller", "capital")


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

    @staticmethod
    def _is_named_entity(entity: str) -> bool:
        """Check if an entity is a specific named entity vs a generic role description.

        Heuristic (language-agnostic):
        - If the entity contains Latin alphabet characters of length >= 3,
          it is likely a proper noun that should be grounded in search data.
        - If the entity is purely non-Latin (CJK, etc.) with no Latin
          component, it may be a generic role description or non-English
          proper noun. In both cases, requiring verbatim appearance in
          English search results is unreasonable, so it is auto-grounded.
        """
        return bool(re.search(r'[a-zA-Z]{3,}', entity))

    def validate_entities_mentioned(
        self,
        l1: L1StructureDecomposition,
    ) -> GateResult:
        """Check if identified entities are mentioned in collected data.

        Two-tier grounding:
        - Named entities (contain Latin chars >= 3): must be grounded at >= 70%.
        - Non-named entities (pure CJK or generic descriptions): auto-grounded.
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

        named_entities = []
        generic_entities = []
        for entity in all_entities:
            if self._is_named_entity(entity):
                named_entities.append(entity)
            else:
                generic_entities.append(entity)

        mentioned = 0
        not_mentioned = []
        for entity in named_entities:
            entity_lower = entity.lower()
            entity_words = entity_lower.split()
            if entity_lower in self._all_text:
                mentioned += 1
            elif any(word in self._all_text for word in entity_words if len(word) > 2):
                mentioned += 1
            else:
                not_mentioned.append(entity)

        mentioned += len(generic_entities)
        total = len(all_entities)
        named_total = len(named_entities)
        grounding_ratio = mentioned / total if total > 0 else 0
        passed = grounding_ratio >= 0.7

        reason = (
            f"{mentioned}/{total} entities grounded ({grounding_ratio:.0%}): "
            f"{named_total} named, {len(generic_entities)} generic (auto-grounded)"
        )
        if not_mentioned:
            reason += f". Named not found: {', '.join(not_mentioned[:5])}"

        return GateResult(gate_name="EntityGrounding", passed=passed, reason=reason)

    # ── Role Diversity ────────────────────────────────────────────

    @staticmethod
    def _extract_role_types(role_str: str) -> set[str]:
        """Extract ALL role types from a free-form role string.

        V2 includes 5 role types: producer, consumer, mediator, controller, capital.
        """
        role_lower = role_str.lower()
        found: set[str] = set()
        for role_type in V2_ROLE_TYPES:
            if role_type in role_lower:
                found.add(role_type)
        return found

    def validate_role_diversity(
        self,
        l1: L1StructureDecomposition,
        l7: Optional[L7PortfolioMapping] = None,
    ) -> GateResult:
        """Check that portfolio mapping covers at least 3 different role types.

        This prevents the LLM from only mapping entities from one role segment.
        The threshold is derived from L1's own role structure.
        """
        l1_role_count = len(l1.roles)
        min_roles = min(3, l1_role_count)

        scored_roles: set[str] = set()
        if l7:
            for entity in l7.best_positioned_entities + l7.overvalued_entities + l7.fragile_entities:
                role_types = self._extract_role_types(entity.role)
                scored_roles.update(role_types)

        passed = len(scored_roles) >= min_roles
        reason = (
            f"Portfolio covers {len(scored_roles)}/{l1_role_count} role types: "
            f"{', '.join(sorted(scored_roles)) if scored_roles else 'none'}. "
            f"Minimum required: {min_roles}"
        )
        if not passed:
            missing = set(r.role_type.lower() for r in l1.roles) - scored_roles
            reason += f". Missing: {', '.join(sorted(missing))}"

        return GateResult(gate_name="RoleDiversity", passed=passed, reason=reason)

    # ── Flow Completeness ─────────────────────────────────────────

    def validate_flow_completeness(
        self,
        l2: L2FlowAnalysis,
    ) -> GateResult:
        """Check if all 4 flows are substantive (not trivially short)."""
        cash = len(l2.cash_nodes)
        info = len(l2.information_nodes)
        risk = len(l2.risk_nodes)
        attention = len(l2.attention_nodes)

        passed = cash >= 2 and info >= 2 and risk >= 1 and attention >= 1
        reason = (
            f"Cash: {cash}, Info: {info}, Risk: {risk}, Attention: {attention}"
        )
        if not passed:
            reason += " — flow analysis too shallow"

        return GateResult(gate_name="FlowCompleteness", passed=passed, reason=reason)

    # ── Role Attribution ──────────────────────────────────────────

    def validate_role_attribution(
        self,
        l1: L1StructureDecomposition,
    ) -> GateResult:
        """Check that power matrix attributes to specific roles, not vague statements."""
        power = l1.power_matrix
        power_fields = [
            power.pricing_power, power.entry_power, power.standard_power,
            power.capital_power, power.data_power,
        ]

        vague_count = 0
        for field in power_fields:
            field_lower = field.lower()
            has_role_ref = any(role in field_lower for role in V2_ROLE_TYPES)
            if not has_role_ref:
                vague_count += 1

        passed = vague_count == 0
        reason = (
            f"All {len(power_fields)} power dimensions attributed to specific roles"
            if passed
            else f"{vague_count}/{len(power_fields)} power dimensions lack role attribution"
        )

        return GateResult(gate_name="RoleAttribution", passed=passed, reason=reason)

    # ── Driver Weights ────────────────────────────────────────────

    def validate_driver_weights(
        self,
        l4: L4DriverAnalysis,
    ) -> GateResult:
        """Check that driver importance weights sum to approximately 1.0."""
        total = sum(d.importance for d in l4.drivers)
        passed = abs(total - 1.0) < 0.05
        reason = (
            f"Driver weights sum: {total:.2f} ({len(l4.drivers)} drivers)"
            if passed
            else f"Driver weights sum: {total:.2f} — should be 1.0 (tolerance: 0.05)"
        )
        return GateResult(gate_name="DriverWeights", passed=passed, reason=reason)

    # ── Scenario Probabilities ────────────────────────────────────

    def validate_scenario_probabilities(
        self,
        l5: L5ScenarioAnalysis,
    ) -> GateResult:
        """Check that scenario probabilities sum to approximately 1.0."""
        total = l5.bull.probability + l5.base.probability + l5.bear.probability
        passed = abs(total - 1.0) < 0.05
        reason = (
            f"Bull={l5.bull.probability:.0%}, Base={l5.base.probability:.0%}, "
            f"Bear={l5.bear.probability:.0%} (sum={total:.2f})"
        )
        if not passed:
            reason += f" — should sum to 1.0"
        return GateResult(gate_name="ScenarioProbabilities", passed=passed, reason=reason)

    # ── Alpha Completeness ────────────────────────────────────────

    def validate_alpha_completeness(
        self,
        l6: L6AlphaAnalysis,
    ) -> GateResult:
        """Check that all 4 alpha components are substantive."""
        fields = {
            "consensus": l6.consensus,
            "reality": l6.reality,
            "mispricing": l6.mispricing,
            "alpha_thesis": l6.alpha_thesis,
        }
        too_short = [name for name, value in fields.items() if not value or len(value.strip()) < 10]
        passed = len(too_short) == 0
        reason = (
            "All 4 alpha components present and substantive"
            if passed
            else f"Too short or missing: {', '.join(too_short)}"
        )
        return GateResult(gate_name="AlphaCompleteness", passed=passed, reason=reason)

    # ── Cross-Layer Consistency ───────────────────────────────────

    def validate_cross_layer_consistency(
        self,
        l1: L1StructureDecomposition,
        l2: L2FlowAnalysis,
        l3: L3RiskAnalysis,
        l7: Optional[L7PortfolioMapping] = None,
    ) -> GateResult:
        """Check that entities referenced in L2/L3/L7 exist in L1's role entities."""
        l1_entity_lower = set()
        for role in l1.roles:
            for entity in role.entities:
                l1_entity_lower.add(entity.lower())

        # Collect L2 flow entities
        l2_entities = set()
        for flow_list in (l2.cash_nodes, l2.information_nodes, l2.risk_nodes, l2.attention_nodes):
            for node in flow_list:
                l2_entities.add(node.entity)

        # Collect L3 risk entities
        l3_entities = set()
        for rc in l3.risk_concentrations:
            l3_entities.add(rc.entity)
        l3_entities.add(l3.profit_risk_separation.profit_owner)
        l3_entities.add(l3.profit_risk_separation.risk_owner)

        # Collect L7 portfolio entities
        l7_entities = set()
        if l7:
            for entity in l7.best_positioned_entities + l7.overvalued_entities + l7.fragile_entities:
                l7_entities.add(entity.name)

        def check_orphans(entities, l1_set):
            orphans = []
            for entity in entities:
                entity_lower = entity.lower()
                matched = any(
                    entity_lower in l1_e or l1_e in entity_lower
                    for l1_e in l1_set
                )
                if not matched:
                    orphans.append(entity)
            return orphans

        l2_orphan = check_orphans(l2_entities, l1_entity_lower)
        l3_orphan = check_orphans(l3_entities, l1_entity_lower)
        l7_orphan = check_orphans(l7_entities, l1_entity_lower) if l7 else []

        total_orphan = len(l2_orphan) + len(l3_orphan) + len(l7_orphan)
        passed = total_orphan == 0

        reason_parts = []
        if l2_orphan:
            reason_parts.append(f"L2 orphans: {', '.join(l2_orphan[:5])}")
        if l3_orphan:
            reason_parts.append(f"L3 orphans: {', '.join(l3_orphan[:5])}")
        if l7_orphan:
            reason_parts.append(f"L7 orphans: {', '.join(l7_orphan[:5])}")
        if not reason_parts:
            reason_parts.append("All L2/L3/L7 entities traceable to L1 roles")

        return GateResult(
            gate_name="CrossLayerConsistency",
            passed=passed,
            reason="; ".join(reason_parts),
        )

    # ── Run All ───────────────────────────────────────────────────

    def run_all_validations(
        self,
        l1: L1StructureDecomposition,
        l2: L2FlowAnalysis,
        l3: L3RiskAnalysis,
        l4: Optional[L4DriverAnalysis] = None,
        l5: Optional[L5ScenarioAnalysis] = None,
        l6: Optional[L6AlphaAnalysis] = None,
        l7: Optional[L7PortfolioMapping] = None,
    ) -> list[GateResult]:
        """Run all validation checks and return results."""
        results = [
            self.validate_entities_mentioned(l1),
            self.validate_flow_completeness(l2),
            self.validate_role_attribution(l1),
            self.validate_cross_layer_consistency(l1, l2, l3, l7),
        ]
        if l4:
            results.append(self.validate_driver_weights(l4))
        if l5:
            results.append(self.validate_scenario_probabilities(l5))
        if l6:
            results.append(self.validate_alpha_completeness(l6))
        if l7:
            results.append(self.validate_role_diversity(l1, l7))
        return results
