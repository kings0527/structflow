"""Unit tests for StructFlow Atlas V2.1 — Meta-Generalization Layer.

Tests: models, gates, reporter, and JSON serialization.
"""

from __future__ import annotations

import json

from structflow.gates import run_all_gates
from structflow.models import (
    AlphaSignal,
    CompanyScore,
    DistortionAnalysis,
    DriverSet,
    L7PortfolioMapping,
    MetaDriver,
    MetaSystemDefinition,
    PortfolioEntity,
    RegimeState,
    ScanInput,
    ScanOutput,
    ScoreVector,
    SystemEquation,
    TimeHorizon,
    VariableMapping,
)
from structflow.reporter import render_report


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_l0() -> MetaSystemDefinition:
    return MetaSystemDefinition(
        system_type="financial market",
        core_function="Provide on-demand compute infrastructure for enterprises — if this disappeared, digital economy collapses",
        state_variables=["data center capacity", "user base", "capital stock", "leverage level"],
        control_variables=["interest rate", "pricing power", "entry barriers", "regulatory standards"],
        exogenous_drivers=["AI workload growth", "geopolitical tech decoupling", "demographic digital adoption"],
        endogenous_feedback_loops=[
            "more users → more data → better models → more users",
            "higher capex → more capacity → lower prices → more demand → higher capex",
        ],
    )


def _make_l1() -> VariableMapping:
    return VariableMapping(
        state_variables=["data center capacity", "user base", "capital stock", "leverage level"],
        flow_variables=["cash flow from subscriptions", "information flow via APIs", "risk transfer via SLAs", "capital flow from investors"],
        control_variables=["interest rate", "pricing power", "entry barriers", "regulatory standards"],
        latent_variables=["market confidence", "risk appetite", "narrative dependency", "liquidity mismatch"],
    )


def _make_l2() -> SystemEquation:
    return SystemEquation(
        flow_weight=0.4,
        control_weight=0.35,
        latent_weight=0.25,
    )


def _make_l3() -> DriverSet:
    return DriverSet(
        drivers=[
            MetaDriver(name="AI Workload Growth", type="macro", direction="+", elasticity=0.8, lag="short", volatility=0.6, system_dependency=0.9),
            MetaDriver(name="Real Interest Rate", type="macro", direction="-", elasticity=0.5, lag="mid", volatility=0.3, system_dependency=0.7),
            MetaDriver(name="Regulatory Pressure", type="policy", direction="-", elasticity=0.3, lag="long", volatility=0.4, system_dependency=0.5),
            MetaDriver(name="Enterprise Digital Transformation", type="behavioral", direction="+", elasticity=0.6, lag="mid", volatility=0.3, system_dependency=0.8),
            MetaDriver(name="Capital Expenditure Cycle", type="financial", direction="+", elasticity=0.7, lag="long", volatility=0.5, system_dependency=0.6),
        ],
    )


def _make_l4() -> RegimeState:
    return RegimeState(
        current_regime="expansion",
        regime_confidence=0.75,
        regime_drivers=["AI Workload Growth", "Enterprise Digital Transformation", "Capital Expenditure Cycle"],
    )


def _make_l5() -> DistortionAnalysis:
    return DistortionAnalysis(
        market_belief="Market believes cloud growth is linear and predictable, driven by enterprise migration",
        true_drivers=["AI workload growth (exogenous)", "Capital expenditure cycle (financial)", "Interest rate sensitivity (macro)"],
        mispricing_sources=["Market underestimates AI-driven non-linear demand spikes", "Market overweights enterprise migration narrative"],
        distortion_score=0.65,
    )


def _make_l6() -> AlphaSignal:
    return AlphaSignal(
        consensus_view="Market believes cloud growth is linear and predictable, driven by steady enterprise migration",
        structural_view="AI workloads are driving non-linear demand spikes that strain capacity, creating structural undersupply",
        mispricing="Market underestimates the velocity and persistence of AI-driven capacity demand relative to linear models",
        alpha_signal="Long cloud infrastructure providers with AI capacity advantage — structural demand is accelerating beyond linear models",
        confidence=0.8,
    )


def _make_l7() -> L7PortfolioMapping:
    return L7PortfolioMapping(
        best_positioned_entities=[
            PortfolioEntity(name="AWS", role="SV controller (capacity)", reason="Dominant data center capacity + AI chip access"),
            PortfolioEntity(name="Azure", role="CV manipulator (enterprise standards)", reason="Enterprise integration + OpenAI partnership"),
        ],
        overvalued_entities=[
            PortfolioEntity(name="Cloud resellers", role="FV intermediary", reason="Thin margins, easily disintermediated by hyperscalers"),
        ],
        fragile_entities=[
            PortfolioEntity(name="Small enterprises", role="LV exposed (lock-in)", reason="Vendor lock-in with rising costs, low switching capability"),
        ],
    )


def _make_gate_report():
    return run_all_gates(_make_l1(), _make_l2(), _make_l3(), _make_l4(), _make_l6())


def _make_scan_output() -> ScanOutput:
    return ScanOutput(
        industry="Cloud Computing",
        region="Global",
        time_horizon=TimeHorizon.MID,
        meta=_make_l0(),
        variables=_make_l1(),
        equation=_make_l2(),
        drivers=_make_l3(),
        regime=_make_l4(),
        distortion=_make_l5(),
        alpha=_make_l6(),
        portfolio=_make_l7(),
        gate_validation=_make_gate_report(),
        key_fragilities=["High distortion score: market misprices AI-driven demand"],
    )


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

def test_scan_input_defaults():
    scan_input = ScanInput(industry="semiconductor")
    assert scan_input.region is None
    assert scan_input.time_horizon == TimeHorizon.MID
    assert scan_input.peer_set == []


def test_l0_model_validation():
    l0 = _make_l0()
    assert l0.system_type == "financial market"
    assert len(l0.state_variables) >= 2
    assert len(l0.control_variables) >= 2
    assert len(l0.exogenous_drivers) >= 1
    assert len(l0.endogenous_feedback_loops) >= 1


def test_l1_variable_mapping():
    l1 = _make_l1()
    assert len(l1.state_variables) >= 3
    assert len(l1.flow_variables) >= 3
    assert len(l1.control_variables) >= 3
    assert len(l1.latent_variables) >= 3


def test_l2_system_equation():
    l2 = _make_l2()
    total = l2.flow_weight + l2.control_weight + l2.latent_weight
    assert abs(total - 1.0) < 0.05


def test_gate1_variable_completeness():
    l1 = _make_l1()
    from structflow.gates import gate1_variable_completeness
    result = gate1_variable_completeness(l1)
    assert result.passed is True


def test_gate1_fails_with_missing_variables():
    l1 = VariableMapping(
        state_variables=["capacity"],
        flow_variables=["cash flow"],
        control_variables=["interest rate"],
        latent_variables=["confidence"],
    )
    from structflow.gates import gate1_variable_completeness
    result = gate1_variable_completeness(l1)
    assert result.passed is False


def test_gate2_system_equation():
    l2 = _make_l2()
    from structflow.gates import gate2_system_equation
    result = gate2_system_equation(l2)
    assert result.passed is True


def test_gate2_fails_with_wrong_weights():
    l2 = SystemEquation(flow_weight=0.5, control_weight=0.3, latent_weight=0.3)
    from structflow.gates import gate2_system_equation
    result = gate2_system_equation(l2)
    assert result.passed is False


def test_gate3_driver_sources():
    l3 = _make_l3()
    from structflow.gates import gate3_driver_sources
    result = gate3_driver_sources(l3)
    assert result.passed is True


def test_gate3_fails_with_invalid_type():
    l3 = DriverSet(drivers=[
        MetaDriver(name="X", type="invalid_type", direction="+", elasticity=0.5, lag="short", volatility=0.3, system_dependency=0.7),
    ])
    from structflow.gates import gate3_driver_sources
    result = gate3_driver_sources(l3)
    assert result.passed is False


def test_gate4_regime_identification():
    l4 = _make_l4()
    from structflow.gates import gate4_regime_identification
    result = gate4_regime_identification(l4)
    assert result.passed is True


def test_gate4_fails_with_invalid_regime():
    l4 = RegimeState(current_regime="unknown", regime_confidence=0.5, regime_drivers=["x"])
    from structflow.gates import gate4_regime_identification
    result = gate4_regime_identification(l4)
    assert result.passed is False


def test_gate5_alpha_generation():
    l6 = _make_l6()
    from structflow.gates import gate5_alpha_generation
    result = gate5_alpha_generation(l6)
    assert result.passed is True


def test_gate5_fails_with_missing_alpha():
    l6 = AlphaSignal(
        consensus_view="short",
        structural_view="Some structural view here",
        mispricing="Some mispricing here",
        alpha_signal="Some alpha signal here",
        confidence=0.5,
    )
    from structflow.gates import gate5_alpha_generation
    result = gate5_alpha_generation(l6)
    assert result.passed is False


def test_all_gates_pass():
    report = run_all_gates(_make_l1(), _make_l2(), _make_l3(), _make_l4(), _make_l6())
    assert report.all_passed is True
    assert len(report.failed_gates) == 0


def test_report_renders_all_sections():
    output = _make_scan_output()
    report = render_report(output)
    assert "## 1. System Mapping" in report
    assert "## 2. System Equation" in report
    assert "## 3. Driver Set" in report
    assert "## 4. Regime State" in report
    assert "## 5. Distortion Analysis" in report
    assert "## 6. Alpha Signal" in report
    assert "## 7. Investment Mapping" in report
    assert "## Gate Validation" in report


def test_report_contains_key_data():
    output = _make_scan_output()
    report = render_report(output)
    assert "AWS" in report
    assert "AI Workload Growth" in report
    assert "expansion" in report
    assert "0.65" in report or "65%" in report  # distortion score


def test_scan_output_json_serializable():
    output = _make_scan_output()
    json_str = output.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["industry"] == "Cloud Computing"
    assert parsed["meta"]["system_type"] == "financial market"
    assert len(parsed["variables"]["state_variables"]) == 4
    assert len(parsed["drivers"]["drivers"]) == 5
    assert parsed["alpha"]["alpha_signal"] is not None
    assert parsed["regime"]["current_regime"] == "expansion"


def test_score_vector_bounds():
    sv = ScoreVector(
        control_score=0, profit_capture_score=0,
        risk_displacement_score=0, information_advantage_score=0,
        incentive_alignment_score=0,
    )
    assert sv.control_score == 0

    sv_max = ScoreVector(
        control_score=10, profit_capture_score=10,
        risk_displacement_score=10, information_advantage_score=10,
        incentive_alignment_score=10,
    )
    assert sv_max.control_score == 10


def test_structural_health_calculation():
    company = CompanyScore(
        name="TestCo",
        role="Controller",
        score_vector=ScoreVector(
            control_score=8, profit_capture_score=7,
            risk_displacement_score=3, information_advantage_score=9,
            incentive_alignment_score=7,
        ),
        structural_health=0,
    )
    sv = company.score_vector
    expected_health = (sv.control_score * sv.profit_capture_score * sv.information_advantage_score) / ((10 - sv.risk_displacement_score) + (10 - sv.incentive_alignment_score))
    assert abs(expected_health - (8 * 7 * 9) / (7 + 3)) < 0.01


def test_system_equation_weights_sum():
    l2 = _make_l2()
    total = l2.flow_weight + l2.control_weight + l2.latent_weight
    assert abs(total - 1.0) < 0.05


def test_driver_types_valid():
    l3 = _make_l3()
    valid_types = {"macro", "micro", "policy", "behavioral", "financial"}
    for d in l3.drivers:
        assert d.type in valid_types


def test_regime_valid():
    l4 = _make_l4()
    valid_regimes = {"expansion", "contraction", "transition", "bubble", "collapse"}
    assert l4.current_regime in valid_regimes


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
