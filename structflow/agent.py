"""Main orchestrator: runs L0→L7 pipeline with gate validation.

V2 Pipeline: Structural Alpha Discovery Engine
  Search → L0 → [search] → L1 → [search] → L2 → L3 → [search] →
  L4 → [search] → L5 → [search] → L6 → [search] → L7(optional) →
  Gates → Output

Key design decisions:
- Iterative search: each layer's output drives new targeted searches.
- Adversarial challenge: L1-L6 each get a challenge round.
- V2 Gates: Structure Completeness, Flow Completeness, Driver Ranking,
  Scenario Coverage, Alpha Generation.
- L7 Portfolio is optional (enable_portfolio parameter).
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.challenge import challenge_l1, challenge_l2, challenge_l3, challenge_l4, challenge_l5, challenge_l6
from structflow.config import config
from structflow.data_collector import DataCollector
from structflow.gates import run_all_gates
from structflow.layers.l0_definition import run_l0
from structflow.layers.l1_structure import run_l1
from structflow.layers.l2_flow import run_l2
from structflow.layers.l3_risk import run_l3
from structflow.layers.l4_drivers import run_l4
from structflow.layers.l5_scenarios import run_l5
from structflow.layers.l6_alpha import run_l6
from structflow.layers.l7_portfolio import run_l7
from structflow.llm_client import LLMClient
from structflow.models import ScanInput, ScanOutput
from structflow.output_validator import OutputValidator
from structflow.retry_guard import RetryGuard

console = Console()


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
    """Execute full V2 Structural Alpha Discovery pipeline.

    Pipeline: Dual Search → L0 → [search] → L1 → [search] → L2 → L3 → [search] →
              L4 → [search] → L5 → [search] → L6 → [search] → L7(optional) →
              Gates → Output

    Args:
        enable_portfolio: If True, run L7 Portfolio mapping (default).
    """
    if client is None:
        client = LLMClient()

    use_search = enable_search if enable_search is not None else config.data.enable_web_search

    # ── Data Collection Phase ────────────────────────────────────
    context_data = None
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

            context_data = collector.get_context_data()
            engine_label = "Tavily + AnySearch" if collector.anysearch else "Tavily"
            console.print(f"  ✓ Collected {collector.total_sources} sources via {engine_label}")
        except Exception as error:
            console.print(f"  [yellow]⚠ Data collection failed: {error}[/yellow]")
            console.print("  [yellow]Continuing with LLM knowledge only[/yellow]")

    validator = OutputValidator(collected_data=collected_raw)
    retry_guard = RetryGuard(max_retries=2, min_pass_rate=0.75)

    # ── L0: Meta Layer ──────────────────────────────────────────
    console.print("[bold cyan]▶ L0: Meta Layer[/bold cyan]")
    l0_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l0(client, scan_input, context_data=context_data, **kw),
        validate_func=lambda result: [_validate_l0(result)],
        layer_name="L0",
    )
    console.print(f"  Core need: {l0_result.core_need}")
    console.print(f"  Sub={l0_result.substitution_risk} Elasticity={l0_result.demand_elasticity} "
                  f"Narrative={l0_result.narrative_dependency} Reg={l0_result.regulatory_dependency}")

    # ── Iterative Search: L0-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L0-driven...[/dim magenta]")
        try:
            collector.collect_after_l0(scan_input.industry, l0_result, scan_input.region)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L0 search failed: {error}[/yellow]")

    # ── L1: Structure Layer ─────────────────────────────────────
    console.print("[bold cyan]▶ L1: Structure Layer[/bold cyan]")
    l1_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l1(client, scan_input, l0_result, context_data=context_data, **kw),
        validate_func=lambda result: [
            validator.validate_entities_mentioned(result),
            validator.validate_role_attribution(result),
        ],
        layer_name="L1",
    )
    if enable_challenge:
        try:
            l1_result = challenge_l1(client, scan_input.industry, l1_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L1 challenge failed: {error}, using original[/yellow]")
    for role in l1_result.roles:
        console.print(f"  {role.role_type}: {', '.join(role.entities)}")

    # ── Iterative Search: L1-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L1-driven...[/dim magenta]")
        try:
            collector.collect_after_l1(scan_input.industry, l1_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L1 search failed: {error}[/yellow]")

    # ── L2: Flow Layer ──────────────────────────────────────────
    console.print("[bold cyan]▶ L2: Flow Layer[/bold cyan]")
    l2_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l2(client, scan_input, l0_result, l1_result, context_data=context_data, **kw),
        validate_func=lambda result: [validator.validate_flow_completeness(result)],
        layer_name="L2",
    )
    if enable_challenge:
        try:
            l2_result = challenge_l2(client, scan_input.industry, l2_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L2 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Cash: {' → '.join(n.entity for n in l2_result.cash_nodes)}")
    console.print(f"  Attention: {' → '.join(n.entity for n in l2_result.attention_nodes)}")

    # ── Iterative Search: L2-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L2-driven...[/dim magenta]")
        try:
            collector.collect_after_l2(scan_input.industry, l2_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L2 search failed: {error}[/yellow]")

    # ── L3: Risk Layer ──────────────────────────────────────────
    console.print("[bold cyan]▶ L3: Risk Layer[/bold cyan]")
    l3_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l3(client, scan_input, l0_result, l1_result, l2_result, context_data=context_data, **kw),
        validate_func=lambda result: [_validate_l3(result)],
        layer_name="L3",
    )
    if enable_challenge:
        try:
            l3_result = challenge_l3(client, scan_input.industry, l3_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L3 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Profit owner: {l3_result.profit_risk_separation.profit_owner}")
    console.print(f"  Risk owner: {l3_result.profit_risk_separation.risk_owner}")
    console.print(f"  Gap score: {l3_result.profit_risk_separation.gap_score}")

    # ── Iterative Search: L3-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L3-driven...[/dim magenta]")
        try:
            collector.collect_after_l3(scan_input.industry, l3_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L3 search failed: {error}[/yellow]")

    # ── L4: Driver Layer ────────────────────────────────────────
    console.print("[bold cyan]▶ L4: Driver Layer[/bold cyan]")
    l4_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l4(client, scan_input, l0_result, l1_result, l2_result, l3_result, context_data=context_data, **kw),
        validate_func=lambda result: [validator.validate_driver_weights(result)],
        layer_name="L4",
    )
    if enable_challenge:
        try:
            l4_result = challenge_l4(client, scan_input.industry, l4_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L4 challenge failed: {error}, using original[/yellow]")
    for d in l4_result.drivers:
        console.print(f"  {d.name}: {d.importance:.0%} ({d.direction}) conf={d.confidence:.0%}")

    # ── Iterative Search: L4-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L4-driven...[/dim magenta]")
        try:
            collector.collect_after_l4(scan_input.industry, l4_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L4 search failed: {error}[/yellow]")

    # ── L5: Scenario Layer ──────────────────────────────────────
    console.print("[bold cyan]▶ L5: Scenario Layer[/bold cyan]")
    l5_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l5(client, scan_input, l0_result, l1_result, l3_result, l4_result, context_data=context_data, **kw),
        validate_func=lambda result: [validator.validate_scenario_probabilities(result)],
        layer_name="L5",
    )
    if enable_challenge:
        try:
            l5_result = challenge_l5(client, scan_input.industry, l5_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L5 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Bull={l5_result.bull.probability:.0%} Base={l5_result.base.probability:.0%} Bear={l5_result.bear.probability:.0%}")

    # ── Iterative Search: L5-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L5-driven...[/dim magenta]")
        try:
            collector.collect_after_l5(scan_input.industry, l5_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L5 search failed: {error}[/yellow]")

    # ── L6: Alpha Layer (CORE VALUE) ────────────────────────────
    console.print("[bold cyan]▶ L6: Alpha Layer[/bold cyan]")
    l6_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l6(client, scan_input, l0_result, l1_result, l3_result, l4_result, l5_result, context_data=context_data, **kw),
        validate_func=lambda result: [validator.validate_alpha_completeness(result)],
        layer_name="L6",
    )
    if enable_challenge:
        try:
            l6_result = challenge_l6(client, scan_input.industry, l6_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L6 challenge failed: {error}, using original[/yellow]")
    console.print(f"  Consensus: {l6_result.consensus[:80]}...")
    console.print(f"  Reality: {l6_result.reality[:80]}...")
    console.print(f"  Alpha: {l6_result.alpha_thesis[:80]}...")

    # ── Iterative Search: L6-driven ──────────────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L6-driven (consensus vs reality)...[/dim magenta]")
        try:
            collector.collect_after_l6(scan_input.industry, l6_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ {collector.total_sources} total sources")
        except Exception as error:
            console.print(f"  [yellow]⚠ L6 search failed: {error}[/yellow]")

    # ── L7: Portfolio Layer (Optional) ──────────────────────────
    l7_result = None
    if enable_portfolio:
        console.print("[bold cyan]▶ L7: Portfolio Layer[/bold cyan]")
        try:
            l7_result = run_l7(
                client, scan_input, l0_result, l1_result, l3_result,
                l4_result, l5_result, l6_result,
                context_data=context_data,
            )
            console.print(f"  Best positioned: {', '.join(e.name for e in l7_result.best_positioned_entities)}")
            console.print(f"  Overvalued: {', '.join(e.name for e in l7_result.overvalued_entities)}")
            console.print(f"  Fragile: {', '.join(e.name for e in l7_result.fragile_entities)}")
        except Exception as error:
            console.print(f"  [yellow]⚠ L7 failed: {error}[/yellow]")

    # ── Gate Validation ──────────────────────────────────────────
    console.print("[bold cyan]▶ Gate Validation (V2)[/bold cyan]")
    gate_report = run_all_gates(l1_result, l2_result, l4_result, l5_result, l6_result)
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
    from structflow.models import GateValidationReport
    combined_report = GateValidationReport(gates=all_gates)

    if not combined_report.all_passed:
        failed_names = ", ".join(g.gate_name for g in combined_report.failed_gates)
        console.print(f"[bold red]⚠ Validation failed: {failed_names}[/bold red]")

    # ── Assemble Final Output ────────────────────────────────────
    key_fragilities = _extract_fragilities(l0_result, l3_result, l5_result, l6_result)

    return ScanOutput(
        industry=scan_input.industry,
        region=scan_input.region,
        time_horizon=scan_input.time_horizon,
        meta=l0_result,
        structure=l1_result,
        flow=l2_result,
        risk=l3_result,
        drivers=l4_result,
        scenarios=l5_result,
        alpha=l6_result,
        portfolio=l7_result,
        gate_validation=combined_report,
        key_fragilities=key_fragilities,
    )


def _validate_l0(l0_result) -> GateResult:
    """Basic validation for L0 output."""
    from structflow.models import GateResult

    issues = []
    if not l0_result.core_need or len(l0_result.core_need.strip()) < 5:
        issues.append("core_need too short")
    for field_name, value in [
        ("substitution_risk", l0_result.substitution_risk),
        ("demand_elasticity", l0_result.demand_elasticity),
        ("narrative_dependency", l0_result.narrative_dependency),
        ("regulatory_dependency", l0_result.regulatory_dependency),
    ]:
        if not (0 <= value <= 1):
            issues.append(f"{field_name} out of range [0,1]: {value}")

    passed = len(issues) == 0
    reason = "L0 valid" if passed else "; ".join(issues)
    return GateResult(gate_name="L0_BasicValidation", passed=passed, reason=reason)


def _validate_l3(l3_result) -> GateResult:
    """Basic validation for L3 output."""
    from structflow.models import GateResult

    issues = []
    if len(l3_result.risk_concentrations) == 0:
        issues.append("no risk concentrations identified")
    if not l3_result.profit_risk_separation.profit_owner.strip():
        issues.append("profit_owner empty")
    if not l3_result.profit_risk_separation.risk_owner.strip():
        issues.append("risk_owner empty")

    passed = len(issues) == 0
    reason = "L3 valid" if passed else "; ".join(issues)
    return GateResult(gate_name="L3_BasicValidation", passed=passed, reason=reason)


def _extract_fragilities(l0_result, l3_result, l5_result, l6_result) -> list[str]:
    """Extract key structural fragilities from V2 analysis results."""
    fragilities = []

    if l0_result.substitution_risk > 0.7:
        fragilities.append(f"High substitution risk ({l0_result.substitution_risk}): core need may be fulfilled by alternatives")

    if l0_result.narrative_dependency > 0.7:
        fragilities.append(f"High narrative/policy dependency ({l0_result.narrative_dependency}): structural demand may collapse if narrative shifts")

    if l0_result.regulatory_dependency > 0.7:
        fragilities.append(f"High regulatory dependency ({l0_result.regulatory_dependency}): regulatory changes could disrupt the industry")

    if l0_result.demand_elasticity > 0.7:
        fragilities.append(f"High demand elasticity ({l0_result.demand_elasticity}): demand is highly sensitive to price changes")

    if l3_result.profit_risk_separation.gap_score > 0.5:
        fragilities.append(
            f"Profit-risk separation (gap={l3_result.profit_risk_separation.gap_score}): "
            f"{l3_result.profit_risk_separation.profit_owner} profits while "
            f"{l3_result.profit_risk_separation.risk_owner} bears risk — moral hazard"
        )

    for rc in l3_result.risk_concentrations:
        if rc.severity > 0.7:
            fragilities.append(f"Critical risk concentration: {rc.entity} ({rc.risk_type}, severity={rc.severity})")

    if l5_result.bear.probability > 0.3:
        fragilities.append(f"High bear scenario probability ({l5_result.bear.probability:.0%}): downside risk is significant")

    if l6_result.mispricing:
        fragilities.append(f"Market mispricing detected: {l6_result.mispricing[:100]}")

    return fragilities
