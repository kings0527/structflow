"""Main orchestrator: runs L0→L7 pipeline with gate validation.

V2.1 Pipeline: Meta-Generalization Layer
  Search → L0 → [search] → L1 → [search] → L2 → [search] → L3 → [search] →
  L4 → [search] → L5 → [search] → L6 → [search] → L7(optional) →
  Gates → Output

Context Management:
  Each layer receives ONLY the search categories relevant to its task,
  not the full accumulated context. This prevents:
  - Hallucination: irrelevant context causes spurious connections
  - Attention drift: LLM focuses on irrelevant parts of a huge context
  - Context explosion: later layers get O(1) context instead of O(n)
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
from structflow.layers.l2_equation import run_l2
from structflow.layers.l3_drivers import run_l3
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
    """Get layer-specific search context, or None if no collector."""
    if not collector:
        return None
    return collector.get_context_for_layer(layer)


def _log_ctx(layer: str, ctx: Optional[str]) -> None:
    """Log context size for monitoring."""
    if ctx:
        tokens = DataCollector.estimate_tokens(ctx)
        console.print(f"  [dim]Context: ~{tokens:,} tokens[/dim]")
    else:
        console.print(f"  [dim]Context: none (LLM-only)[/dim]")


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
    """Execute full V2.1 Meta-Generalization pipeline."""
    if client is None:
        client = LLMClient()

    use_search = enable_search if enable_search is not None else config.data.enable_web_search

    # ── Data Collection Phase ────────────────────────────────────
    collected_raw = {}
    collector = None
    if use_search:
        console.print("[bold magenta]▶ Data Collection (Tavily + AnySearch)[/bold magenta]")
        try:
            collector = DataCollector(api_key=tavily_key, anysearch_key=anysearch_key, output_dir=output_dir)
            collected_raw = collector.collect_initial(
                industry=scan_input.industry,
                region=scan_input.region,
                peer_set=scan_input.peer_set if scan_input.peer_set else None,
            )
            if not scan_input.peer_set and "discovered_competitors" in collected_raw:
                discovered = collected_raw["discovered_competitors"].split(", ")
                scan_input.peer_set = discovered
                console.print(f"  ✓ Discovered competitors: {', '.join(discovered)}")
            engine_label = "Tavily + AnySearch" if collector.anysearch else "Tavily"
            console.print(f"  ✓ Collected {collector.total_sources} sources via {engine_label}")
        except Exception as error:
            console.print(f"  [yellow]⚠ Data collection failed: {error}[/yellow]")

    validator = OutputValidator(collected_data=collected_raw)
    retry_guard = RetryGuard(max_retries=2, min_pass_rate=0.75)

    # ── L0: Meta System Definition ──────────────────────────────
    console.print("[bold cyan]▶ L0: Meta System Definition[/bold cyan]")
    ctx_l0 = _get_ctx(collector, "l0")
    _log_ctx("L0", ctx_l0)
    l0_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l0(client, scan_input, context_data=ctx_l0, **kw),
        validate_func=lambda result: [_validate_l0(result)],
        layer_name="L0",
    )
    console.print(f"  System: {l0_result.system_type}")
    console.print(f"  SV={len(l0_result.state_variables)} CV={len(l0_result.control_variables)} "
                  f"Exog={len(l0_result.exogenous_drivers)} Feedback={len(l0_result.endogenous_feedback_loops)}")

    # ── Iterative Search: L0-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L0-driven...[/dim magenta]")
        try:
            collector.collect_after_l0(scan_input.industry, l0_result, scan_input.region)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L0 search failed: {error}[/yellow]")

    # ── L1: Variable Mapping ────────────────────────────────────
    console.print("[bold cyan]▶ L1: Variable Mapping (SV/FV/CV/LV)[/bold cyan]")
    ctx_l1 = _get_ctx(collector, "l1")
    _log_ctx("L1", ctx_l1)
    l1_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l1(client, scan_input, l0_result, context_data=ctx_l1, **kw),
        validate_func=lambda result: [validator.validate_variable_completeness(result)],
        layer_name="L1",
    )
    if enable_challenge:
        try:
            l1_result = challenge_l1(client, scan_input.industry, l1_result, context_data=ctx_l1)
        except Exception as error:
            console.print(f"  [yellow]⚔ L1 challenge failed: {error}, using original[/yellow]")
    console.print(f"  SV={len(l1_result.state_variables)} FV={len(l1_result.flow_variables)} "
                  f"CV={len(l1_result.control_variables)} LV={len(l1_result.latent_variables)}")

    # ── Iterative Search: L1-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L1-driven...[/dim magenta]")
        try:
            collector.collect_after_l1(scan_input.industry, l1_result)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L1 search failed: {error}[/yellow]")

    # ── L2: System Equation ─────────────────────────────────────
    console.print("[bold cyan]▶ L2: System Equation (α+β+γ=1)[/bold cyan]")
    ctx_l2 = _get_ctx(collector, "l2")
    _log_ctx("L2", ctx_l2)
    l2_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l2(client, scan_input, l0_result, l1_result, context_data=ctx_l2, **kw),
        validate_func=lambda result: [validator.validate_system_equation(result)],
        layer_name="L2",
    )
    if enable_challenge:
        try:
            l2_result = challenge_l2(client, scan_input.industry, l2_result, l1_result, context_data=ctx_l2)
        except Exception as error:
            console.print(f"  [yellow]⚔ L2 challenge failed: {error}, using original[/yellow]")
    console.print(f"  α={l2_result.flow_weight:.2f} β={l2_result.control_weight:.2f} γ={l2_result.latent_weight:.2f}")

    # ── Iterative Search: L2-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L2-driven...[/dim magenta]")
        try:
            collector.collect_after_l2(scan_input.industry, l2_result)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L2 search failed: {error}[/yellow]")

    # ── L3: Driver Set ──────────────────────────────────────────
    console.print("[bold cyan]▶ L3: Driver Set[/bold cyan]")
    ctx_l3 = _get_ctx(collector, "l3")
    _log_ctx("L3", ctx_l3)
    l3_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l3(client, scan_input, l0_result, l1_result, l2_result, context_data=ctx_l3, **kw),
        validate_func=lambda result: [validator.validate_driver_sources(result)],
        layer_name="L3",
    )
    if enable_challenge:
        try:
            l3_result = challenge_l3(client, scan_input.industry, l3_result, l1_result, context_data=ctx_l3)
        except Exception as error:
            console.print(f"  [yellow]⚔ L3 challenge failed: {error}, using original[/yellow]")
    for d in l3_result.drivers:
        console.print(f"  {d.name} ({d.type}, {d.direction}) dep={d.system_dependency:.0%}")

    # ── Iterative Search: L3-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L3-driven...[/dim magenta]")
        try:
            collector.collect_after_l3(scan_input.industry, l3_result)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L3 search failed: {error}[/yellow]")

    # ── L4: Regime State ────────────────────────────────────────
    console.print("[bold cyan]▶ L4: Regime State[/bold cyan]")
    ctx_l4 = _get_ctx(collector, "l4")
    _log_ctx("L4", ctx_l4)
    l4_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l4(client, scan_input, l0_result, l1_result, l2_result, l3_result, context_data=ctx_l4, **kw),
        validate_func=lambda result: [validator.validate_regime(result)],
        layer_name="L4",
    )
    if enable_challenge:
        try:
            l4_result = challenge_l4(client, scan_input.industry, l4_result, l3_result, context_data=ctx_l4)
        except Exception as error:
            console.print(f"  [yellow]⚔ L4 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Regime: {l4_result.current_regime} (confidence={l4_result.regime_confidence:.0%})")

    # ── Iterative Search: L4-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L4-driven...[/dim magenta]")
        try:
            collector.collect_after_l4(scan_input.industry, l4_result)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L4 search failed: {error}[/yellow]")

    # ── L5: Distortion Analysis ─────────────────────────────────
    console.print("[bold cyan]▶ L5: Distortion Analysis[/bold cyan]")
    ctx_l5 = _get_ctx(collector, "l5")
    _log_ctx("L5", ctx_l5)
    l5_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l5(client, scan_input, l0_result, l1_result, l2_result, l3_result, l4_result, context_data=ctx_l5, **kw),
        validate_func=lambda result: [validator.validate_distortion(result)],
        layer_name="L5",
    )
    if enable_challenge:
        try:
            l5_result = challenge_l5(client, scan_input.industry, l5_result, l4_result, context_data=ctx_l5)
        except Exception as error:
            console.print(f"  [yellow]⚔ L5 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Distortion: {l5_result.distortion_score:.0%}")
    console.print(f"  Market belief: {l5_result.market_belief[:80]}...")

    # ── Iterative Search: L5-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L5-driven (consensus vs reality)...[/dim magenta]")
        try:
            collector.collect_after_l5(scan_input.industry, l5_result)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L5 search failed: {error}[/yellow]")

    # ── L6: Alpha Signal (CORE VALUE) ───────────────────────────
    console.print("[bold cyan]▶ L6: Alpha Signal[/bold cyan]")
    ctx_l6 = _get_ctx(collector, "l6")
    _log_ctx("L6", ctx_l6)
    l6_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l6(client, scan_input, l0_result, l1_result, l2_result, l3_result, l4_result, l5_result, context_data=ctx_l6, **kw),
        validate_func=lambda result: [validator.validate_alpha_completeness(result)],
        layer_name="L6",
    )
    if enable_challenge:
        try:
            l6_result = challenge_l6(client, scan_input.industry, l6_result, l5_result, context_data=ctx_l6)
        except Exception as error:
            console.print(f"  [yellow]⚔ L6 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Consensus: {l6_result.consensus_view[:80]}...")
    console.print(f"  Alpha: {l6_result.alpha_signal[:80]}...")
    console.print(f"  Confidence: {l6_result.confidence:.0%}")

    # ── Iterative Search: L6-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L6-driven (alpha validation)...[/dim magenta]")
        try:
            collector.collect_after_l6(scan_input.industry, l6_result)
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L6 search failed: {error}[/yellow]")

    # ── L7: Portfolio Layer (Optional) ──────────────────────────
    l7_result = None
    if enable_portfolio:
        console.print("[bold cyan]▶ L7: Portfolio Mapping[/bold cyan]")
        ctx_l7 = _get_ctx(collector, "l7")
        _log_ctx("L7", ctx_l7)
        try:
            l7_result = run_l7(
                client, scan_input, l0_result, l1_result, l3_result,
                l4_result, l5_result, l6_result,
                context_data=ctx_l7,
            )
            console.print(f"  Best positioned: {', '.join(e.name for e in l7_result.best_positioned_entities)}")
            console.print(f"  Overvalued: {', '.join(e.name for e in l7_result.overvalued_entities)}")
            console.print(f"  Fragile: {', '.join(e.name for e in l7_result.fragile_entities)}")
        except Exception as error:
            console.print(f"  [yellow]⚠ L7 failed: {error}[/yellow]")

    # ── Gate Validation ──────────────────────────────────────────
    console.print("[bold cyan]▶ Gate Validation (V2.1)[/bold cyan]")
    gate_report = run_all_gates(l1_result, l2_result, l3_result, l4_result, l6_result)
    quality_gates = validator.run_all_validations(
        l1_result, l2_result, l3_result, l4_result, l5_result, l6_result, l7_result,
    )

    for gate in gate_report.gates:
        status = "[green]✓[/green]" if gate.passed else "[red]✗[/red]"
        console.print(f"  {status} {gate.gate_name}: {gate.reason}")

    console.print("[bold cyan]▶ Quality Validation[/bold cyan]")
    for gate in quality_gates:
        status = "[green]✓[/green]" if gate.passed else "[yellow]⚠[/yellow]"
        console.print(f"  {status} {gate.gate_name}: {gate.reason}")

    all_gates = gate_report.gates + quality_gates
    combined_report = GateValidationReport(gates=all_gates)

    if not combined_report.all_passed:
        failed_names = ", ".join(g.gate_name for g in combined_report.failed_gates)
        console.print(f"[bold red]⚠ Validation failed: {failed_names}[/bold red]")

    # ── Assemble Final Output ────────────────────────────────────
    key_fragilities = _extract_fragilities(l0_result, l4_result, l5_result, l6_result)

    return ScanOutput(
        industry=scan_input.industry,
        region=scan_input.region,
        time_horizon=scan_input.time_horizon,
        meta=l0_result,
        variables=l1_result,
        equation=l2_result,
        drivers=l3_result,
        regime=l4_result,
        distortion=l5_result,
        alpha=l6_result,
        portfolio=l7_result,
        gate_validation=combined_report,
        key_fragilities=key_fragilities,
    )


def _validate_l0(l0_result) -> GateResult:
    """Basic validation for L0 output."""
    issues = []
    if not l0_result.system_type or len(l0_result.system_type.strip()) < 3:
        issues.append("system_type too short")
    if not l0_result.core_function or len(l0_result.core_function.strip()) < 10:
        issues.append("core_function too short")
    if len(l0_result.state_variables) < 2:
        issues.append("state_variables too few")
    if len(l0_result.control_variables) < 2:
        issues.append("control_variables too few")

    passed = len(issues) == 0
    reason = "L0 valid" if passed else "; ".join(issues)
    return GateResult(gate_name="L0_BasicValidation", passed=passed, reason=reason)


def _extract_fragilities(l0_result, l4_result, l5_result, l6_result) -> list[str]:
    """Extract key structural fragilities from V2.1 analysis results."""
    fragilities = []

    for loop in l0_result.endogenous_feedback_loops:
        loop_lower = loop.lower()
        if any(kw in loop_lower for kw in ["crash", "collapse", "spiral", "contagion", "cascade"]):
            fragilities.append(f"Dangerous feedback loop: {loop[:100]}")

    if l4_result.current_regime == "bubble":
        fragilities.append(f"System in BUBBLE regime (confidence={l4_result.regime_confidence:.0%}) — unsustainable expansion")
    elif l4_result.current_regime == "collapse":
        fragilities.append(f"System in COLLAPSE regime (confidence={l4_result.regime_confidence:.0%}) — rapid deterioration")

    if l5_result.distortion_score > 0.6:
        fragilities.append(f"High distortion score ({l5_result.distortion_score:.0%}): market significantly misprices the system")

    if l6_result.confidence > 0.7 and l5_result.distortion_score > 0.5:
        fragilities.append(f"High-confidence alpha signal ({l6_result.confidence:.0%}): {l6_result.alpha_signal[:100]}")

    for source in l5_result.mispricing_sources[:3]:
        fragilities.append(f"Mispricing source: {source[:100]}")

    return fragilities
