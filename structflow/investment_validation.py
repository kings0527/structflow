"""Validate that L7 distinguishes tradable assets from operating nodes."""

from __future__ import annotations

from datetime import date

from structflow.input_resolver import EntityProfile
from structflow.models import GateResult, InvestmentMapping
from structflow.research_clock import coerce_date, normalize_analysis_date


TRADABLE_TYPES = {
    "listed_equity",
    "listed_subsidiary",
    "commodity",
    "fund",
    "derivative",
}


class InvestmentValidator:
    def validate(
        self,
        mapping: InvestmentMapping | None,
        profile: EntityProfile,
        as_of: str | date | None,
        known_source_ids: set[str] | None = None,
    ) -> GateResult:
        if mapping is None:
            return GateResult(
                gate_name="Hard_L7AssetVerification",
                passed=True,
                reason="L7 not requested",
            )
        issues: list[str] = []
        cutoff = normalize_analysis_date(as_of)
        snapshot = profile.market_snapshot
        known = known_source_ids or set()

        for bucket_name in ("best_positioned", "overvalued"):
            for asset in getattr(mapping, bucket_name):
                if asset.asset_type not in TRADABLE_TYPES or not asset.is_tradable:
                    issues.append(f"{bucket_name}:{asset.asset} is not tradable")
                if asset.asset_type in {"listed_equity", "listed_subsidiary", "fund"}:
                    if not asset.ticker or not asset.venue:
                        issues.append(f"{bucket_name}:{asset.asset} lacks ticker/venue")

        for asset in (
            mapping.best_positioned + mapping.overvalued + mapping.fragile
        ):
            if not asset.evidence_ids or asset.verification_status == "unverified":
                issues.append(f"{asset.asset} lacks verified evidence")
            if known:
                unknown = sorted(set(asset.evidence_ids) - known)
                if unknown:
                    issues.append(f"{asset.asset} has unknown evidence IDs {unknown}")
            if asset.observed_price is None:
                continue
            observed_on = coerce_date(asset.price_as_of)
            if observed_on is None or observed_on > cutoff:
                issues.append(f"{asset.asset} has invalid/future price date")
            if (
                snapshot
                and asset.ticker == profile.ticker
                and abs(asset.observed_price - snapshot.price) / snapshot.price > 0.01
            ):
                issues.append(f"{asset.asset} price conflicts with market snapshot")

        return GateResult(
            gate_name="Hard_L7AssetVerification",
            passed=not issues,
            reason=(
                f"{sum(len(getattr(mapping, name)) for name in ('best_positioned', 'overvalued', 'fragile'))} mappings verified"
                if not issues
                else "; ".join(issues[:6])
            ),
        )
