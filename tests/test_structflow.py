"""Unit tests for StructFlow Atlas V2.2 — Nonlinear State-Space Engine."""

from __future__ import annotations

import json

from structflow.gates import run_all_gates
from structflow.models import (
    AlphaEngine,
    AssetMapping,
    CapacityLag,
    CompanyScore,
    DemandElasticityModule,
    DistortionEngine,
    Driver,
    DriverSpace,
    FeedbackLoop,
    FlowFeedbackSystem,
    InventoryCycle,
    InvestmentMapping,
    MetaSystemDefinition,
    NonlinearDynamics,
    RegimeEngine,
    RegimeTransition,
    ScanInput,
    ScanOutput,
    ScoreVector,
    TimeHorizon,
    VariableMapping,
)
from structflow.reporter import render_report


# ─── Fixtures ──────────────────────────────────────────────────

def _make_l0() -> MetaSystemDefinition:
    return MetaSystemDefinition(
        system_type="platform economy",
        core_function="Provide on-demand compute infrastructure — if this disappeared, digital economy collapses",
        system_boundary="Includes cloud providers, data centers, and API ecosystems. Excludes edge devices and end-user applications.",
        failure_mode="Cascading capacity shortage → service degradation → customer migration → revenue collapse → capex freeze",
    )


def _make_l1() -> VariableMapping:
    return VariableMapping(
        state_variables=["data center capacity", "user base", "capital stock"],
        flow_variables=["cash flow from subscriptions", "data throughput", "investment flow"],
        control_variables=["interest rate", "pricing power", "regulatory standards"],
        latent_variables=["market confidence", "risk appetite", "technology narrative"],
    )


def _make_l2() -> DriverSpace:
    return DriverSpace(drivers=[
        Driver(name="AI Workload Growth", category="macro", maps_to_variable="FV", direction="+", elasticity=0.8, volatility=0.6, lag="short", regime_dependency=0.9),
        Driver(name="Real Interest Rate", category="macro", maps_to_variable="CV", direction="-", elasticity=0.5, volatility=0.3, lag="mid", regime_dependency=0.7),
        Driver(name="Regulatory Pressure", category="policy", maps_to_variable="CV", direction="-", elasticity=0.3, volatility=0.4, lag="long", regime_dependency=0.5),
        Driver(name="Capacity Expansion", category="structural", maps_to_variable="SV", direction="+", elasticity=0.7, volatility=0.4, lag="long", regime_dependency=0.6),
        Driver(name="Market Confidence", category="behavioral", maps_to_variable="LV", direction="nonlinear", elasticity=0.6, volatility=0.7, lag="mid", regime_dependency=0.8),
    ])


def _make_l3() -> FlowFeedbackSystem:
    return FlowFeedbackSystem(
        flow_types=["capital flow", "goods flow", "information flow", "risk flow"],
        feedback_loops=[
            FeedbackLoop(loop_name="Growth Flywheel", type="reinforcing", mechanism="more users → more data → better models → more users", trigger="user acquisition exceeds threshold", amplification_factor=0.8),
            FeedbackLoop(loop_name="Capacity Balance", type="balancing", mechanism="high utilization → capex → new capacity → lower utilization", trigger="utilization > 80%", amplification_factor=0.5),
            FeedbackLoop(loop_name="Price War Spiral", type="reinforcing", mechanism="price cut → competitor follows → lower margins → cost cutting → quality drop → customer loss", trigger="new entrant with low cost", amplification_factor=0.7),
        ],
    )


def _make_nonlinear() -> NonlinearDynamics:
    return NonlinearDynamics(
        inventory_cycle=InventoryCycle(cycle_stage="mid", inventory_pressure=0.4, price_sensitivity=0.6),
        capacity_lag=CapacityLag(capex_cycle_lag="18 months", supply_response_delay="long"),
        demand_elasticity=DemandElasticityModule(elasticity=0.3, state_dependency=True),
    )


def _make_l4() -> RegimeEngine:
    return RegimeEngine(
        current_regime="expansion",
        confidence=0.75,
        transition_probability=RegimeTransition(next_regime="transition", probability=0.3),
    )


def _make_l5() -> DistortionEngine:
    return DistortionEngine(
        market_belief="Market believes cloud growth is linear and predictable, driven by steady enterprise migration",
        structural_truth="AI workloads are driving non-linear demand spikes that strain capacity, creating structural undersupply",
        mispricing_sources=["Market underestimates AI-driven demand velocity", "Market overweights enterprise migration narrative"],
        distortion_score=0.65,
    )


def _make_l6() -> AlphaEngine:
    return AlphaEngine(
        consensus_view="Market believes cloud growth is linear and predictable, driven by steady enterprise migration",
        structural_view="AI workloads drive non-linear demand spikes straining capacity, creating structural undersupply",
        mispricing="Market underestimates the velocity and persistence of AI-driven capacity demand relative to linear models",
        alpha_signal="Long cloud infrastructure providers with AI capacity advantage — structural demand is accelerating beyond linear models",
        direction="long",
        confidence=0.8,
    )


def _make_l7() -> InvestmentMapping:
    return InvestmentMapping(
        best_positioned=[
            AssetMapping(asset="AWS", role="SV_controller", exposure=0.9, sensitivity_to_drivers=["AI Workload Growth", "Capacity Expansion"], risk_profile="Regulatory antitrust risk"),
            AssetMapping(asset="Azure", role="CV_beneficiary", exposure=0.8, sensitivity_to_drivers=["AI Workload Growth", "Market Confidence"], risk_profile="Enterprise spending slowdown"),
        ],
        overvalued=[
            AssetMapping(asset="Cloud resellers", role="FV_bottleneck", exposure=0.3, sensitivity_to_drivers=["Real Interest Rate"], risk_profile="Disintermediation by hyperscalers"),
        ],
        fragile=[
            AssetMapping(asset="Small enterprises", role="LV_reflection", exposure=0.5, sensitivity_to_drivers=["Market Confidence", "Regulatory Pressure"], risk_profile="Vendor lock-in with rising costs"),
        ],
    )


def _make_gate_report():
    return run_all_gates(_make_l1(), _make_l2(), _make_l3(), _make_l4(), _make_l6())


def _make_scan_output() -> ScanOutput:
    return ScanOutput(
        industry="Cloud Computing", region="Global", time_horizon=TimeHorizon.MID,
        meta=_make_l0(), variables=_make_l1(), drivers=_make_l2(), flow_feedback=_make_l3(),
        nonlinear_dynamics=_make_nonlinear(), regime=_make_l4(), distortion=_make_l5(),
        alpha=_make_l6(), portfolio=_make_l7(), gate_validation=_make_gate_report(),
        key_fragilities=["High distortion (65%): market misprices AI demand"],
    )


# ─── Tests ─────────────────────────────────────────────────────

def test_scan_input_defaults():
    si = ScanInput(industry="semiconductor")
    assert si.region is None
    assert si.time_horizon == TimeHorizon.MID
    assert si.peer_set == []


def test_l0_model_validation():
    l0 = _make_l0()
    assert l0.system_type == "platform economy"
    assert len(l0.system_boundary) > 10
    assert len(l0.failure_mode) > 10


def test_l1_variable_mapping():
    l1 = _make_l1()
    assert len(l1.state_variables) >= 3
    assert len(l1.flow_variables) >= 3
    assert len(l1.control_variables) >= 3
    assert len(l1.latent_variables) >= 3


def test_gate1_variable_completeness():
    from structflow.gates import gate1_variable_completeness
    assert gate1_variable_completeness(_make_l1()).passed is True


def test_gate1_fails_with_missing_variables():
    from structflow.gates import gate1_variable_completeness
    l1 = VariableMapping(state_variables=["x"], flow_variables=["y"], control_variables=["z"], latent_variables=["w"])
    assert gate1_variable_completeness(l1).passed is False


def test_gate2_driver_binding():
    from structflow.gates import gate2_driver_binding
    assert gate2_driver_binding(_make_l2()).passed is True


def test_gate2_fails_with_invalid_mapping():
    from structflow.gates import gate2_driver_binding
    l2 = DriverSpace(drivers=[Driver(name="X", category="macro", maps_to_variable="XX", direction="+", elasticity=0.5, volatility=0.3, lag="short", regime_dependency=0.7)])
    assert gate2_driver_binding(l2).passed is False


def test_gate3_feedback_completeness():
    from structflow.gates import gate3_feedback_completeness
    assert gate3_feedback_completeness(_make_l3()).passed is True


def test_gate3_fails_with_too_few_loops():
    from structflow.gates import gate3_feedback_completeness
    l3 = FlowFeedbackSystem(flow_types=["capital flow"], feedback_loops=[
        FeedbackLoop(loop_name="X", type="reinforcing", mechanism="x", trigger="y", amplification_factor=0.5)])
    assert gate3_feedback_completeness(l3).passed is False


def test_gate4_regime_engine():
    from structflow.gates import gate4_regime_engine
    assert gate4_regime_engine(_make_l4()).passed is True


def test_gate4_fails_with_invalid_regime():
    from structflow.gates import gate4_regime_engine
    l4 = RegimeEngine(current_regime="unknown", confidence=0.5, transition_probability=RegimeTransition(next_regime="expansion", probability=0.3))
    assert gate4_regime_engine(l4).passed is False


def test_gate5_alpha_generation():
    from structflow.gates import gate5_alpha_generation
    assert gate5_alpha_generation(_make_l6()).passed is True


def test_gate5_fails_with_invalid_direction():
    from structflow.gates import gate5_alpha_generation
    l6 = AlphaEngine(consensus_view="x"*20, structural_view="x"*20, mispricing="x"*20, alpha_signal="x"*20, direction="invalid", confidence=0.5)
    assert gate5_alpha_generation(l6).passed is False


def test_all_gates_pass():
    report = run_all_gates(_make_l1(), _make_l2(), _make_l3(), _make_l4(), _make_l6())
    assert report.all_passed is True
    assert len(report.failed_gates) == 0


def test_report_renders_all_sections():
    report = render_report(_make_scan_output())
    for section in ["## 1. System Mapping", "## 2. Driver System", "## 3. Flow + Feedback System",
                    "## 4. Regime Engine Output", "## 5. Distortion Engine Output",
                    "## 6. Nonlinear Cycle State", "## 7. Alpha Signal", "## 8. Investment Mapping",
                    "## 9. Cross-Layer Validation Report"]:
        assert section in report, f"Missing section: {section}"


def test_scan_output_json_serializable():
    output = _make_scan_output()
    parsed = json.loads(output.model_dump_json())
    assert parsed["industry"] == "Cloud Computing"
    assert parsed["meta"]["system_type"] == "platform economy"
    assert len(parsed["drivers"]["drivers"]) == 5
    assert parsed["alpha"]["direction"] == "long"
    assert parsed["regime"]["current_regime"] == "expansion"
    assert parsed["nonlinear_dynamics"]["inventory_cycle"]["cycle_stage"] == "mid"


def test_score_vector_bounds():
    sv = ScoreVector(control_score=0, profit_capture_score=0, risk_displacement_score=0, information_advantage_score=0, incentive_alignment_score=0)
    assert sv.control_score == 0
    sv_max = ScoreVector(control_score=10, profit_capture_score=10, risk_displacement_score=10, information_advantage_score=10, incentive_alignment_score=10)
    assert sv_max.control_score == 10


def test_structural_health_calculation():
    company = CompanyScore(name="X", role="Y", score_vector=ScoreVector(control_score=8, profit_capture_score=7, risk_displacement_score=3, information_advantage_score=9, incentive_alignment_score=7), structural_health=0)
    sv = company.score_vector
    expected = (8 * 7 * 9) / ((10 - 3) + (10 - 7))
    assert abs(expected - 504 / 10) < 0.01


def test_driver_maps_to_variable_valid():
    for d in _make_l2().drivers:
        assert d.maps_to_variable in {"SV", "FV", "CV", "LV"}


def test_alpha_direction_valid():
    assert _make_l6().direction in {"long", "short", "neutral"}


def test_feedback_loop_types():
    loops = _make_l3().feedback_loops
    assert any(l.type == "reinforcing" for l in loops)
    assert any(l.type == "balancing" for l in loops)


def test_regime_has_transition():
    r = _make_l4()
    assert r.transition_probability.next_regime in {"expansion", "contraction", "transition", "bubble", "collapse", "shock"}
    assert 0 <= r.transition_probability.probability <= 1


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
