"""Tests for the first-principles upgrades.

Batch 1: regime distribution, persistence mechanism, narrative stage,
crowding assessment, loop delay, irreversibility, retry temperature cap.
"""

from structflow.models import (
    AlphaEngine,
    DistortionEngine,
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
