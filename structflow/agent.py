"""V2.2 Main orchestrator — Nonlinear State-Space Engine pipeline.

Pipeline: L0→L1→L2→L3→Nonlinear→L4→L5→L6→L7(optional)→Gates→Output
Each layer receives ONLY relevant search context (per-layer delivery).
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.challenge import challenge_l1, challenge_l2, challenge_l3, challenge_l4, challenge_l5, challenge_l6
from structflow.config import config
from structflow.data_collector import DataCollector
from structflow.gates import run_all_gates
from structflow.layers.l0_system import run_l0
from structflow.layers.l1_mapping import run_l1
from structflow.layers.l2_drivers import run_l2
from structflow.layers.l3_flow_feedback import run_l3
from structflow.layers.nonlinear import run_nonlinear
from structflow.layers.l4_regime import run_l4
from structflow.layers.l5_distortion import run_l5
from structflow.layers.l6_alpha import run_l6
from structflow.layers.l7_portfolio import run_l7
from structflow.llm_client import LLMClient
from structflow.models import GateResult, GateValidationReport, ScanInput, ScanOutput
from structflow.output_validator import OutputValidator
from structflow.retry_guard import RetryGuard

console = Console()


def _get_ctx(collector: DataCollector | None, layer: str) -> Optional[str]:
    if not collector:
        return None
    return collector.get_context_for_layer(layer)


def _log_ctx(layer: str, ctx: Optional[str]) -> None:
    if ctx:
        console.print(f"  [dim]Context: ~{DataCollector.estimate_tokens(ctx):,} tokens[/dim]")
    else:
        console.print(f"  [dim]Context: none[/dim]")


def run_scan(
    scan_input: ScanInput,
    client: LLMClient | None = None,
    enable_search: bool | None = None,
    tavily_key: Optional[str] = None,
    anysearch_key: Optional[str] = None,
    enable_challenge: bool = True,
    enable_portfolio: bool = True,
    output_dir: Optional[str] = None,
) -> ScanOutput:
    if client is None:
        client = LLMClient()
    use_search = enable_search if enable_search is not None else config.data.enable_web_search

    # ── Data Collection ─────────────────────────────────────────
    collected_raw = {}
    collector = None
    if use_search:
        console.print("[bold magenta]▶ Data Collection (Tavily + AnySearch)[/bold magenta]")
        try:
            collector = DataCollector(api_key=tavily_key, anysearch_key=anysearch_key, output_dir=output_dir)
            collected_raw = collector.collect_initial(
                industry=scan_input.industry, region=scan_input.region,
                peer_set=scan_input.peer_set if scan_input.peer_set else None)
            if not scan_input.peer_set and "discovered_competitors" in collected_raw:
                discovered = collected_raw["discovered_competitors"].split(", ")
                scan_input.peer_set = discovered
                console.print(f"  ✓ Discovered: {', '.join(discovered)}")
            console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ Data collection failed: {error}[/yellow]")

    validator = OutputValidator(collected_data=collected_raw)
    retry_guard = RetryGuard(max_retries=2, min_pass_rate=0.75)

    # ── L0: Meta System Definition ──────────────────────────────
    console.print("[bold cyan]▶ L0: Meta System Definition[/bold cyan]")
    ctx = _get_ctx(collector, "l0"); _log_ctx("L0", ctx)
    l0 = retry_guard.run_with_retry(
        func=lambda **kw: run_l0(client, scan_input, context_data=ctx, **kw),
        validate_func=lambda r: [_validate_l0(r)], layer_name="L0")
    console.print(f"  {l0.system_type} | {l0.core_function[:60]}...")

    if collector:
        try: collector.collect_after_l0(scan_input.industry, l0, scan_input.region); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L1: Variable Space ──────────────────────────────────────
    console.print("[bold cyan]▶ L1: Variable Space (SV/FV/CV/LV)[/bold cyan]")
    ctx = _get_ctx(collector, "l1"); _log_ctx("L1", ctx)
    l1 = retry_guard.run_with_retry(
        func=lambda **kw: run_l1(client, scan_input, l0, context_data=ctx, **kw),
        validate_func=lambda r: [validator.validate_variable_completeness(r)], layer_name="L1")
    if enable_challenge:
        try: l1 = challenge_l1(client, scan_input.industry, l1, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    console.print(f"  SV={len(l1.state_variables)} FV={len(l1.flow_variables)} CV={len(l1.control_variables)} LV={len(l1.latent_variables)}")

    if collector:
        try: collector.collect_after_l1(scan_input.industry, l1); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L2: Driver Engine ───────────────────────────────────────
    console.print("[bold cyan]▶ L2: Driver Engine[/bold cyan]")
    ctx = _get_ctx(collector, "l2"); _log_ctx("L2", ctx)
    l2 = retry_guard.run_with_retry(
        func=lambda **kw: run_l2(client, scan_input, l0, l1, context_data=ctx, **kw),
        validate_func=lambda r: [validator.validate_driver_binding(r)], layer_name="L2")
    if enable_challenge:
        try: l2 = challenge_l2(client, scan_input.industry, l2, l1, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    for d in l2.drivers:
        console.print(f"  {d.name} →{d.maps_to_variable} ({d.direction})")

    if collector:
        try: collector.collect_after_l2(scan_input.industry, l2); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L3: Flow + Feedback ─────────────────────────────────────
    console.print("[bold cyan]▶ L3: Flow + Feedback System[/bold cyan]")
    ctx = _get_ctx(collector, "l3"); _log_ctx("L3", ctx)
    l3 = retry_guard.run_with_retry(
        func=lambda **kw: run_l3(client, scan_input, l0, l1, l2, context_data=ctx, **kw),
        validate_func=lambda r: [validator.validate_feedback_completeness(r)], layer_name="L3")
    if enable_challenge:
        try: l3 = challenge_l3(client, scan_input.industry, l3, l2, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    console.print(f"  Flows={len(l3.flow_types)} Loops={len(l3.feedback_loops)}")

    if collector:
        try: collector.collect_after_l3(scan_input.industry, l3); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── Nonlinear Dynamics ──────────────────────────────────────
    console.print("[bold cyan]▶ Nonlinear Dynamics[/bold cyan]")
    ctx = _get_ctx(collector, "nonlinear"); _log_ctx("NL", ctx)
    nl = run_nonlinear(client, scan_input, l0, l1, l2, l3, context_data=ctx)
    console.print(f"  Cycle: {nl.inventory_cycle.cycle_stage} (pressure={nl.inventory_cycle.inventory_pressure:.0%})")
    console.print(f"  Capex lag: {nl.capacity_lag.capex_cycle_lag} | Elasticity: {nl.demand_elasticity.elasticity:.0%}")

    if collector:
        try: collector.collect_after_nonlinear(scan_input.industry, nl); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L4: Regime Engine ───────────────────────────────────────
    console.print("[bold cyan]▶ L4: Regime Engine[/bold cyan]")
    ctx = _get_ctx(collector, "l4"); _log_ctx("L4", ctx)
    l4 = retry_guard.run_with_retry(
        func=lambda **kw: run_l4(client, scan_input, l0, l1, l2, l3, nl, context_data=ctx, **kw),
        validate_func=lambda r: [validator.validate_regime(r)], layer_name="L4")
    if enable_challenge:
        try: l4 = challenge_l4(client, scan_input.industry, l4, l2, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    console.print(f"  Regime: {l4.current_regime} → {l4.transition_probability.next_regime} (p={l4.transition_probability.probability:.0%})")

    if collector:
        try: collector.collect_after_l4(scan_input.industry, l4); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L5: Distortion Engine ───────────────────────────────────
    console.print("[bold cyan]▶ L5: Distortion Engine[/bold cyan]")
    ctx = _get_ctx(collector, "l5"); _log_ctx("L5", ctx)
    l5 = retry_guard.run_with_retry(
        func=lambda **kw: run_l5(client, scan_input, l0, l1, l2, l4, context_data=ctx, **kw),
        validate_func=lambda r: [validator.validate_distortion(r)], layer_name="L5")
    if enable_challenge:
        try: l5 = challenge_l5(client, scan_input.industry, l5, l4, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    console.print(f"  Distortion: {l5.distortion_score:.0%}")

    if collector:
        try: collector.collect_after_l5(scan_input.industry, l5); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L6: Alpha Engine ────────────────────────────────────────
    console.print("[bold cyan]▶ L6: Alpha Engine[/bold cyan]")
    ctx = _get_ctx(collector, "l6"); _log_ctx("L6", ctx)
    l6 = retry_guard.run_with_retry(
        func=lambda **kw: run_l6(client, scan_input, l0, l1, l2, l4, l5, context_data=ctx, **kw),
        validate_func=lambda r: [validator.validate_alpha_completeness(r)], layer_name="L6")
    if enable_challenge:
        try: l6 = challenge_l6(client, scan_input.industry, l6, l5, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    console.print(f"  Alpha: {l6.alpha_signal[:80]}... ({l6.direction}, conf={l6.confidence:.0%})")

    if collector:
        try: collector.collect_after_l6(scan_input.industry, l6); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L7: Investment Mapping (Optional) ───────────────────────
    l7 = None
    if enable_portfolio:
        console.print("[bold cyan]▶ L7: Investment Mapping[/bold cyan]")
        ctx = _get_ctx(collector, "l7"); _log_ctx("L7", ctx)
        try:
            l7 = run_l7(client, scan_input, l0, l1, l2, l4, l5, l6, context_data=ctx)
            console.print(f"  Best: {', '.join(a.asset for a in l7.best_positioned)}")
        except Exception as e:
            console.print(f"  [yellow]⚠ L7 failed: {e}[/yellow]")

    # ── Gate Validation ─────────────────────────────────────────
    console.print("[bold cyan]▶ Gate Validation (V2.2)[/bold cyan]")
    gate_report = run_all_gates(l1, l2, l3, l4, l6)
    quality_gates = validator.run_all_validations(l1, l2, l3, l4, l5, l6, l7)
    for g in gate_report.gates:
        console.print(f"  {'[green]✓[/green]' if g.passed else '[red]✗[/red]'} {g.gate_name}: {g.reason}")
    for g in quality_gates:
        console.print(f"  {'[green]✓[/green]' if g.passed else '[yellow]⚠[/yellow]'} {g.gate_name}: {g.reason}")
    all_gates = gate_report.gates + quality_gates
    combined = GateValidationReport(gates=all_gates)
    if not combined.all_passed:
        console.print(f"[bold red]⚠ Failed: {', '.join(g.gate_name for g in combined.failed_gates)}[/bold red]")

    # ── Assemble Output ─────────────────────────────────────────
    return ScanOutput(
        industry=scan_input.industry, region=scan_input.region,
        time_horizon=scan_input.time_horizon,
        meta=l0, variables=l1, drivers=l2, flow_feedback=l3, nonlinear_dynamics=nl,
        regime=l4, distortion=l5, alpha=l6, portfolio=l7,
        gate_validation=combined, key_fragilities=_extract_fragilities(l0, l4, l5, l6),
    )


def _validate_l0(l0) -> GateResult:
    issues = []
    if not l0.system_type or len(l0.system_type.strip()) < 3:
        issues.append("system_type too short")
    if not l0.core_function or len(l0.core_function.strip()) < 10:
        issues.append("core_function too short")
    if not l0.system_boundary or len(l0.system_boundary.strip()) < 10:
        issues.append("system_boundary too short")
    if not l0.failure_mode or len(l0.failure_mode.strip()) < 10:
        issues.append("failure_mode too short")
    return GateResult(gate_name="L0_BasicValidation", passed=not issues, reason="L0 valid" if not issues else "; ".join(issues))


def _extract_fragilities(l0, l4, l5, l6) -> list[str]:
    f = []
    if l4.current_regime in ("bubble", "collapse", "shock"):
        f.append(f"System in {l4.current_regime.upper()} regime (confidence={l4.confidence:.0%})")
    if l4.transition_probability.probability > 0.5 and l4.transition_probability.next_regime in ("collapse", "shock", "contraction"):
        f.append(f"High probability ({l4.transition_probability.probability:.0%}) of transitioning to {l4.transition_probability.next_regime}")
    if l5.distortion_score > 0.6:
        f.append(f"High distortion ({l5.distortion_score:.0%}): market significantly misprices the system")
    if l6.confidence > 0.7 and l5.distortion_score > 0.5:
        f.append(f"High-confidence alpha ({l6.confidence:.0%}, {l6.direction}): {l6.alpha_signal[:100]}")
    for src in l5.mispricing_sources[:3]:
        f.append(f"Mispricing: {src[:100]}")
    return f
