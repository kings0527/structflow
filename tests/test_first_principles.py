"""Tests for the first-principles upgrades.

Batch 1: regime distribution, persistence mechanism, narrative stage,
crowding assessment, loop delay, irreversibility, retry temperature cap.
"""

from structflow.models import (
    AlphaEngine,
    DistortionEngine,
    EarlyWarningSignal,
    FeedbackLoop,
    FlowFeedbackSystem,
    GateResult,
    RegimeEngine,
    RegimeTransition,
)
from structflow.output_validator import OutputValidator
from structflow.retry_guard import RetryGuard


def _regime(**updates) -> RegimeEngine:
    values = {
        "current_regime": "expansion",
        "confidence": 0.7,
        "transition_probability": RegimeTransition(
            next_regime="transition", probability=0.30
        ),
        "regime_distribution": {
            "expansion": 0.55,
            "transition": 0.30,
            "contraction": 0.05,
            "bubble": 0.05,
            "collapse": 0.025,
            "shock": 0.025,
        },
        "early_warning_signals": [
            EarlyWarningSignal(
                signal="none_observed",
                proxy="volatility decay after shocks remains fast",
            ),
        ],
    }
    values.update(updates)
    return RegimeEngine(**values)


def _distortion(**updates) -> DistortionEngine:
    values = {
        "market_belief": "Consensus expects stable linear growth ahead.",
        "structural_truth": "Order inflow drives nonlinear utilization swings.",
        "mispricing_sources": ["nonlinear utilization is underpriced"],
        "distortion_score": 0.5,
        "persistence_mechanism": (
            "Mandate-constrained funds cannot exit benchmark names, "
            "so the gap persists."
        ),
        "narrative_stage": "spreading",
        "narrative_stage_proxy": "media coverage volume still accelerating",
    }
    values.update(updates)
    return DistortionEngine(**values)


def _alpha(**updates) -> AlphaEngine:
    values = {
        "consensus_view": "Consensus expects stable linear growth ahead.",
        "structural_view": "Nonlinear order feedback dominates utilization.",
        "mispricing": "Regime dependence of utilization is underappreciated.",
        "alpha_signal": "Neutral exposure until order inflow confirms regime.",
        "direction": "neutral",
        "confidence": 0.5,
        "crowding_assessment": (
            "Positioning checked: flows are moderate, thesis not crowded."
        ),
        "falsifiers": ["order inflow confirms the regime for two quarters"],
        "irreversibility": "none",
    }
    values.update(updates)
    return AlphaEngine(**values)


# ── L4 regime distribution (Bayesian discipline) ──────────────


def test_regime_distribution_valid_passes():
    assert OutputValidator().validate_regime(_regime()).passed is True


def test_regime_distribution_missing_fails():
    result = OutputValidator().validate_regime(
        _regime(regime_distribution={})
    )
    assert result.passed is False
    assert "regime_distribution missing" in result.reason


def test_regime_distribution_must_cover_all_six_regimes():
    result = OutputValidator().validate_regime(
        _regime(regime_distribution={"expansion": 0.6, "transition": 0.4})
    )
    assert result.passed is False
    assert "missing regimes" in result.reason


def test_regime_distribution_must_sum_to_one():
    result = OutputValidator().validate_regime(
        _regime(regime_distribution={
            "expansion": 0.5, "transition": 0.5, "contraction": 0.3,
            "bubble": 0.1, "collapse": 0.1, "shock": 0.1,
        })
    )
    assert result.passed is False
    assert "sums to" in result.reason


def test_declared_transition_must_match_distribution_argmax():
    result = OutputValidator().validate_regime(
        _regime(transition_probability=RegimeTransition(
            next_regime="contraction", probability=0.05
        ))
    )
    assert result.passed is False
    assert "argmax" in result.reason


def test_declared_probability_must_track_distribution_value():
    result = OutputValidator().validate_regime(
        _regime(transition_probability=RegimeTransition(
            next_regime="transition", probability=0.9
        ))
    )
    assert result.passed is False
    assert "deviates" in result.reason


# ── L3 loop delay (control theory) ───────────────────────────


def _loops(delays: list[str]) -> FlowFeedbackSystem:
    types = ["reinforcing", "balancing", "reinforcing"]
    return FlowFeedbackSystem(
        flow_types=["capital flow"],
        feedback_loops=[
            FeedbackLoop(
                loop_name=f"loop-{index}",
                type=types[index],
                mechanism="a causes b causes a",
                trigger="threshold",
                amplification_factor=0.5,
                delay=delay,
            )
            for index, delay in enumerate(delays)
        ],
    )


def test_missing_loop_delay_fails():
    result = OutputValidator().validate_feedback_completeness(
        _loops(["short", "", "mid"])
    )
    assert result.passed is False
    assert "delay" in result.reason


def test_balancing_long_delay_flagged_as_oscillation_risk():
    result = OutputValidator().validate_feedback_completeness(
        _loops(["short", "long", "mid"])
    )
    assert result.passed is True
    assert "Oscillation-risk" in result.reason


def test_chinese_delay_alias_normalized():
    loop = FeedbackLoop(
        loop_name="x", type="balancing", mechanism="m",
        trigger="t", amplification_factor=0.5, delay="长",
    )
    assert loop.delay == "long"


# ── L5 persistence mechanism + narrative stage ────────────────


def test_distortion_with_all_fields_passes():
    assert OutputValidator().validate_distortion(_distortion()).passed is True


def test_missing_persistence_mechanism_fails():
    result = OutputValidator().validate_distortion(
        _distortion(persistence_mechanism="")
    )
    assert result.passed is False
    assert "persistence_mechanism" in result.reason


def test_invalid_narrative_stage_fails():
    result = OutputValidator().validate_distortion(
        _distortion(narrative_stage="viral")
    )
    assert result.passed is False
    assert "narrative_stage" in result.reason


def test_narrative_stage_requires_measurable_proxy():
    result = OutputValidator().validate_distortion(
        _distortion(narrative_stage_proxy="vibes")
    )
    assert result.passed is False
    assert "proxy" in result.reason


def test_chinese_narrative_stage_alias_normalized():
    assert _distortion(narrative_stage="饱和").narrative_stage == "saturated"


# ── L6 crowding + irreversibility (ergodicity) ────────────────


def test_alpha_with_all_fields_passes():
    assert (
        OutputValidator().validate_alpha_completeness(_alpha()).passed is True
    )


def test_missing_crowding_assessment_fails():
    result = OutputValidator().validate_alpha_completeness(
        _alpha(crowding_assessment="")
    )
    assert result.passed is False
    assert "crowding_assessment" in result.reason


def test_invalid_irreversibility_fails():
    result = OutputValidator().validate_alpha_completeness(
        _alpha(irreversibility="total")
    )
    assert result.passed is False
    assert "irreversibility" in result.reason


def test_absorbing_state_requires_ruin_path():
    result = OutputValidator().validate_alpha_completeness(
        _alpha(irreversibility="absorbing", ruin_path="")
    )
    assert result.passed is False
    assert "ruin_path" in result.reason


def test_absorbing_state_with_ruin_path_passes():
    result = OutputValidator().validate_alpha_completeness(
        _alpha(
            irreversibility="absorbing",
            ruin_path=(
                "Sustained cash burn forces dilution then delisting; "
                "equity value does not recover."
            ),
        )
    )
    assert result.passed is True


# ── Retry guard temperature cap (engineering) ─────────────────


def test_retry_temperature_capped_at_half():
    guard = RetryGuard(max_retries=2, min_pass_rate=0.75)
    seen_temperatures: list[float] = []

    def func(retry_feedback: str = "", temperature: float = 0.2) -> str:
        seen_temperatures.append(temperature)
        return "output"

    def validate(_: str) -> list[GateResult]:
        return [GateResult(gate_name="Hard_X", passed=False, reason="fail")]

    guard.run_with_retry(func, validate, "layer")
    assert max(seen_temperatures) <= 0.5


# ── Batch 2: early warning, chokepoints, prior, origins ───────


from structflow.evidence import EvidenceRecord  # noqa: E402
from structflow.models import (  # noqa: E402
    Chokepoint,
    EvidenceAdjustment,
    MetaSystemDefinition,
)
from structflow.research_gates import ResearchValidator  # noqa: E402


def _record(url: str, upstream: str | None = None) -> EvidenceRecord:
    return EvidenceRecord(
        category="l6_alpha",
        provider="host_agent_search",
        query="q",
        title="t",
        url=url,
        content="evidence body",
        upstream_origin=upstream,
    )


def test_missing_early_warning_signals_fails():
    result = OutputValidator().validate_regime(
        _regime(early_warning_signals=[])
    )
    assert result.passed is False
    assert "early_warning_signals" in result.reason


def test_none_observed_with_proxy_is_valid():
    result = OutputValidator().validate_regime(
        _regime(early_warning_signals=[
            EarlyWarningSignal(
                signal="none_observed",
                proxy="volatility decay after shocks remains fast",
            ),
        ])
    )
    assert result.passed is True


def test_warning_signal_requires_proxy():
    result = OutputValidator().validate_regime(
        _regime(early_warning_signals=[
            EarlyWarningSignal(signal="flickering", proxy="n/a"),
        ])
    )
    assert result.passed is False
    assert "proxy" in result.reason


def _flow(chokepoints: list[Chokepoint]) -> FlowFeedbackSystem:
    return FlowFeedbackSystem(
        flow_types=["goods flow"],
        feedback_loops=[],
        chokepoints=chokepoints,
    )


def test_chokepoint_assessment_required():
    result = OutputValidator().validate_chokepoints(_flow([]))
    assert result.passed is False
    assert "chokepoint" in result.reason


def test_single_point_chokepoint_must_close_into_failure_or_falsifier():
    meta = MetaSystemDefinition(
        system_type="manufacturing system",
        core_function="convert capacity into output",
        system_boundary="capacity and orders inside; services outside",
        failure_mode="demand slump drains cash and forces shutdown",
    )
    flow = _flow([
        Chokepoint(
            name="Xinjiang rail corridor",
            flow_type="goods flow",
            concentration="single_point",
        ),
    ])
    open_alpha = _alpha()
    result = ResearchValidator().validate_chokepoint_closure(
        meta, flow, open_alpha
    )
    assert result.passed is False
    assert "Xinjiang" in result.reason

    closed_alpha = _alpha(
        alpha_signal=(
            "Neutral exposure; falsifier: Xinjiang rail corridor "
            "disruption severs coal outflow."
        ),
    )
    closed = ResearchValidator().validate_chokepoint_closure(
        meta, flow, closed_alpha
    )
    assert closed.passed is True


def test_confidence_capped_by_independent_origins():
    records = {
        "src_1": _record("https://a.example/x"),
        "src_2": _record("https://b.example/y"),
    }
    alpha = _alpha(
        confidence=0.8,
        supporting_evidence_ids=["src_1", "src_2"],
    )
    result = ResearchValidator().validate_confidence_evidence_cap(
        alpha, records
    )
    assert result.passed is False
    assert "cap=0.65" in result.reason


def test_shared_upstream_origin_counts_as_one_source():
    records = {
        "src_1": _record("https://a.example/x", upstream="USGS 2026 report"),
        "src_2": _record("https://b.example/y", upstream="usgs 2026 report"),
    }
    alpha = _alpha(
        confidence=0.55,
        supporting_evidence_ids=["src_1", "src_2"],
    )
    result = ResearchValidator().validate_confidence_evidence_cap(
        alpha, records
    )
    # one origin → cap 0.50 < 0.55
    assert result.passed is False
    assert "independent_origins=1" in result.reason


def test_prior_decomposition_required_when_evidence_exists():
    result = ResearchValidator().validate_prior_decomposition(
        _alpha(), {"src_1"}
    )
    assert result.passed is False
    assert "reference_class" in result.reason


def test_prior_decomposition_passes_with_cited_adjustments():
    alpha = _alpha(
        reference_class=(
            "Capacity-constrained systems entering regime transition"
        ),
        prior_probability=0.4,
        evidence_adjustments=[
            EvidenceAdjustment(
                evidence_id="src_1",
                direction="+",
                rationale="orders confirm nonlinear response",
            ),
        ],
    )
    result = ResearchValidator().validate_prior_decomposition(
        alpha, {"src_1"}
    )
    assert result.passed is True


# ── Host-agent friction fixes (from live skill-invocation test) ─


from structflow.models import Driver, DriverSpace  # noqa: E402


def test_driver_requires_measurable_proxy():
    space = DriverSpace(drivers=[Driver(
        name="capacity utilization", category="structural",
        maps_to_variable="FV", direction="nonlinear", proxy="",
        elasticity=0.8, volatility=0.4, lag="mid", regime_dependency=0.7,
    )])
    result = OutputValidator().validate_driver_binding(space)
    assert result.passed is False
    assert "proxy" in result.reason


def test_alpha_requires_structured_falsifiers():
    result = OutputValidator().validate_alpha_completeness(
        _alpha(falsifiers=[])
    )
    assert result.passed is False
    assert "falsifiers" in result.reason


def test_falsifier_list_closes_single_point_chokepoint():
    meta = MetaSystemDefinition(
        system_type="manufacturing system",
        core_function="convert capacity into output",
        system_boundary="capacity and orders inside; services outside",
        failure_mode="demand slump drains cash and forces shutdown",
    )
    flow = _flow([
        Chokepoint(
            name="sole graphite refinery",
            flow_type="goods flow",
            concentration="single_point",
        ),
    ])
    alpha = _alpha(
        falsifiers=["sole graphite refinery outage severs anode supply"],
    )
    result = ResearchValidator().validate_chokepoint_closure(
        meta, flow, alpha
    )
    assert result.passed is True


def test_layer_context_embeds_binding_schema():
    from structflow.skill_runtime import _layer_schema_block

    block = _layer_schema_block("l4")
    assert "Output JSON Schema (binding)" in block
    assert "regime_distribution" in block
    assert "early_warning_signals" in block
    assert _layer_schema_block("unknown-layer") == ""
