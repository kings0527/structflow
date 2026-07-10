"""V2.2 Main orchestrator — Nonlinear State-Space Engine pipeline.

Pipeline: L0→L1→L2→L3→Nonlinear→L4→L5→L6→L7(optional)→Gates→Output
Each layer receives ONLY relevant search context (per-layer delivery).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console

from structflow.challenge import challenge_l1, challenge_l2, challenge_l3, challenge_l4, challenge_l5, challenge_l6, challenge_l7
from structflow.config import config
from structflow.data_collector import DataCollector
from structflow.input_resolver import (
    InputKind,
    fallback_profile,
    profile_context,
    run_input_resolution,
    save_profile,
)
from structflow.coverage_contract import CoverageValidator, coverage_contract
from structflow.financial_consistency import (
    FinancialConsistencyValidator,
    financial_extraction_contract,
)
from structflow.market_snapshot import resolve_consensus_market_snapshot
from structflow.research_clock import current_analysis_date, temporal_contract
from structflow.temporal_grounding import TemporalGroundingValidator
from structflow.investment_validation import InvestmentValidator
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
from structflow.research_gates import ResearchValidator
from structflow.retry_guard import RetryGuard
from structflow.system_templates import get_template_methodology
from structflow.workspace import MaterialLibrary

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
    data_dir: Optional[str] = None,
    material_paths: Optional[list[str]] = None,
    refresh_search: bool = False,
) -> ScanOutput:
    if client is None:
        client = LLMClient()
    analysis_date = current_analysis_date()
    use_search = enable_search if enable_search is not None else config.data.enable_web_search
    data_path = Path(data_dir) if data_dir else None
    search_path = data_path / "search" if data_path else (
        Path(output_dir) if output_dir else None
    )
    material_records = []
    if data_path:
        material_library = MaterialLibrary(data_path / "materials")
        material_status = material_library.sync(material_paths or [])
        material_records = material_library.evidence_records()
        for error in material_status["errors"]:
            console.print(f"  [yellow]⚠ Material ingestion: {error}[/yellow]")

    # ── Data Collection ─────────────────────────────────────────
    collected_raw = {}
    collector = None
    cache_file = search_path / "search_data.json" if search_path else None
    cache_available = bool(cache_file and cache_file.exists())
    if use_search or cache_available or material_records:
        console.print("[bold magenta]▶ Data Collection (cache + search + materials)[/bold magenta]")
        try:
            cache_only = (cache_available and not refresh_search) or not use_search
            collector = DataCollector(
                api_key=tavily_key,
                anysearch_key=anysearch_key,
                output_dir=str(search_path) if search_path else output_dir,
                industry=scan_input.industry,
                cache_only=cache_only,
            )
            collector.set_analysis_date(analysis_date)
            loaded = (
                collector.load_cache(search_path, cache_only=True)
                if cache_available and not refresh_search and search_path
                else 0
            )
            if use_search and (refresh_search or loaded == 0):
                collected_raw = collector.collect_initial(
                    industry=scan_input.industry, region=scan_input.region,
                    peer_set=scan_input.peer_set if scan_input.peer_set else None,
                    discover_competitors=False)
                console.print(f"  ✓ {collector.total_sources} fetched sources")
            elif loaded:
                console.print(f"  ✓ Reused {loaded} cached evidence records")
            if material_records:
                collector.context.add_evidence(material_records)
                console.print(
                    f"  ✓ Loaded {len(material_records)} material evidence chunks"
                )
        except Exception as error:
            console.print(f"  [yellow]⚠ Data collection failed: {error}[/yellow]")

    # ── Input Resolution: identity, material segments, current facts ──
    research_validator = ResearchValidator()
    coverage_validator = CoverageValidator()
    financial_validator = FinancialConsistencyValidator()
    temporal_validator = TemporalGroundingValidator()
    investment_validator = InvestmentValidator()
    resolution_retry_guard = RetryGuard(
        max_retries=1, min_pass_rate=0.75
    )
    console.print("[bold cyan]▶ Input Resolution[/bold cyan]")
    resolution_context = (
        collector.get_resolution_context() if collector else ""
    )
    integrity_contract = "\n\n".join((
        temporal_contract(analysis_date),
        financial_extraction_contract(analysis_date),
    ))
    resolution_context = "\n\n".join(
        part for part in (integrity_contract, resolution_context) if part
    )
    profile = None
    if collector:
        try:
            profile = resolution_retry_guard.run_with_retry(
                func=lambda **kw: run_input_resolution(
                    client,
                    scan_input,
                    resolution_context,
                    **kw,
                ),
                validate_func=lambda value: [
                    research_validator.validate_entity_profile(
                        value,
                        collector.evidence_source_ids,
                    ),
                    financial_validator.validate(
                        value, analysis_date
                    ),
                ],
                layer_name="Input Resolution",
            )
            if profile.evidence_gaps:
                collector.collect_profile_gaps(profile)
                resolution_context = (
                    collector.get_resolution_context()
                )
                resolution_context = "\n\n".join((
                    integrity_contract,
                    resolution_context,
                ))
                profile = resolution_retry_guard.run_with_retry(
                    func=lambda **kw: run_input_resolution(
                        client,
                        scan_input,
                        resolution_context,
                        **kw,
                    ),
                    validate_func=lambda value: [
                        research_validator.validate_entity_profile(
                            value,
                            collector.evidence_source_ids,
                        ),
                        financial_validator.validate(
                            value, analysis_date
                        ),
                    ],
                    layer_name="Input Resolution Final",
                )
            snapshot = resolve_consensus_market_snapshot(
                collector.context.evidence.records(),
                profile,
                analysis_date,
            )
            if snapshot:
                profile = profile.model_copy(
                    update={"market_snapshot": snapshot}
                )
            collector.set_profile_context(
                "\n\n".join((
                    profile_context(profile),
                    coverage_contract(profile),
                    temporal_contract(analysis_date),
                ))
            )
            save_profile(
                profile,
                str(data_path) if data_path else output_dir,
            )
            if (
                profile.input_kind == InputKind.INDUSTRY
                and not scan_input.peer_set
            ):
                peers = collector.collect_competitors(
                    scan_input.industry,
                    scan_input.region,
                )
                if peers:
                    scan_input.peer_set = peers
                    console.print(
                        f"  ✓ Discovered peers: {', '.join(peers)}"
                    )
        except Exception as error:
            console.print(
                f"  [yellow]⚠ Input resolution degraded: "
                f"{error}[/yellow]"
            )
    if profile is None:
        profile = fallback_profile(
            scan_input, resolution_context
        )
        if collector:
            collector.set_profile_context(
                profile_context(profile)
            )
        save_profile(
            profile,
            str(data_path) if data_path else output_dir,
        )
    snapshot_text = (
        f" | price={profile.market_snapshot.price} "
        f"as_of={profile.market_snapshot.as_of}"
        if profile.market_snapshot else ""
    )
    console.print(
        f"  {profile.input_kind.value}: "
        f"{profile.canonical_name}"
        f"{f' ({profile.ticker})' if profile.ticker else ''}"
        f" | segments={len(profile.material_segments)}"
        f"{snapshot_text}"
    )

    validator = OutputValidator(collected_data=collected_raw)
    retry_guard = RetryGuard(max_retries=2, min_pass_rate=0.75)

    # ── L0: Meta System Definition ──────────────────────────────
    console.print("[bold cyan]▶ L0: Meta System Definition[/bold cyan]")
    ctx = _get_ctx(collector, "l0"); _log_ctx("L0", ctx)
    l0 = retry_guard.run_with_retry(
        func=lambda **kw: run_l0(client, scan_input, context_data=ctx, **kw),
        validate_func=lambda r: [
            _validate_l0(r),
            coverage_validator.validate_l0(
                r, profile
            ),
        ], layer_name="L0")
    console.print(f"  {l0.system_type} | {l0.core_function[:60]}...")

    # Match system template based on L0's system_type
    template = None
    if collector:
        template = collector.set_template(l0.system_type)
        if template:
            console.print(f"  [dim]Template: {template.name} (variables + search keywords loaded)[/dim]")
        else:
            console.print(f"  [dim]Template: no match (LLM-generated variables)[/dim]")

    if collector:
        try: collector.collect_after_l0(scan_input.industry, l0, scan_input.region); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L1: Variable Space ──────────────────────────────────────
    console.print("[bold cyan]▶ L1: Variable Space (SV/FV/CV/LV)[/bold cyan]")
    ctx = _get_ctx(collector, "l1"); _log_ctx("L1", ctx)
    validate_l1 = lambda r: [
        validator.validate_variable_completeness(r),
        coverage_validator.validate_l1(r, profile),
    ]
    l1 = retry_guard.run_with_retry(
        func=lambda **kw: run_l1(client, scan_input, l0, context_data=ctx,
                                  template_methodology=get_template_methodology(template), **kw),
        validate_func=validate_l1, layer_name="L1")
    if enable_challenge:
        try: l1 = challenge_l1(client, scan_input.industry, l1, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    if any(
        not gate.passed and gate.gate_name.startswith("Hard_")
        for gate in validate_l1(l1)
    ):
        l1 = retry_guard.run_with_retry(
            func=lambda **kw: run_l1(
                client,
                scan_input,
                l0,
                context_data=ctx,
                template_methodology=get_template_methodology(template),
                **kw,
            ),
            validate_func=validate_l1,
            layer_name="L1 Final",
        )
    console.print(f"  SV={len(l1.state_variables)} FV={len(l1.flow_variables)} CV={len(l1.control_variables)} LV={len(l1.latent_variables)}")

    if collector:
        try: collector.collect_after_l1(scan_input.industry, l1); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L2: Driver Engine ───────────────────────────────────────
    console.print("[bold cyan]▶ L2: Driver Engine[/bold cyan]")
    ctx = _get_ctx(collector, "l2"); _log_ctx("L2", ctx)
    validate_l2 = lambda r: [
        validator.validate_driver_binding(r),
        coverage_validator.validate_l2(r, profile),
    ]
    l2 = retry_guard.run_with_retry(
        func=lambda **kw: run_l2(client, scan_input, l0, l1, context_data=ctx, **kw),
        validate_func=validate_l2, layer_name="L2")
    if enable_challenge:
        try: l2 = challenge_l2(client, scan_input.industry, l2, l1, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    if any(
        not gate.passed and gate.gate_name.startswith("Hard_")
        for gate in validate_l2(l2)
    ):
        l2 = retry_guard.run_with_retry(
            func=lambda **kw: run_l2(
                client,
                scan_input,
                l0,
                l1,
                context_data=ctx,
                **kw,
            ),
            validate_func=validate_l2,
            layer_name="L2 Final",
        )
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
    validate_l5 = lambda r: [
        validator.validate_distortion(r),
        research_validator.validate_citations(
            r,
            (
                collector.evidence_source_ids
                if collector else set()
            ),
            "L5",
        ),
    ]
    l5 = retry_guard.run_with_retry(
        func=lambda **kw: run_l5(client, scan_input, l0, l1, l2, l4, context_data=ctx, **kw),
        validate_func=validate_l5, layer_name="L5")
    if enable_challenge:
        try: l5 = challenge_l5(client, scan_input.industry, l5, l4, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    if any(
        not gate.passed
        and gate.gate_name.startswith("Hard_")
        for gate in validate_l5(l5)
    ):
        l5 = retry_guard.run_with_retry(
            func=lambda **kw: run_l5(
                client,
                scan_input,
                l0,
                l1,
                l2,
                l4,
                context_data=ctx,
                **kw,
            ),
            validate_func=validate_l5,
            layer_name="L5 Final",
        )
    console.print(f"  Distortion: {l5.distortion_score:.0%}")

    if collector:
        try: collector.collect_after_l5(scan_input.industry, l5); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── Contradiction Search (防确认偏差) ──────────────────────
    if collector:
        console.print("[dim magenta]  ▶ Contradiction search: looking for counter-evidence...[/dim magenta]")
        try: collector.collect_contradiction(scan_input.industry, l5); console.print(f"  ✓ {collector.total_sources} sources")
        except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

    # ── L6: Alpha Engine ────────────────────────────────────────
    console.print("[bold cyan]▶ L6: Alpha Engine[/bold cyan]")
    ctx = _get_ctx(collector, "l6"); _log_ctx("L6", ctx)
    validate_l6 = lambda r: [
        validator.validate_alpha_completeness(r),
        research_validator.validate_citations(
            r,
            (
                collector.evidence_source_ids
                if collector else set()
            ),
            "L6",
        ),
        temporal_validator.validate_alpha(
            r, profile, analysis_date
        ),
        research_validator.validate_financial_quality(
            r, profile
        ),
        research_validator.validate_advice_boundary(r),
        research_validator.validate_regime_alpha_reconciliation(
            l4, r
        ),
    ]
    l6 = retry_guard.run_with_retry(
        func=lambda **kw: run_l6(client, scan_input, l0, l1, l2, l4, l5, context_data=ctx, **kw),
        validate_func=validate_l6, layer_name="L6")
    if enable_challenge:
        try: l6 = challenge_l6(client, scan_input.industry, l6, l5, context_data=ctx)
        except Exception as e: console.print(f"  [yellow]⚔ {e}[/yellow]")
    if any(
        not gate.passed
        and gate.gate_name.startswith("Hard_")
        for gate in validate_l6(l6)
    ):
        l6 = retry_guard.run_with_retry(
            func=lambda **kw: run_l6(
                client,
                scan_input,
                l0,
                l1,
                l2,
                l4,
                l5,
                context_data=ctx,
                **kw,
            ),
            validate_func=validate_l6,
            layer_name="L6 Final",
        )
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

        # L7 evidence acquisition: draft first, then verify concrete assets.
        if collector and l7:
            console.print("[dim magenta]  ▶ Post-L7 search: verifying assets...[/dim magenta]")
            try:
                collector.collect_after_l7(scan_input.industry, l7)
                ctx = _get_ctx(collector, "l7")
                _log_ctx("L7 verification", ctx)
                console.print(
                    f"  ✓ {collector.total_sources} "
                    "unique evidence records"
                )
            except Exception as e: console.print(f"  [yellow]⚠ {e}[/yellow]")

        # L7 finalization consumes the newly acquired asset evidence.
        if enable_challenge and l7:
            try:
                l7 = challenge_l7(
                    client,
                    scan_input.industry,
                    l7,
                    l6,
                    context_data=ctx,
                )
            except Exception as e:
                console.print(f"  [yellow]⚔ L7 challenge failed: {e}[/yellow]")
        elif collector and l7:
            try:
                l7 = run_l7(
                    client,
                    scan_input,
                    l0,
                    l1,
                    l2,
                    l4,
                    l5,
                    l6,
                    context_data=ctx,
                )
            except Exception as e:
                console.print(
                    f"  [yellow]⚠ L7 evidence finalization "
                    f"failed: {e}[/yellow]"
                )

        if l7:
            l7_evidence_gate = investment_validator.validate(
                l7,
                profile,
                analysis_date,
                collector.evidence_source_ids if collector else set(),
            )
            if not l7_evidence_gate.passed:
                try:
                    l7 = run_l7(
                        client,
                        scan_input,
                        l0,
                        l1,
                        l2,
                        l4,
                        l5,
                        l6,
                        context_data=ctx,
                        retry_feedback=l7_evidence_gate.reason,
                        temperature=0.5,
                    )
                except Exception as e:
                    console.print(
                        f"  [yellow]⚠ L7 evidence retry "
                        f"failed: {e}[/yellow]"
                    )

    if collector and collector.failed_requests:
        console.print(
            "[yellow]⚠ Evidence acquisition degraded: "
            f"{collector.failed_requests} provider/policy failures "
            "were recorded[/yellow]"
        )

    # ── Gate Validation ─────────────────────────────────────────
    console.print("[bold cyan]▶ Gate Validation (V2.2)[/bold cyan]")
    gate_report = run_all_gates(l1, l2, l3, l4, l6)
    quality_gates = validator.run_all_validations(l1, l2, l3, l4, l5, l6, l7)
    quality_gates += [
        research_validator.validate_entity_profile(
            profile,
            (
                collector.evidence_source_ids
                if collector else set()
            ),
        ),
        financial_validator.validate(profile, analysis_date),
        coverage_validator.validate_l0(
            l0, profile
        ),
        coverage_validator.validate_l1(
            l1, profile
        ),
        coverage_validator.validate_l2(
            l2, profile
        ),
        research_validator.validate_citations(
            l5,
            (
                collector.evidence_source_ids
                if collector else set()
            ),
            "L5",
        ),
        *validate_l6(l6)[1:],
        investment_validator.validate(
            l7,
            profile,
            analysis_date,
            collector.evidence_source_ids if collector else set(),
        ),
    ]
    for g in gate_report.gates:
        console.print(f"  {'[green]✓[/green]' if g.passed else '[red]✗[/red]'} {g.gate_name}: {g.reason}")
    for g in quality_gates:
        console.print(f"  {'[green]✓[/green]' if g.passed else '[yellow]⚠[/yellow]'} {g.gate_name}: {g.reason}")
    all_gates = gate_report.gates + quality_gates
    combined = GateValidationReport(gates=all_gates)
    if not combined.all_passed:
        console.print(f"[bold red]⚠ Failed: {', '.join(g.gate_name for g in combined.failed_gates)}[/bold red]")
    hard_failures = [
        gate
        for gate in combined.failed_gates
        if gate.gate_name.startswith("Hard_")
    ]
    if hard_failures:
        details = "; ".join(
            f"{gate.gate_name}: {gate.reason}"
            for gate in hard_failures
        )
        raise RuntimeError(
            "Research integrity gates failed; report publication blocked. "
            + details
        )

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
