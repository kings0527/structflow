import json
from pathlib import Path

from structflow.input_resolver import EntityProfile, InputKind
from structflow.models import TimeHorizon
from structflow.skill_runtime import (
    AnalysisDraft,
    GenerationMode,
    ResearchRequest,
    advance_stage,
    compile_layer_context,
    finalize_draft,
    import_evidence,
    initialize_run,
    save_profile,
)
from structflow import skill_runtime


def _draft(source_ids: list[str]) -> dict:
    support = source_ids[:2]
    contradiction = source_ids[2:3]
    variables = {
        "state_variables": [
            "installed capacity",
            "inventory stock",
            "customer base",
        ],
        "flow_variables": [
            "capacity utilization flow",
            "order inflow",
            "operating cash flow",
        ],
        "control_variables": [
            "pricing rule",
            "credit constraint",
            "entry standard",
        ],
        "latent_variables": [
            "capacity expectation",
            "risk appetite",
            "customer trust",
        ],
    }
    return {
        "industry": "Example Industry",
        "region": "Global",
        "time_horizon": "mid",
        "meta": {
            "system_type": "manufacturing system",
            "core_function": "Convert constrained capacity into essential output.",
            "system_boundary": "Includes capacity, inputs, orders, and distribution; excludes unrelated services.",
            "failure_mode": "Input shortage reduces output, drains cash, and forces capacity shutdown.",
        },
        "variables": variables,
        "drivers": {
            "drivers": [
                {
                    "name": "capacity utilization",
                    "category": "structural",
                    "proxy": "monthly utilization rate from industry association",
                    "maps_to_variable": "FV",
                    "direction": "nonlinear",
                    "elasticity": 0.8,
                    "volatility": 0.4,
                    "lag": "mid",
                    "regime_dependency": 0.7,
                },
                {
                    "name": "credit constraint",
                    "category": "financial",
                    "proxy": "aggregate financing growth rate",
                    "maps_to_variable": "CV",
                    "direction": "-",
                    "elasticity": 0.5,
                    "volatility": 0.5,
                    "lag": "mid",
                    "regime_dependency": 0.8,
                },
                {
                    "name": "capacity expectation",
                    "category": "behavioral",
                    "proxy": "capex guidance revisions in filings",
                    "maps_to_variable": "LV",
                    "direction": "nonlinear",
                    "elasticity": 0.4,
                    "volatility": 0.7,
                    "lag": "short",
                    "regime_dependency": 0.8,
                },
            ]
        },
        "flow_feedback": {
            "flow_types": [
                "capital flow",
                "goods flow",
                "information flow",
                "risk flow",
            ],
            "feedback_loops": [
                {
                    "loop_name": "Capacity expansion",
                    "type": "reinforcing",
                    "mechanism": "orders raise utilization, cash flow, and capacity investment",
                    "trigger": "utilization exceeds threshold",
                    "amplification_factor": 0.7,
                    "delay": "mid",
                },
                {
                    "loop_name": "Inventory balance",
                    "type": "balancing",
                    "mechanism": "inventory accumulation lowers price and production",
                    "trigger": "inventory exceeds demand",
                    "amplification_factor": 0.5,
                    "delay": "short",
                },
                {
                    "loop_name": "Credit contraction",
                    "type": "reinforcing",
                    "mechanism": "cash weakness tightens credit and reduces output",
                    "trigger": "cash coverage falls",
                    "amplification_factor": 0.6,
                    "delay": "mid",
                },
            ],
            "chokepoints": [
                {
                    "name": "credit supply",
                    "flow_type": "capital flow",
                    "concentration": "concentrated",
                },
            ],
        },
        "nonlinear_dynamics": {
            "inventory_cycle": {
                "cycle_stage": "mid",
                "inventory_pressure": 0.4,
                "price_sensitivity": 0.6,
            },
            "capacity_lag": {
                "capex_cycle_lag": "18 months",
                "supply_response_delay": "long",
            },
            "demand_elasticity": {
                "elasticity": 0.5,
                "state_dependency": True,
            },
        },
        "regime": {
            "current_regime": "transition",
            "confidence": 0.65,
            "transition_probability": {
                "next_regime": "expansion",
                "probability": 0.45,
            },
            "regime_distribution": {
                "transition": 0.40,
                "expansion": 0.45,
                "contraction": 0.05,
                "bubble": 0.04,
                "collapse": 0.03,
                "shock": 0.03,
            },
            "early_warning_signals": [
                {
                    "signal": "none_observed",
                    "proxy": "order-inflow volatility decay after recent shocks",
                },
            ],
        },
        "distortion": {
            "market_belief": "Consensus expects stable linear capacity utilization growth.",
            "structural_truth": "Capacity utilization changes nonlinearly with order inflow.",
            "mispricing_sources": [
                "capacity utilization is more nonlinear than consensus expects"
            ],
            "distortion_score": 0.55,
            "persistence_mechanism": (
                "Index-tracking funds must hold capacity leaders regardless "
                "of order inflow, so the utilization gap stays open."
            ),
            "narrative_stage": "spreading",
            "narrative_stage_proxy": "Coverage of capacity tightness is still broadening across outlets.",
            "supporting_evidence_ids": support,
            "contradicting_evidence_ids": contradiction,
        },
        "alpha": {
            "consensus_view": "Consensus expects stable linear capacity utilization growth.",
            "structural_view": "Capacity utilization follows nonlinear order and inventory feedback.",
            "mispricing": "Capacity utilization regime dependence is underappreciated.",
            "alpha_signal": "Neutral capacity utilization exposure until order inflow confirms the regime.",
            "falsifiers": [
                "Order inflow re-accelerates for two consecutive quarters",
                "Credit constraint loosens via policy easing"
            ],
            "direction": "neutral",
            "confidence": 0.55,
            "crowding_assessment": (
                "Positioning checked: order-inflow thesis is not crowded; "
                "flows into capacity names remain moderate."
            ),
            "irreversibility": "none",
            "reference_class": (
                "Capacity-constrained manufacturing systems entering a "
                "regime transition"
            ),
            "prior_probability": 0.45,
            "evidence_adjustments": [
                {
                    "evidence_id": support[0],
                    "direction": "+",
                    "rationale": "Utilization evidence confirms nonlinear order response.",
                },
            ],
            "supporting_evidence_ids": support,
            "contradicting_evidence_ids": contradiction,
        },
        "portfolio": None,
        "key_fragilities": ["Credit contraction can amplify an inventory shock."],
    }


def _initialize(tmp_path: Path) -> dict:
    return initialize_run(
        ResearchRequest(
            subject="Example Industry",
            region="Global",
            time_horizon=TimeHorizon.MID,
            generation_mode=GenerationMode.CORE,
        ),
        root=tmp_path,
    )


def test_skill_init_writes_schemas_without_llm_configuration(tmp_path):
    result = _initialize(tmp_path)

    assert Path(result["profile_schema"]).exists()
    assert Path(result["analysis_schema"]).exists()
    assert result["search_setup"]["llm_key_required"] is False
    assert result["search_setup"]["provider_search_optional"] is True
    assert result["search_setup"]["host_search_supported"] is True
    assert "llm" not in json.loads(
        (Path(result["data_dir"]) / "request.json").read_text()
    )


def test_host_evidence_import_is_deduplicated_and_compiled(tmp_path):
    _initialize(tmp_path)
    evidence_path = tmp_path / "evidence.json"
    record = {
        "category": "industry_overview",
        "provider": "host_agent_search",
        "query": "example capacity",
        "title": "Primary capacity source",
        "url": "https://example.com/capacity?utm_source=x",
        "content": "Dated capacity and utilization evidence.",
        "published_at": "2026-07-20",
        "source_type": "government",
        "quality_score": 0.9,
    }
    evidence_path.write_text(
        json.dumps([record, record]), encoding="utf-8"
    )

    result = import_evidence(
        "Example Industry", evidence_path, root=tmp_path
    )
    context = compile_layer_context(
        "Example Industry", "l0", root=tmp_path
    )

    assert result["received"] == 2
    assert result["added_unique_sources"] == 1
    assert "Primary capacity source" in context


def test_finalize_publishes_only_after_hard_gates_pass(tmp_path):
    initialized = _initialize(tmp_path)
    evidence = []
    for index, source_type in enumerate(
        ("government", "regulator", "industry_research"), start=1
    ):
        evidence.append({
            "category": (
                "contradiction_thesis" if index == 3 else "industry_overview"
            ),
            "provider": "host_agent_search",
            "query": f"query {index}",
            "title": f"Source {index}",
            "url": f"https://source{index}.example/fact",
            "content": "Capacity utilization and order inflow evidence.",
            "published_at": "2026-07-20",
            "source_type": source_type,
            "quality_score": 0.9,
        })
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    imported = import_evidence(
        "Example Industry", evidence_path, root=tmp_path
    )

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        EntityProfile(
            input_kind=InputKind.INDUSTRY,
            canonical_name="Example Industry",
            jurisdiction="Global",
            required_system_dimensions=["capacity", "orders", "credit"],
            evidence_ids=imported["source_ids"][:2],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    assert save_profile(
        "Example Industry", profile_path, root=tmp_path
    )["ok"]

    draft_path = tmp_path / "draft.json"
    draft = AnalysisDraft.model_validate(
        _draft(imported["source_ids"])
    )
    draft_path.write_text(
        draft.model_dump_json(indent=2), encoding="utf-8"
    )
    result = finalize_draft(
        "Example Industry",
        draft_path,
        root=tmp_path,
        run_dir=initialized["run_dir"],
    )

    assert result["ok"], result
    assert Path(result["report"]).exists()
    assert Path(result["validation"]).exists()


def test_finalize_blocks_publication_when_evidence_is_missing(tmp_path):
    initialized = _initialize(tmp_path)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        EntityProfile(
            input_kind=InputKind.INDUSTRY,
            canonical_name="Example Industry",
            jurisdiction="Global",
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    assert save_profile(
        "Example Industry", profile_path, root=tmp_path
    )["ok"]

    draft_path = tmp_path / "draft.json"
    draft = AnalysisDraft.model_validate(
        _draft(["src_missing_1", "src_missing_2", "src_missing_3"])
    )
    draft_path.write_text(
        draft.model_dump_json(indent=2), encoding="utf-8"
    )
    result = finalize_draft(
        "Example Industry",
        draft_path,
        root=tmp_path,
        run_dir=initialized["run_dir"],
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert not (Path(initialized["run_dir"]) / "scan_report.md").exists()
    assert any(
        gate["gate_name"] == "Hard_EvidenceAvailability"
        for gate in result["hard_failures"]
    )


def test_natural_language_skill_flow_preserves_order_and_composes_run(
    tmp_path,
):
    initialized = _initialize(tmp_path)
    evidence = [
        {
            "category": (
                "contradiction_thesis" if index == 3 else "industry_overview"
            ),
            "provider": "host_agent_search",
            "query": f"query {index}",
            "title": f"Source {index}",
            "url": f"https://source{index}.example/fact",
            "content": "Capacity utilization and order inflow evidence.",
            "published_at": "2026-07-20",
            "source_type": source_type,
        }
        for index, source_type in enumerate(
            ("government", "regulator", "industry_research"), start=1
        )
    ]
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    imported = import_evidence(
        "Example Industry", evidence_path, root=tmp_path
    )
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        EntityProfile(
            input_kind=InputKind.INDUSTRY,
            canonical_name="Example Industry",
            jurisdiction="Global",
            evidence_ids=imported["source_ids"][:2],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    profile_result = advance_stage(
        "Example Industry",
        "profile",
        profile_path,
        root=tmp_path,
        run_dir=initialized["run_dir"],
    )
    assert profile_result["ok"]

    draft = _draft(imported["source_ids"])
    stage_keys = {
        "l0": "meta",
        "l1": "variables",
        "l2": "drivers",
        "l3": "flow_feedback",
        "nonlinear": "nonlinear_dynamics",
        "l4": "regime",
        "l5": "distortion",
        "l6": "alpha",
    }
    for stage, key in stage_keys.items():
        path = tmp_path / f"{stage}.json"
        path.write_text(json.dumps(draft[key]), encoding="utf-8")
        result = advance_stage(
            "Example Industry",
            stage,
            path,
            root=tmp_path,
            run_dir=initialized["run_dir"],
        )
        assert result["ok"], result
        assert result["search"]["status"] == "not-configured"

    result = finalize_draft(
        "Example Industry",
        root=tmp_path,
        run_dir=initialized["run_dir"],
    )

    assert result["ok"], result
    assert Path(result["report"]).exists()


def test_l5_stage_preserves_followup_and_contradiction_search_hooks(
    tmp_path, monkeypatch
):
    initialized = _initialize(tmp_path)
    workspace = skill_runtime.workspace_for(
        "Example Industry", tmp_path
    )
    request = skill_runtime._load_request(workspace)
    calls = []

    class FakeCollector:
        total_sources = 3
        failed_requests = 0

        def collect_after_l5(self, subject, value):
            calls.append(("after_l5", subject))
            self.total_sources += 1

        def collect_contradiction(self, subject, value):
            calls.append(("contradiction", subject))
            self.total_sources += 1

        def save_to_directory(self, directory):
            return Path(directory) / "search_data.json"

    monkeypatch.setattr(
        skill_runtime,
        "_provider_collector",
        lambda *args, **kwargs: FakeCollector(),
    )
    value = AnalysisDraft.model_validate(
        _draft(["src_1", "src_2", "src_3"])
    ).distortion

    result = skill_runtime._search_after_stage(
        workspace,
        request,
        tmp_path,
        "l5",
        value,
    )

    assert initialized["mode"] == "core"
    assert calls == [
        ("after_l5", "Example Industry"),
        ("contradiction", "Example Industry"),
    ]
    assert result["new_unique_sources"] == 2


def _import_standard_evidence(tmp_path: Path) -> dict:
    evidence = [
        {
            "category": (
                "contradiction_thesis" if index == 3 else "industry_overview"
            ),
            "provider": "host_agent_search",
            "query": f"query {index}",
            "title": f"Source {index}",
            "url": f"https://source{index}.example/fact",
            "content": "Capacity utilization and order inflow evidence.",
            "published_at": "2026-07-20",
            "source_type": source_type,
            "quality_score": 0.9,
        }
        for index, source_type in enumerate(
            ("government", "regulator", "industry_research"), start=1
        )
    ]
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return import_evidence("Example Industry", evidence_path, root=tmp_path)


def _run_all_stages(tmp_path: Path, run_dir: str, source_ids: list) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        EntityProfile(
            input_kind=InputKind.INDUSTRY,
            canonical_name="Example Industry",
            jurisdiction="Global",
            evidence_ids=source_ids[:2],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    assert advance_stage(
        "Example Industry", "profile", profile_path,
        root=tmp_path, run_dir=run_dir,
    )["ok"]
    draft = _draft(source_ids)
    for stage, key in {
        "l0": "meta", "l1": "variables", "l2": "drivers",
        "l3": "flow_feedback", "nonlinear": "nonlinear_dynamics",
        "l4": "regime", "l5": "distortion", "l6": "alpha",
    }.items():
        path = tmp_path / f"{stage}.json"
        path.write_text(json.dumps(draft[key]), encoding="utf-8")
        result = advance_stage(
            "Example Industry", stage, path,
            root=tmp_path, run_dir=run_dir,
        )
        assert result["ok"], result


def test_falsifier_review_enforced_and_tracked_on_rerun(tmp_path):
    # First run: publish a complete report.
    first = _initialize(tmp_path)
    imported = _import_standard_evidence(tmp_path)
    _run_all_stages(tmp_path, first["run_dir"], imported["source_ids"])
    assert first["resolution_required"] is False
    published = finalize_draft(
        "Example Industry", root=tmp_path, run_dir=first["run_dir"]
    )
    assert published["ok"], published

    # Second run: prior commitments must exist and block L0.
    second = _initialize(tmp_path)
    assert second["resolution_required"] is True
    assert Path(second["prior_commitments"]).exists()
    commitments = json.loads(
        Path(second["prior_commitments"]).read_text(encoding="utf-8")
    )
    assert commitments["l6"]["direction"] == "neutral"
    assert commitments["l4"]["regime_distribution"]

    l0_path = tmp_path / "l0_retry.json"
    l0_path.write_text(
        json.dumps(_draft(imported["source_ids"])["meta"]), encoding="utf-8"
    )
    blocked = advance_stage(
        "Example Industry", "l0", l0_path,
        root=tmp_path, run_dir=second["run_dir"],
    )
    assert blocked["ok"] is False
    assert "resolve" in blocked["error"]

    # Grade the commitments, then L0 proceeds.
    verdicts_path = tmp_path / "verdicts.json"
    verdicts_path.write_text(json.dumps({
        "verdicts": [
            {
                "commitment": "neutral direction until order inflow confirms",
                "status": "hit",
                "note": "no regime confirmation arrived; neutral held",
            },
            {
                "commitment": "transition->expansion at 0.45",
                "status": "partial",
            },
        ]
    }), encoding="utf-8")
    resolved = skill_runtime.record_resolution(
        "Example Industry", verdicts_path,
        root=tmp_path, run_dir=second["run_dir"],
    )
    assert resolved["ok"], resolved
    assert resolved["calibration"]["evaluated_commitments"] == 2

    unblocked = advance_stage(
        "Example Industry", "l0", l0_path,
        root=tmp_path, run_dir=second["run_dir"],
    )
    assert unblocked["ok"], unblocked

    # Second published report carries the track record.
    _run_all_stages(
        tmp_path, second["run_dir"], imported["source_ids"]
    )
    second_published = finalize_draft(
        "Example Industry", root=tmp_path, run_dir=second["run_dir"]
    )
    assert second_published["ok"], second_published
    report_text = Path(second_published["report"]).read_text(
        encoding="utf-8"
    )
    assert "Track Record (Falsifier Review)" in report_text


def test_invalid_resolution_status_rejected(tmp_path):
    first = _initialize(tmp_path)
    imported = _import_standard_evidence(tmp_path)
    _run_all_stages(tmp_path, first["run_dir"], imported["source_ids"])
    assert finalize_draft(
        "Example Industry", root=tmp_path, run_dir=first["run_dir"]
    )["ok"]
    second = _initialize(tmp_path)
    verdicts_path = tmp_path / "bad_verdicts.json"
    verdicts_path.write_text(json.dumps({
        "verdicts": [{"commitment": "x", "status": "maybe"}]
    }), encoding="utf-8")
    result = skill_runtime.record_resolution(
        "Example Industry", verdicts_path,
        root=tmp_path, run_dir=second["run_dir"],
    )
    assert result["ok"] is False
    assert "maybe" in result["error"]


def test_calibration_summary_buckets():
    entries = [
        {
            "prior_confidence": 0.8,
            "verdicts": [
                {"status": "hit"},
                {"status": "miss"},
                {"status": "not_yet_evaluable"},
            ],
        },
        {
            "prior_confidence": 0.4,
            "verdicts": [{"status": "partial"}],
        },
    ]
    summary = skill_runtime._calibration_summary(entries)
    assert summary["evaluated_commitments"] == 3
    assert summary["by_prior_confidence"][">0.7"]["hit_rate"] == 0.5
    assert summary["by_prior_confidence"]["<0.5"]["hit_rate"] == 0.5
