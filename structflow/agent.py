"""Main orchestrator: runs L0→L1→L2→L3 pipeline with gate validation."""

from __future__ import annotations

from rich.console import Console

from structflow.gates import run_all_gates
from structflow.layers.l0_definition import run_l0
from structflow.layers.l1_structure import run_l1
from structflow.layers.l2_flow_risk import run_l2
from structflow.layers.l3_scoring import run_l3
from structflow.llm_client import LLMClient
from structflow.models import ScanInput, ScanOutput

console = Console()


def run_scan(scan_input: ScanInput, client: LLMClient | None = None) -> ScanOutput:
    """Execute full industry scan pipeline: L0 → L1 → L2 → L3 → Gates → Output."""
    if client is None:
        client = LLMClient()

    # L0: Industry Definition
    console.print("[bold cyan]▶ L0: Industry Definition[/bold cyan]")
    l0_result = run_l0(client, scan_input)
    console.print(f"  Core need: {l0_result.core_need}")
    console.print(f"  Substitution risk: {l0_result.substitution_risk} | Demand stability: {l0_result.demand_stability} | Narrative dep: {l0_result.narrative_dependency}")

    # L1: Structure Decomposition
    console.print("[bold cyan]▶ L1: Structure Decomposition[/bold cyan]")
    l1_result = run_l1(client, scan_input, l0_result)
    for role in l1_result.roles:
        console.print(f"  {role.role_type}: {', '.join(role.entities)}")

    # L2: Flow & Risk Analysis
    console.print("[bold cyan]▶ L2: Flow & Risk Analysis[/bold cyan]")
    l2_result = run_l2(client, scan_input, l0_result, l1_result)
    console.print(f"  Cash flow chain: {' → '.join(n.entity for n in l2_result.cash_flow_chain)}")
    console.print(f"  Risk concentration: {l2_result.risk_concentration_answer}")

    # L3: Scoring & Ranking
    console.print("[bold cyan]▶ L3: Scoring & Ranking[/bold cyan]")
    l3_result = run_l3(client, scan_input, l0_result, l1_result, l2_result)
    console.print(f"  Phase: [bold]{l3_result.phase.stage.value}[/bold]")
    for company in l3_result.companies_ranked:
        console.print(f"  {company.name} ({company.role}): health={company.structural_health:.2f}")

    # Gate Validation
    console.print("[bold cyan]▶ Gate Validation[/bold cyan]")
    gate_report = run_all_gates(l1_result, l2_result, l3_result)
    for gate in gate_report.gates:
        status = "[green]✓[/green]" if gate.passed else "[red]✗[/red]"
        console.print(f"  {status} {gate.gate_name}: {gate.reason}")

    if not gate_report.all_passed:
        failed_names = ", ".join(g.gate_name for g in gate_report.failed_gates)
        console.print(f"[bold red]⚠ Gate validation failed: {failed_names}[/bold red]")
        console.print("[yellow]Output may be incomplete or unreliable.[/yellow]")

    # Assemble final output
    risk_map = {
        "risk_accumulation_points": [n.model_dump() for n in l2_result.risk_accumulation_points],
        "risk_concentration": l2_result.risk_concentration_answer,
        "profit_risk_separation": l2_result.profit_risk_separation_answer,
    }

    # Key fragilities: derive from high-risk signals
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
        gate_validation=gate_report,
        key_fragilities=key_fragilities,
    )


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
