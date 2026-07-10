"""Hard research-quality gates that validate facts, not only schema shape."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from structflow.input_resolver import EntityProfile, InputKind
from structflow.models import (
    AlphaEngine,
    DistortionEngine,
    GateResult,
    InvestmentMapping,
    MetaSystemDefinition,
    RegimeEngine,
    DriverSpace,
    VariableMapping,
)


def _result(name: str, passed: bool, reason: str) -> GateResult:
    return GateResult(
        gate_name=f"Hard_{name}",
        passed=passed,
        reason=reason,
    )


def _all_text(values: Iterable[object]) -> str:
    return " ".join(str(value) for value in values if value)


def _segment_tokens(name: str) -> list[str]:
    aliases = {
        "电气设备": ["电气设备", "输变电", "变压器", "电网设备"],
        "电线电缆": ["电线电缆", "电缆"],
        "新能源": ["新能源", "光伏", "多晶硅", "逆变器", "储能"],
        "煤炭": ["煤炭", "煤矿"],
        "发电": ["发电", "电站", "电力运营"],
        "铝": ["铝电子", "新材料", "铝合金", "高纯铝"],
        "黄金": ["黄金", "金矿"],
        "资本": ["资本开支", "融资", "债务", "资本配置"],
    }
    for key, values in aliases.items():
        if key in name:
            return values
    cleaned = re.sub(
        r"(产品|业务|产业|及工程|工程|板块|分部)", "", name
    ).strip()
    return [cleaned] if cleaned else [name]


def _declared_ids(value: object) -> tuple[list[str], list[str]]:
    support = list(
        getattr(value, "supporting_evidence_ids", []) or []
    )
    contradiction = list(
        getattr(value, "contradicting_evidence_ids", []) or []
    )
    return support, contradiction


class ResearchValidator:
    def validate_entity_profile(
        self,
        profile: EntityProfile,
        available_ids: set[str],
    ) -> GateResult:
        if profile.input_kind != InputKind.COMPANY:
            return _result(
                "EntityProfile",
                bool(profile.canonical_name),
                f"Resolved input kind: {profile.input_kind.value}",
            )
        cited_ids = [
            source_id
            for segment in profile.material_segments
            for source_id in segment.evidence_ids
        ] + list(profile.evidence_ids)
        unknown = [
            source_id
            for source_id in cited_ids
            if source_id not in available_ids
        ]
        uncited_segments = [
            segment.name
            for segment in profile.material_segments
            if not segment.evidence_ids
        ]
        passed = (
            bool(profile.ticker)
            and len(profile.material_segments) >= 2
            and bool(profile.required_system_dimensions)
            and not uncited_segments
            and not unknown
        )
        return _result(
            "EntityProfile",
            passed,
            (
                f"ticker={profile.ticker}; "
                f"segments={len(profile.material_segments)}; "
                f"uncited={uncited_segments}; unknown={unknown}"
            ),
        )

    def validate_material_segment_coverage(
        self,
        meta: MetaSystemDefinition,
        profile: EntityProfile,
    ) -> GateResult:
        if profile.input_kind != InputKind.COMPANY:
            return _result(
                "MaterialSegmentCoverage",
                True,
                "Not a company input",
            )
        boundary = _all_text([
            meta.system_type,
            meta.core_function,
            meta.system_boundary,
            meta.failure_mode,
        ])
        missing: list[str] = []
        material_segments = [
            segment
            for segment in profile.material_segments
            if (
                segment.name not in {"其他", "其他业务"}
                and
                segment.revenue_share is None
                or segment.revenue_share >= 0.05
                or (
                    segment.gross_profit_share is not None
                    and segment.gross_profit_share >= 0.05
                )
            )
        ]
        for segment in material_segments:
            if not any(
                token and token in boundary
                for token in _segment_tokens(segment.name)
            ):
                missing.append(segment.name)
        for dimension in profile.required_system_dimensions:
            if not any(
                token and token in boundary
                for token in _segment_tokens(dimension)
            ):
                missing.append(dimension)
        return _result(
            "MaterialSegmentCoverage",
            not missing,
            (
                "All material segments are inside L0 boundary"
                if not missing
                else "L0 omitted material segments/dimensions: "
                + ", ".join(missing)
            ),
        )

    def validate_variable_segment_coverage(
        self,
        variables: VariableMapping,
        profile: EntityProfile,
    ) -> GateResult:
        if profile.input_kind != InputKind.COMPANY:
            return _result(
                "VariableSegmentCoverage",
                True,
                "Not a company input",
            )
        text = _all_text([
            *variables.state_variables,
            *variables.flow_variables,
            *variables.control_variables,
            *variables.latent_variables,
        ])
        names = [
            segment.name
            for segment in profile.material_segments
            if segment.name not in {"其他", "其他业务"}
        ] + profile.required_system_dimensions
        missing = [
            name
            for name in names
            if not any(
                token and token in text
                for token in _segment_tokens(name)
            )
        ]
        return _result(
            "VariableSegmentCoverage",
            not missing,
            (
                "Variable space covers material segments"
                if not missing
                else "Variable space omitted: "
                + ", ".join(dict.fromkeys(missing))
            ),
        )

    def validate_driver_segment_coverage(
        self,
        drivers: DriverSpace,
        profile: EntityProfile,
    ) -> GateResult:
        if profile.input_kind != InputKind.COMPANY:
            return _result(
                "DriverSegmentCoverage",
                True,
                "Not a company input",
            )
        text = _all_text(
            driver.name for driver in drivers.drivers
        )
        names = [
            segment.name
            for segment in profile.material_segments
            if segment.name not in {"其他", "其他业务"}
        ] + profile.required_system_dimensions
        missing = [
            name
            for name in names
            if not any(
                token and token in text
                for token in _segment_tokens(name)
            )
        ]
        return _result(
            "DriverSegmentCoverage",
            not missing,
            (
                "Driver space covers material segments"
                if not missing
                else "Driver space omitted: "
                + ", ".join(dict.fromkeys(missing))
            ),
        )

    def validate_citations(
        self,
        value: DistortionEngine | AlphaEngine,
        available_ids: set[str],
        layer_name: str,
    ) -> GateResult:
        support, contradiction = _declared_ids(value)
        if not available_ids:
            return _result(
                f"{layer_name}ClaimCitation",
                True,
                "No external evidence available; citation gate skipped",
            )
        unknown = [
            source_id
            for source_id in support + contradiction
            if source_id not in available_ids
        ]
        passed = (
            len(support) >= 2
            and len(contradiction) >= 1
            and not unknown
        )
        reason = (
            f"support={len(support)}, contradiction="
            f"{len(contradiction)}, unknown={unknown}"
        )
        return _result(f"{layer_name}ClaimCitation", passed, reason)

    def validate_temporal_grounding(
        self,
        alpha: AlphaEngine,
        profile: EntityProfile,
    ) -> GateResult:
        text = _all_text([
            alpha.consensus_view,
            alpha.structural_view,
            alpha.mispricing,
            alpha.alpha_signal,
        ])
        price_claims = [
            float(match)
            for match in re.findall(
                r"(?:股价|价格|收盘价)[^\d]{0,12}"
                r"(\d{1,5}(?:\.\d+)?)\s*(?:元|CNY)",
                text,
            )
        ]
        if not price_claims:
            return _result(
                "TemporalGrounding",
                True,
                "No current-price claim emitted",
            )
        snapshot = profile.market_snapshot
        if snapshot is None:
            return _result(
                "TemporalGrounding",
                False,
                "Price claim emitted without a dated market snapshot",
            )
        if snapshot.stale_days > 3:
            return _result(
                "TemporalGrounding",
                False,
                f"Market snapshot is stale: {snapshot.as_of}",
            )
        mismatch = [
            price
            for price in price_claims
            if abs(price - snapshot.price)
            / snapshot.price > 0.01
        ]
        support, _ = _declared_ids(alpha)
        cited = snapshot.source_id in support
        passed = not mismatch and cited
        return _result(
            "TemporalGrounding",
            passed,
            (
                f"snapshot={snapshot.price} {snapshot.currency} "
                f"as_of={snapshot.as_of}; mismatches={mismatch}; "
                f"snapshot_cited={cited}"
            ),
        )

    def validate_financial_quality(
        self,
        alpha: AlphaEngine,
        profile: EntityProfile,
    ) -> GateResult:
        if (
            profile.input_kind != InputKind.COMPANY
            or not profile.financial_quality_flags
        ):
            return _result(
                "FinancialQuality",
                True,
                "No material financial-quality warning",
            )
        text = _all_text([
            alpha.structural_view,
            alpha.mispricing,
            alpha.alpha_signal,
        ])
        quality_terms = (
            "扣非", "非经常", "公允价值", "经营现金流",
            "现金回款", "资本开支", "利润质量",
        )
        passed = any(term in text for term in quality_terms)
        return _result(
            "FinancialQuality",
            passed,
            (
                "Alpha addresses adjusted earnings/cash quality"
                if passed
                else "Alpha must address profile warnings: "
                + "; ".join(profile.financial_quality_flags[:4])
            ),
        )

    def validate_advice_boundary(
        self, alpha: AlphaEngine
    ) -> GateResult:
        text = _all_text([
            alpha.consensus_view,
            alpha.structural_view,
            alpha.mispricing,
            alpha.alpha_signal,
        ])
        forbidden = re.findall(
            r"建议(?:买入|卖出|做多|做空|持有)|"
            r"目标价|上行空间|买入评级|卖出评级|"
            r"建仓|加仓|减仓|target price|upside",
            text,
        )
        return _result(
            "AdviceBoundary",
            not forbidden,
            (
                "No prescriptive investment advice"
                if not forbidden
                else "Forbidden advice language: "
                + ", ".join(sorted(set(forbidden)))
            ),
        )

    def validate_regime_alpha_reconciliation(
        self,
        regime: RegimeEngine,
        alpha: AlphaEngine,
    ) -> GateResult:
        transition = regime.transition_probability
        if not (
            transition.next_regime == "contraction"
            and transition.probability >= 0.40
            and alpha.direction == "long"
        ):
            return _result(
                "RegimeAlphaReconciliation",
                True,
                "Regime and alpha do not require special reconciliation",
            )
        text = _all_text([
            alpha.structural_view,
            alpha.mispricing,
            alpha.alpha_signal,
        ])
        contraction_terms = (
            "收缩", "衰退", "下行周期", "需求下滑", "contraction",
            "recession", "downcycle",
        )
        mechanism_terms = (
            "已充分计价", "已充分反映", "逆周期", "对冲",
            "分部背离", "领先复苏", "安全边际", "priced in",
            "counter-cyclical", "hedge", "segment divergence",
        )
        trigger_terms = (
            "反转触发", "成立条件", "否定条件", "失效条件",
            "reversal trigger", "falsifier",
        )
        passed = (
            any(term in text for term in contraction_terms)
            and any(term in text for term in mechanism_terms)
            and any(term in text for term in trigger_terms)
        )
        return _result(
            "RegimeAlphaReconciliation",
            passed,
            (
                "Long signal explicitly reconciles contraction risk"
                if passed
                else "Long signal must explain why contraction is "
                "mispriced and define reversal triggers"
            ),
        )

    def validate_l7_evidence(
        self,
        portfolio: Optional[InvestmentMapping],
        available_ids: set[str],
    ) -> GateResult:
        if portfolio is None:
            return _result(
                "L7AssetVerification",
                True,
                "Portfolio layer disabled",
            )
        assets = [
            *portfolio.best_positioned,
            *portfolio.overvalued,
            *portfolio.fragile,
        ]
        failures: list[str] = []
        for asset in assets:
            evidence_ids = list(
                getattr(asset, "evidence_ids", []) or []
            )
            status = getattr(
                asset, "verification_status", "unverified"
            )
            if (
                not evidence_ids
                or status == "unverified"
                or any(
                    source_id not in available_ids
                    for source_id in evidence_ids
                )
            ):
                failures.append(asset.asset)
        return _result(
            "L7AssetVerification",
            not failures,
            (
                f"{len(assets)} assets evidence-verified"
                if not failures
                else "Unverified assets: " + ", ".join(failures)
            ),
        )
