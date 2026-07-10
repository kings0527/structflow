"""Stable profile-to-layer coverage bindings without semantic text guessing."""

from __future__ import annotations

from structflow.input_resolver import EntityProfile, InputKind
from structflow.models import (
    DriverSpace,
    GateResult,
    MetaSystemDefinition,
    VariableMapping,
)


def segment_id(index: int) -> str:
    return f"SEG-{index + 1:03d}"


def dimension_id(index: int) -> str:
    return f"DIM-{index + 1:03d}"


def expected_segment_ids(profile: EntityProfile) -> list[str]:
    if profile.input_kind != InputKind.COMPANY:
        return []
    return [segment_id(index) for index, _ in enumerate(profile.material_segments)]


def expected_dimension_ids(profile: EntityProfile) -> list[str]:
    if profile.input_kind != InputKind.COMPANY:
        return []
    return [
        dimension_id(index)
        for index, _ in enumerate(profile.required_system_dimensions)
    ]


def coverage_contract(profile: EntityProfile) -> str:
    if profile.input_kind != InputKind.COMPANY:
        return ""
    lines = [
        "## Binding Coverage Contract",
        "Return the exact IDs below in covered_segment_ids and covered_dimension_ids.",
        "An ID means the item is explicitly represented, not merely mentioned in prose.",
        "",
        "Material segments:",
    ]
    lines.extend(
        f"- {segment_id(index)}: {segment.name}"
        for index, segment in enumerate(profile.material_segments)
    )
    lines.append("Required system dimensions:")
    lines.extend(
        f"- {dimension_id(index)}: {name}"
        for index, name in enumerate(profile.required_system_dimensions)
    )
    return "\n".join(lines)


class CoverageValidator:
    @staticmethod
    def _validate(
        gate_name: str,
        actual_segments: list[str],
        actual_dimensions: list[str],
        profile: EntityProfile,
    ) -> GateResult:
        expected_segments = set(expected_segment_ids(profile))
        expected_dimensions = set(expected_dimension_ids(profile))
        if not expected_segments and not expected_dimensions:
            return GateResult(
                gate_name=gate_name,
                passed=True,
                reason="Coverage contract not required for this input kind",
            )
        actual_segment_set = set(actual_segments)
        actual_dimension_set = set(actual_dimensions)
        missing_segments = sorted(expected_segments - actual_segment_set)
        missing_dimensions = sorted(expected_dimensions - actual_dimension_set)
        unknown = sorted(
            (actual_segment_set - expected_segments)
            | (actual_dimension_set - expected_dimensions)
        )
        passed = not missing_segments and not missing_dimensions and not unknown
        reason = (
            f"segments={len(actual_segment_set)}/{len(expected_segments)}; "
            f"dimensions={len(actual_dimension_set)}/{len(expected_dimensions)}"
        )
        if missing_segments:
            reason += f"; missing segments={missing_segments}"
        if missing_dimensions:
            reason += f"; missing dimensions={missing_dimensions}"
        if unknown:
            reason += f"; unknown IDs={unknown}"
        return GateResult(gate_name=gate_name, passed=passed, reason=reason)

    def validate_l0(
        self, value: MetaSystemDefinition, profile: EntityProfile
    ) -> GateResult:
        return self._validate(
            "Hard_MaterialSegmentCoverage",
            value.covered_segment_ids,
            value.covered_dimension_ids,
            profile,
        )

    def validate_l1(
        self, value: VariableMapping, profile: EntityProfile
    ) -> GateResult:
        return self._validate(
            "Hard_VariableSegmentCoverage",
            value.covered_segment_ids,
            value.covered_dimension_ids,
            profile,
        )

    def validate_l2(
        self, value: DriverSpace, profile: EntityProfile
    ) -> GateResult:
        return self._validate(
            "Hard_DriverSegmentCoverage",
            value.covered_segment_ids,
            value.covered_dimension_ids,
            profile,
        )
