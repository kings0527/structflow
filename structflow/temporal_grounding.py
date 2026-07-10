"""Structured validation for point-in-time market claims."""

from __future__ import annotations

import re
from datetime import date

from structflow.input_resolver import EntityProfile
from structflow.models import AlphaEngine, GateResult
from structflow.research_clock import coerce_date, normalize_analysis_date


PRICE_CLAIM = re.compile(
    r"(?:当前|现时|最新)?(?:股价|价格|收盘(?:价)?)"
    r"[\s\S]{0,60}?(\d+(?:\.\d+)?)\s*元"
    r"|(?:current|latest|closing|close|share)\s+price"
    r"[\s\S]{0,40}?(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class TemporalGroundingValidator:
    def validate_alpha(
        self,
        alpha: AlphaEngine,
        profile: EntityProfile,
        as_of: str | date | None,
    ) -> GateResult:
        text = " ".join((
            alpha.consensus_view,
            alpha.structural_view,
            alpha.mispricing,
            alpha.alpha_signal,
        ))
        prose_price = PRICE_CLAIM.search(text)
        has_structured = alpha.observed_price is not None
        if prose_price and not has_structured:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason=(
                    "Price appears in prose but observed_price, price_as_of, "
                    "and price_evidence_ids are missing"
                ),
            )
        if not prose_price and not has_structured:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=True,
                reason="No observed-price claim emitted",
            )

        snapshot = profile.market_snapshot
        if snapshot is None:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason="Observed-price claim has no consensus market snapshot",
            )
        if not alpha.price_as_of or not alpha.price_evidence_ids:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason="Structured price is missing date or evidence IDs",
            )
        claim_date = coerce_date(alpha.price_as_of)
        snapshot_date = coerce_date(snapshot.as_of)
        cutoff = normalize_analysis_date(as_of)
        if claim_date is None or claim_date > cutoff:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason="Price observation date is invalid or after cutoff",
            )
        if snapshot_date is None or abs((claim_date - snapshot_date).days) > 3:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason="Price date does not match consensus snapshot",
            )
        relative_error = abs(alpha.observed_price - snapshot.price) / snapshot.price
        if relative_error > 0.01:
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason=(
                    f"Observed price {alpha.observed_price:g} conflicts with "
                    f"snapshot {snapshot.price:g}"
                ),
            )
        snapshot_ids = set(snapshot.source_ids or [snapshot.source_id])
        claim_ids = set(alpha.price_evidence_ids)
        if not claim_ids or not claim_ids.issubset(snapshot_ids):
            return GateResult(
                gate_name="Hard_TemporalGrounding",
                passed=False,
                reason="Price evidence IDs are not the consensus source IDs",
            )
        if prose_price:
            prose_value = next(
                float(group)
                for group in prose_price.groups()
                if group is not None
            )
            if abs(prose_value - alpha.observed_price) / alpha.observed_price > 0.01:
                return GateResult(
                    gate_name="Hard_TemporalGrounding",
                    passed=False,
                    reason="Prose price conflicts with structured observed_price",
                )
        return GateResult(
            gate_name="Hard_TemporalGrounding",
            passed=True,
            reason=(
                f"price={alpha.observed_price:g}; as_of={claim_date.isoformat()}; "
                f"consensus_sources={len(snapshot_ids)}"
            ),
        )
