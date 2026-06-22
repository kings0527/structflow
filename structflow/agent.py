"""Main orchestrator: runs L0→L1→L2→L3 pipeline with gate validation.

Key design decisions:
- Heuristic search: after L1 and L2, additional web searches are performed
  based on the identified entities and risks, enriching context for deeper layers.
- Retry with feedback: failed validation reasons are fed back to the LLM on retry.
- Cross-layer consistency: entities in L2/L3 must trace back to L1 roles.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.challenge import challenge_l1, challenge_l2, challenge_l3
from structflow.config import config
from structflow.data_collector import DataCollector
from structflow.gates import run_all_gates
from structflow.layers.l0_definition import run_l0
from structflow.layers.l1_structure import run_l1
from structflow.layers.l2_flow_risk import run_l2
from structflow.layers.l3_scoring import run_l3
from structflow.llm_client import LLMClient
from structflow.models import ScanInput, ScanOutput
from structflow.output_validator import OutputValidator
from structflow.retry_guard import RetryGuard
from structflow.score_calibrator import ScoreCalibrator

console = Console()


def run_scan(
    scan_input: ScanInput,
    client: LLMClient | None = None,
    enable_search: bool | None = None,
    tavily_key: Optional[str] = None,
    anysearch_key: Optional[str] = None,
    enable_challenge: bool = True,
    output_dir: Optional[str] = None,
) -> ScanOutput:
    """Execute full industry scan pipeline.

    Pipeline: Dual Search (Tavily+AnySearch) → L0 → [iterative search] →
              L1 → [iterative search] → L2 → [iterative search] → L3 →
              Gates → Output

    Search strategy: each layer's output drives new targeted searches,
    so the LLM always has fresh data relevant to its specific findings.

    If output_dir is provided, search data is saved to that directory.
    """
    if client is None:
        client = LLMClient()

    # Determine if web search is enabled
    use_search = enable_search if enable_search is not None else config.data.enable_web_search

    # ── Data Collection Phase (Dual Search) ───────────────────────
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

            # Use discovered competitors if user didn't provide peers
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

    # Initialize validation and retry systems
    validator = OutputValidator(collected_data=collected_raw)
    retry_guard = RetryGuard(max_retries=2, min_pass_rate=0.75)

    # ── L0: Industry Definition ──────────────────────────────────
    console.print("[bold cyan]▶ L0: Industry Definition[/bold cyan]")
    l0_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l0(client, scan_input, context_data=context_data, **kw),
        validate_func=lambda result: [_validate_l0(result)],
        layer_name="L0",
    )
    console.print(f"  Core need: {l0_result.core_need}")
    console.print(f"  Substitution risk: {l0_result.substitution_risk} | Demand stability: {l0_result.demand_stability} | Narrative dep: {l0_result.narrative_dependency}")

    # ── Iterative Search: driven by L0 output ─────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L0-driven (core need, substitution, narrative)...[/dim magenta]")
        try:
            collector.collect_after_l0(scan_input.industry, l0_result, scan_input.region)
            context_data = collector.get_context_data()
            console.print(f"  ✓ Context enriched with L0-driven search ({collector.total_sources} total sources)")
        except Exception as error:
            console.print(f"  [yellow]⚠ L0 iterative search failed: {error}[/yellow]")

    # ── L1: Structure Decomposition ──────────────────────────────
    console.print("[bold cyan]▶ L1: Structure Decomposition[/bold cyan]")
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

    # ── Iterative Search: driven by L1 entities & power dynamics ──
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L1-driven (entity power, pricing dynamics)...[/dim magenta]")
        try:
            collector.collect_after_l1(scan_input.industry, l1_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ Context enriched with L1-driven search ({collector.total_sources} total sources)")
        except Exception as error:
            console.print(f"  [yellow]⚠ L1 iterative search failed: {error}[/yellow]")

    # ── L2: Flow & Risk Analysis ─────────────────────────────────
    console.print("[bold cyan]▶ L2: Flow & Risk Analysis[/bold cyan]")
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
    console.print(f"  Cash flow chain: {' → '.join(n.entity for n in l2_result.cash_flow_chain)}")
    console.print(f"  Risk concentration: {l2_result.risk_concentration_answer}")

    # ── Iterative Search: driven by L2 risks & hidden subsidies ──
    if collector:
        console.print("[dim magenta]  ▶ Iterative search: L2-driven (risk concentration, subsidies, profit-risk separation)...[/dim magenta]")
        try:
            collector.collect_after_l2(scan_input.industry, l2_result)
            context_data = collector.get_context_data()
            console.print(f"  ✓ Context enriched with L2-driven search ({collector.total_sources} total sources)")
        except Exception as error:
            console.print(f"  [yellow]⚠ L2 iterative search failed: {error}[/yellow]")

    # ── L3: Scoring & Ranking ────────────────────────────────────
    console.print("[bold cyan]▶ L3: Scoring & Ranking[/bold cyan]")
    l3_result = retry_guard.run_with_retry(
        func=lambda **kw: run_l3(client, scan_input, l0_result, l1_result, l2_result, context_data=context_data, **kw),
        validate_func=lambda result: [validator.validate_score_range(result)],
        layer_name="L3",
    )
    if enable_challenge:
        try:
            l3_result = challenge_l3(client, scan_input.industry, l3_result, context_data=context_data)
        except Exception as error:
            console.print(f"  [yellow]⚔ L3 challenge failed: {error}, using original[/yellow]")
    # Apply score calibration for cross-model consistency
    l3_result = ScoreCalibrator.calibrate_l3(l3_result)
    console.print(f"  Phase: [bold]{l3_result.phase.stage.value}[/bold]")
    for company in l3_result.companies_ranked:
        console.print(f"  {company.name} ({company.role}): health={company.structural_health:.2f}")

    # ── Gate Validation ──────────────────────────────────────────
    console.print("[bold cyan]▶ Gate Validation[/bold cyan]")
    gate_report = run_all_gates(l1_result, l2_result, l3_result)
    quality_gates = validator.run_all_validations(l1_result, l2_result, l3_result)

    for gate in gate_report.gates:
        status = "[green]✓[/green]" if gate.passed else "[red]✗[/red]"
        console.print(f"  {status} {gate.gate_name}: {gate.reason}")

    console.print("[bold cyan]▶ Quality Validation[/bold cyan]")
    for gate in quality_gates:
        status = "[green]✓[/green]" if gate.passed else "[yellow]⚠[/yellow]"
        console.print(f"  {status} {gate.gate_name}: {gate.reason}")

    # Merge quality gates into gate report
    all_gates = gate_report.gates + quality_gates
    from structflow.models import GateValidationReport
    combined_report = GateValidationReport(gates=all_gates)

    if not combined_report.all_passed:
        failed_names = ", ".join(g.gate_name for g in combined_report.failed_gates)
        console.print(f"[bold red]⚠ Validation failed: {failed_names}[/bold red]")
        console.print("[yellow]Output may be incomplete or unreliable.[/yellow]")

    # ── Assemble Final Output ────────────────────────────────────
    risk_map = {
        "risk_accumulation_points": [n.model_dump() for n in l2_result.risk_accumulation_points],
        "risk_concentration": l2_result.risk_concentration_answer,
        "profit_risk_separation": l2_result.profit_risk_separation_answer,
    }

    key_fragilities = _extract_fragilities(l0_result, l2_result, l3_result)

    return ScanOutput(
        industry=scan_input.industry,
        region=scan_input.region,
        time_horizon=scan_input.time_horizon,
        industry_definition=l0_result,
        structure=l1_result,
        power_map=l1_result.power_matrix,
        flow_analysis=l2_result,
        risk_map=risk_map,
        industry_structure_score=l3_result.industry_score,
        companies_ranked=l3_result.companies_ranked,
        structural_phase=l3_result.phase,
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
        ("demand_stability", l0_result.demand_stability),
        ("narrative_dependency", l0_result.narrative_dependency),
    ]:
        if not (0 <= value <= 1):
            issues.append(f"{field_name} out of range [0,1]: {value}")

    passed = len(issues) == 0
    reason = "L0 valid" if passed else "; ".join(issues)
    return GateResult(gate_name="L0_BasicValidation", passed=passed, reason=reason)


def _extract_fragilities(l0_result, l2_result, l3_result) -> list[str]:
    """Extract key structural fragilities from analysis results."""
    fragilities = []

    if l0_result.substitution_risk > 0.7:
        fragilities.append(f"High substitution risk ({l0_result.substitution_risk}): core need may be fulfilled by alternatives")

    if l0_result.narrative_dependency > 0.7:
        fragilities.append(f"High narrative/policy dependency ({l0_result.narrative_dependency}): structural demand may collapse if narrative shifts")

    if l0_result.demand_stability < 0.3:
        fragilities.append(f"Volatile demand ({l0_result.demand_stability}): revenue predictability is low")

    if l2_result.hidden_subsidy_sources:
        subsidy_names = ", ".join(n.entity for n in l2_result.hidden_subsidy_sources)
        fragilities.append(f"Hidden subsidy dependency: {subsidy_names} — system may not be self-sustaining")

    if "separated" in l2_result.profit_risk_separation_answer.lower() or "yes" in l2_result.profit_risk_separation_answer.lower():
        fragilities.append("Profit-risk separation detected: entities profit without bearing proportional risk — moral hazard present")

    if l3_result.phase.stage.value in ("decline", "disrupted"):
        fragilities.append(f"Industry phase: {l3_result.phase.stage.value} — structural deterioration underway")

    return fragilities
