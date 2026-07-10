"""Deterministic checks for extracted financial periods, units and relations."""

from __future__ import annotations

import re
from datetime import date

from structflow.input_resolver import EntityProfile, InputKind
from structflow.models import GateResult
from structflow.research_clock import normalize_analysis_date, period_end


MONEY_MULTIPLIERS = {
    "元": 1.0,
    "cny": 1.0,
    "rmb": 1.0,
    "万元": 10_000.0,
    "百万元": 1_000_000.0,
    "亿元": 100_000_000.0,
    "million cny": 1_000_000.0,
    "billion cny": 1_000_000_000.0,
    "mn cny": 1_000_000.0,
    "bn cny": 1_000_000_000.0,
    "million rmb": 1_000_000.0,
    "billion rmb": 1_000_000_000.0,
    "mn rmb": 1_000_000.0,
    "bn rmb": 1_000_000_000.0,
}

MONETARY_METRIC_HINTS = (
    "收入",
    "利润",
    "现金流",
    "应收",
    "存货",
    "资产",
    "负债",
    "资本开支",
    "revenue",
    "profit",
    "cash flow",
    "receivable",
    "inventory",
    "assets",
    "debt",
    "capex",
)


def _money_multiplier(unit: str, currency: str) -> float | None:
    normalized = re.sub(r"\s+", " ", (unit or "").strip().lower())
    if normalized in MONEY_MULTIPLIERS:
        return MONEY_MULTIPLIERS[normalized]
    aliases = {currency.strip().lower()}
    if currency.upper() == "CNY":
        aliases.update({"cny", "rmb", "元", "人民币元"})
    if normalized in aliases:
        return 1.0
    if not any(alias and alias in normalized for alias in aliases):
        return None
    if any(token in normalized for token in ("billion", "bn")):
        return 1_000_000_000.0
    if any(token in normalized for token in ("million", "mn")):
        return 1_000_000.0
    if any(token in normalized for token in ("thousand", "k ")):
        return 1_000.0
    return 1.0


def financial_extraction_contract(analysis_date: date) -> str:
    return f"""
## Binding Financial Extraction Contract

- Current research run date: {analysis_date.isoformat()}.
- Preserve source-reported number and unit before normalization.
- Normalize monetary values to base currency exactly: 1万元=10,000元; 1亿元=100,000,000元.
- Recompute comparisons. Never describe A as below B when A > B.
- Headline profit, adjusted profit, operating cash flow and capex are distinct metrics.
- A period ending after the run date cannot be labeled as an actual result.
""".strip()


class FinancialConsistencyValidator:
    def validate(
        self,
        profile: EntityProfile,
        as_of: str | date | None,
    ) -> GateResult:
        if profile.input_kind != InputKind.COMPANY:
            return GateResult(
                gate_name="Hard_FinancialConsistency",
                passed=True,
                reason="Financial consistency not required for this input kind",
            )
        cutoff = normalize_analysis_date(as_of)
        issues: list[str] = []

        latest_period_end = period_end(profile.latest_reporting_period or "")
        if latest_period_end and latest_period_end > cutoff:
            issues.append(
                f"latest reporting period is after cutoff: {profile.latest_reporting_period}"
            )

        for fact in profile.latest_financial_facts:
            end = period_end(fact.period)
            if end and end > cutoff:
                issues.append(f"future period: {fact.metric} {fact.period}")
            if fact.value is None:
                issues.append(f"missing normalized value: {fact.metric} {fact.period}")
                continue
            is_monetary = any(
                token in fact.metric.lower()
                for token in MONETARY_METRIC_HINTS
            )
            if is_monetary:
                value_multiplier = _money_multiplier(
                    fact.unit, profile.reporting_currency
                )
                reported_multiplier = _money_multiplier(
                    fact.reported_unit, profile.reporting_currency
                )
                if value_multiplier is None:
                    issues.append(
                        f"unknown monetary unit: {fact.metric} {fact.unit}"
                    )
                    continue
                normalized_value = fact.value * value_multiplier
                if fact.reported_value is None or reported_multiplier is None:
                    issues.append(
                        f"missing reported value/unit: {fact.metric} {fact.period}"
                    )
                    continue
                reported_normalized = (
                    fact.reported_value * reported_multiplier
                )
                if (
                    abs(normalized_value - reported_normalized)
                    / max(abs(reported_normalized), 1.0)
                    > 0.005
                ):
                    issues.append(
                        f"unit conversion mismatch: {fact.metric} {fact.period}"
                    )
                    continue
                fact.value = reported_normalized
                fact.unit = profile.reporting_currency

        facts_by_period: dict[str, dict[str, float]] = {}
        for fact in profile.latest_financial_facts:
            if fact.value is not None:
                facts_by_period.setdefault(fact.period, {})[fact.metric] = fact.value
        for period, facts in facts_by_period.items():
            cash = next(
                (value for key, value in facts.items() if "经营活动现金流" in key),
                None,
            )
            profit = next(
                (value for key, value in facts.items() if "归母净利润" in key and "扣非" not in key),
                None,
            )
            if cash is None or profit is None:
                continue
            related_flags = " ".join(
                flag for flag in profile.financial_quality_flags if period[:4] in flag
            )
            if "低于净利润" in related_flags and cash > profit:
                issues.append(
                    f"{period}: cash flow {cash:g} is above profit {profit:g}, not below"
                )
            if "高于净利润" in related_flags and cash < profit:
                issues.append(
                    f"{period}: cash flow {cash:g} is below profit {profit:g}, not above"
                )

        annual_revenue = next(
            (
                fact.value
                for fact in profile.latest_financial_facts
                if fact.metric == "营业收入"
                and fact.value is not None
                and any(token in fact.period for token in ("全年", "年度", "年报"))
            ),
            None,
        )
        if annual_revenue:
            implied_totals: list[float] = []
            for segment in profile.material_segments:
                if not segment.revenue_share or segment.revenue_share <= 0:
                    continue
                match = re.search(
                    r"收入(?:约|为)?\s*([\d.]+)\s*(亿元|万元|百万元)",
                    segment.materiality_reason,
                )
                if not match:
                    continue
                reported = float(match.group(1))
                implied_totals.append(
                    reported * MONEY_MULTIPLIERS[match.group(2)] / segment.revenue_share
                )
            if implied_totals:
                implied = sorted(implied_totals)[len(implied_totals) // 2]
                ratio = annual_revenue / implied
                if ratio < 0.5 or ratio > 2.0:
                    issues.append(
                        "annual revenue scale conflicts with segment revenue/share "
                        f"(ratio={ratio:.2f})"
                    )

        return GateResult(
            gate_name="Hard_FinancialConsistency",
            passed=not issues,
            reason="Financial periods and arithmetic are consistent"
            if not issues
            else "; ".join(issues[:5]),
        )
