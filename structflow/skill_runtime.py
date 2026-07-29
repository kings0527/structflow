"""Deterministic runtime used by the StructFlow skill.

The host agent owns research, reasoning, and generation. This module only
manages workspaces, evidence, schemas, validation, and publication.
"""

from __future__ import annotations

import json
import os
from dataclasses import fields, replace
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from structflow.config import MarketDataConfig
from structflow.coverage_contract import CoverageValidator
from structflow.data_collector import DataCollector
from structflow.evidence import (
    EvidenceRecord,
    EvidenceStore,
    infer_source_type,
    recency_score,
    source_weight,
)
from structflow.financial_consistency import FinancialConsistencyValidator
from structflow.gates import run_all_gates
from structflow.input_resolver import EntityProfile, InputKind, profile_context
from structflow.investment_validation import InvestmentValidator
from structflow.market_data import collect_market_data
from structflow.market_snapshot import resolve_consensus_market_snapshot
from structflow.models import (
    AlphaEngine,
    CompanyScore,
    DistortionEngine,
    DriverSpace,
    FlowFeedbackSystem,
    GateResult,
    GateValidationReport,
    InvestmentMapping,
    MetaSystemDefinition,
    NonlinearDynamics,
    RegimeEngine,
    ScanOutput,
    ScoreVector,
    TimeHorizon,
    VariableMapping,
)
from structflow.output_validator import OutputValidator
from structflow.reporter import render_report
from structflow.research_clock import (
    coerce_date,
    current_analysis_date,
    temporal_contract,
)
from structflow.research_gates import ResearchValidator
from structflow.score_calibrator import ScoreCalibrator
from structflow.system_templates import (
    get_template_methodology,
    match_template,
)
from structflow.temporal_grounding import TemporalGroundingValidator
from structflow.workspace import MaterialLibrary, ResearchWorkspace


class GenerationMode(str, Enum):
    FULL = "full"
    CORE = "core"
    VALIDATE_ONLY = "validate-only"


class ResearchRequest(BaseModel):
    subject: str
    region: Optional[str] = None
    time_horizon: TimeHorizon = TimeHorizon.MID
    peer_set: list[str] = Field(default_factory=list)
    generation_mode: GenerationMode = GenerationMode.FULL
    analysis_date: date = Field(default_factory=current_analysis_date)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AnalysisDraft(BaseModel):
    """Agent-generated analysis before deterministic gates are attached."""

    industry: str
    region: Optional[str] = None
    time_horizon: TimeHorizon = TimeHorizon.MID
    meta: MetaSystemDefinition
    variables: VariableMapping
    drivers: DriverSpace
    flow_feedback: FlowFeedbackSystem
    nonlinear_dynamics: NonlinearDynamics
    regime: RegimeEngine
    distortion: DistortionEngine
    alpha: AlphaEngine
    portfolio: Optional[InvestmentMapping] = None
    industry_score: Optional[ScoreVector] = None
    companies_ranked: list[CompanyScore] = Field(default_factory=list)
    key_fragilities: list[str] = Field(default_factory=list)


class EvidenceImportItem(BaseModel):
    category: str
    provider: str = "host_agent_search"
    query: str
    title: str
    url: str = ""
    content: str
    published_at: Optional[str] = None
    source_type: Optional[str] = None
    upstream_origin: Optional[str] = None
    relevance_score: float = Field(default=0.5, ge=0, le=1)
    quality_score: Optional[float] = Field(default=None, ge=0, le=1)
    freshness_score: Optional[float] = Field(default=None, ge=0, le=1)


VALID_RESOLUTION_STATUSES = {
    "hit",
    "miss",
    "partial",
    "indeterminate",
    "not_yet_evaluable",
}


class ResolutionVerdict(BaseModel):
    """One graded prior commitment (falsifier, direction, or regime call)."""

    commitment: str
    status: str
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ResolutionInput(BaseModel):
    verdicts: list[ResolutionVerdict]


STAGE_FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "l0": ("l0.json", MetaSystemDefinition),
    "l1": ("l1.json", VariableMapping),
    "l2": ("l2.json", DriverSpace),
    "l3": ("l3.json", FlowFeedbackSystem),
    "nonlinear": ("nonlinear.json", NonlinearDynamics),
    "l4": ("l4.json", RegimeEngine),
    "l5": ("l5.json", DistortionEngine),
    "l6": ("l6.json", AlphaEngine),
    "l7-draft": ("l7_draft.json", InvestmentMapping),
    "l7-final": ("l7.json", InvestmentMapping),
}


STAGE_PAYLOAD_KEYS = {
    "l0": "meta",
    "l1": "variables",
    "l2": "drivers",
    "l3": "flow_feedback",
    "nonlinear": "nonlinear_dynamics",
    "l4": "regime",
    "l5": "distortion",
    "l6": "alpha",
    "l7-draft": "portfolio",
    "l7-final": "portfolio",
}


LAYER_CONTEXT_PREFIXES: dict[str, list[str]] = {
    "profile": [
        "industry_overview",
        "company_",
        "company_filing",
        "company_financial",
        "market_data_",
        "policy_context",
        "user_material",
    ],
    "l0": [
        "industry_overview",
        "market_structure",
        "policy_context",
        "risk_landscape",
        "revenue_model",
        "precision_",
    ],
    "l1": [
        "industry_overview",
        "market_structure",
        "policy_context",
        "l0_",
        "precision_",
    ],
    "l2": ["l1_", "policy_context", "industry_overview", "precision_"],
    "l3": ["l2_", "l1_", "market_structure", "precision_supply_chain"],
    "nonlinear": [
        "l3_",
        "l2_",
        "l1_",
        "risk_landscape",
        "precision_capacity",
    ],
    "l4": [
        "l3_",
        "l4_",
        "nonlinear_",
        "risk_landscape",
        "industry_overview",
        "contradiction_",
        "market_data_",
    ],
    "l5": [
        "l5_",
        "l4_",
        "revenue_model",
        "industry_overview",
        "contradiction_",
        "precision_",
        "market_data_",
    ],
    "l6": [
        "l6_",
        "l5_",
        "l4_",
        "risk_landscape",
        "contradiction_",
        "precision_",
        "market_data_",
        "positioning_",
    ],
    "l7": [
        "company_",
        "l7_",
        "l6_",
        "l4_",
        "l5_",
        "contradiction_",
        "market_data_",
    ],
}


def workspace_for(subject: str, root: str | Path = ".") -> ResearchWorkspace:
    return ResearchWorkspace(Path(root).resolve() / "scans", subject)


def _latest_completed_run(workspace: ResearchWorkspace) -> Path | None:
    """Newest published run of this subject, used for falsifier review."""
    candidates: list[tuple[str, Path]] = []
    if not workspace.report_dir.exists():
        return None
    for run_dir in workspace.report_dir.iterdir():
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("status") != "completed":
            continue
        if not (run_dir / "l6.json").exists() or not (run_dir / "l4.json").exists():
            continue
        candidates.append((manifest.get("validated_at", ""), run_dir))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _write_prior_commitments(
    workspace: ResearchWorkspace, run_dir: Path
) -> dict[str, Any] | None:
    """Persist the previous run's scoreable commitments into the new run.

    A falsifiable model that never revisits its own falsifiers is not
    falsifiable in practice. The L0 stage refuses to run until these
    commitments are graded via `resolve`.
    """
    prior_run = _latest_completed_run(workspace)
    if prior_run is None or prior_run.resolve() == run_dir.resolve():
        return None
    try:
        alpha = AlphaEngine.model_validate_json(
            (prior_run / "l6.json").read_text(encoding="utf-8")
        )
        regime = RegimeEngine.model_validate_json(
            (prior_run / "l4.json").read_text(encoding="utf-8")
        )
    except Exception:
        return None
    payload = {
        "prior_run": str(prior_run),
        "resolution_required": True,
        "l6": {
            "direction": alpha.direction,
            "confidence": alpha.confidence,
            "alpha_signal": alpha.alpha_signal,
            "falsifiers": alpha.falsifiers,
            "irreversibility": alpha.irreversibility,
            "ruin_path": alpha.ruin_path,
        },
        "l4": {
            "current_regime": regime.current_regime,
            "regime_distribution": regime.regime_distribution,
            "next_regime": regime.transition_probability.next_regime,
            "transition_probability": regime.transition_probability.probability,
        },
        "instruction": (
            "Grade each prior commitment against fresh evidence and run "
            "`resolve` with the verdicts before the L0 stage: did declared "
            "falsifiers trigger, did the regime call hold, did the signal "
            "direction survive?"
        ),
    }
    _write_json(run_dir / "prior_commitments.json", payload)
    return payload


def _load_resolution_log(workspace: ResearchWorkspace) -> dict[str, Any]:
    path = workspace.data_dir / "resolutions.json"
    if not path.exists():
        return {"entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": []}
    if not isinstance(payload.get("entries"), list):
        payload["entries"] = []
    return payload


def _calibration_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Minimal Brier-style track record: hit rate by prior confidence bucket.

    partial counts as half a hit; indeterminate and not_yet_evaluable are
    excluded from the denominator.
    """
    buckets = {"<0.5": [0.0, 0], "0.5-0.7": [0.0, 0], ">0.7": [0.0, 0]}
    total_evaluable = 0
    for entry in entries:
        confidence = float(entry.get("prior_confidence") or 0.0)
        if confidence < 0.5:
            bucket = "<0.5"
        elif confidence <= 0.7:
            bucket = "0.5-0.7"
        else:
            bucket = ">0.7"
        for verdict in entry.get("verdicts", []):
            status = verdict.get("status")
            if status == "hit":
                score = 1.0
            elif status == "partial":
                score = 0.5
            elif status == "miss":
                score = 0.0
            else:
                continue
            buckets[bucket][0] += score
            buckets[bucket][1] += 1
            total_evaluable += 1
    by_confidence = {
        name: {
            "evaluated": count,
            "hit_rate": round(score / count, 2) if count else None,
        }
        for name, (score, count) in buckets.items()
    }
    return {
        "resolution_entries": len(entries),
        "evaluated_commitments": total_evaluable,
        "by_prior_confidence": by_confidence,
    }


def record_resolution(
    subject: str,
    input_path: str | Path,
    *,
    root: str | Path = ".",
    run_dir: str | Path,
) -> dict[str, Any]:
    """Grade the previous run's commitments and append them to the log."""
    workspace = workspace_for(subject, root)
    _load_request(workspace)
    target = _validated_run_dir(workspace, run_dir)
    commitments_path = target / "prior_commitments.json"
    if not commitments_path.exists():
        return {
            "ok": False,
            "error": (
                "No prior commitments found in this run; resolution is "
                "only required when a previous published run exists."
            ),
        }
    commitments = json.loads(commitments_path.read_text(encoding="utf-8"))
    resolution = ResolutionInput.model_validate_json(
        Path(input_path).read_text(encoding="utf-8")
    )
    if not resolution.verdicts:
        return {"ok": False, "error": "At least one verdict is required."}
    invalid = [
        verdict.status
        for verdict in resolution.verdicts
        if verdict.status not in VALID_RESOLUTION_STATUSES
    ]
    if invalid:
        return {
            "ok": False,
            "error": (
                f"Invalid verdict statuses {invalid}; use "
                f"{sorted(VALID_RESOLUTION_STATUSES)}"
            ),
        }
    log = _load_resolution_log(workspace)
    log["entries"] = [
        entry
        for entry in log["entries"]
        if entry.get("current_run") != str(target)
    ]
    log["entries"].append({
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "prior_run": commitments.get("prior_run"),
        "current_run": str(target),
        "prior_direction": commitments.get("l6", {}).get("direction"),
        "prior_confidence": commitments.get("l6", {}).get("confidence"),
        "verdicts": [
            verdict.model_dump() for verdict in resolution.verdicts
        ],
    })
    summary = _calibration_summary(log["entries"])
    log["calibration"] = summary
    _write_json(workspace.data_dir / "resolutions.json", log)
    return {
        "ok": True,
        "resolutions": str(workspace.data_dir / "resolutions.json"),
        "calibration": summary,
    }


def _pending_resolution(
    workspace: ResearchWorkspace, run_dir: Path
) -> bool:
    if not (run_dir / "prior_commitments.json").exists():
        return False
    log = _load_resolution_log(workspace)
    return not any(
        entry.get("current_run") == str(run_dir)
        for entry in log["entries"]
    )


def initialize_run(
    request: ResearchRequest,
    *,
    root: str | Path = ".",
    material_paths: Iterable[str | Path] = (),
) -> dict[str, Any]:
    workspace = workspace_for(request.subject, root)
    workspace.prepare()
    workspace.migrate_legacy_cache()
    material_status = MaterialLibrary(workspace.materials_dir).sync(
        material_paths
    )
    run_dir = workspace.create_report_run()
    prior_commitments = _write_prior_commitments(workspace, run_dir)

    request_payload = request.model_dump(mode="json")
    _write_json(workspace.data_dir / "request.json", request_payload)
    _write_json(run_dir / "request.json", request_payload)
    _write_json(
        run_dir / "entity_profile.schema.json",
        EntityProfile.model_json_schema(),
    )
    _write_json(
        run_dir / "analysis.schema.json",
        AnalysisDraft.model_json_schema(),
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "status": "initialized",
            "subject": request.subject,
            "generation_mode": request.generation_mode.value,
            "analysis_date": request.analysis_date.isoformat(),
            "created_at": request.created_at.isoformat(),
            "data_dir": str(workspace.data_dir),
            "run_dir": str(run_dir),
            "material_status": material_status,
        },
    )
    return {
        "ok": True,
        "subject": request.subject,
        "mode": request.generation_mode.value,
        "analysis_date": request.analysis_date.isoformat(),
        "data_dir": str(workspace.data_dir),
        "run_dir": str(run_dir),
        "search_cache": str(workspace.search_cache_file),
        "profile_schema": str(run_dir / "entity_profile.schema.json"),
        "analysis_schema": str(run_dir / "analysis.schema.json"),
        "material_status": material_status,
        "search_setup": _search_setup_status(Path(root).resolve()),
        "prior_commitments": (
            str(run_dir / "prior_commitments.json")
            if prior_commitments
            else None
        ),
        "resolution_required": bool(prior_commitments),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _env_value(root: Path, name: str) -> str:
    environment = os.getenv(name, "").strip()
    if environment:
        return environment
    path = root / ".env"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip()
    return ""


def _search_setup_status(root: Path) -> dict[str, Any]:
    configured = {
        "tavily": bool(_env_value(root, "TAVILY_API_KEY")),
        "anysearch": bool(_env_value(root, "ANYSEARCH_API_KEY")),
    }
    return {
        "llm_key_required": False,
        "provider_search_optional": True,
        "host_search_supported": True,
        "optional_provider_keys": configured,
        "guidance": (
            "Tavily and AnySearch are optional. Use host-agent search and "
            "`import-evidence` when provider search is unavailable or leaves "
            "claims uncovered."
        ),
    }


def _load_request(workspace: ResearchWorkspace) -> ResearchRequest:
    path = workspace.data_dir / "request.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Workspace is not initialized: {path}. Run `structflow init`."
        )
    return ResearchRequest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _record_from_manifest(item: dict[str, Any]) -> list[EvidenceRecord]:
    record_fields = {field.name for field in fields(EvidenceRecord)}
    values = {
        key: value for key, value in item.items() if key in record_fields
    }
    try:
        record = EvidenceRecord(**values)
    except TypeError:
        return []
    categories = item.get("categories") or [record.category]
    queries = item.get("queries") or [record.query]
    return [
        replace(record, category=str(category), query=str(query))
        for category in categories
        for query in queries
    ]


def load_evidence_store(
    workspace: ResearchWorkspace,
    *,
    analysis_date: date | None = None,
    include_materials: bool = True,
) -> EvidenceStore:
    store = EvidenceStore(analysis_date=analysis_date)
    if workspace.search_cache_file.exists():
        payload = json.loads(
            workspace.search_cache_file.read_text(encoding="utf-8")
        )
        for item in payload.get("evidence", []):
            if not isinstance(item, dict):
                continue
            for record in _record_from_manifest(item):
                store.add(record)
    if include_materials:
        for record in MaterialLibrary(
            workspace.materials_dir
        ).evidence_records():
            store.add(record)
    return store


def _save_evidence_store(
    workspace: ResearchWorkspace,
    store: EvidenceStore,
    *,
    imported: int = 0,
) -> None:
    previous_metadata: dict[str, Any] = {}
    if workspace.search_cache_file.exists():
        try:
            previous_payload = json.loads(
                workspace.search_cache_file.read_text(encoding="utf-8")
            )
            previous_metadata = previous_payload.get("metadata", {})
        except (OSError, json.JSONDecodeError):
            previous_metadata = {}
    manifest = store.manifest()
    categories = {
        category: [
            record["source_id"]
            for record in manifest
            if category in record.get("categories", [])
        ]
        for category in store.categories()
    }
    _write_json(
        workspace.search_cache_file,
        {
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_sources": store.unique_source_count,
                "imported_in_last_operation": imported,
                "engines": {"host_agent": True},
                "queries_executed": previous_metadata.get(
                    "queries_executed", []
                ),
                "logical_query_keys": previous_metadata.get(
                    "logical_query_keys", []
                ),
                "failed_requests": previous_metadata.get(
                    "failed_requests", []
                ),
            },
            "categories": categories,
            "evidence": manifest,
        },
    )


def _merge_import_items(
    workspace: ResearchWorkspace,
    request: ResearchRequest,
    items: list[EvidenceImportItem],
) -> dict[str, Any]:
    """Merge validated import items into the persisted evidence store.

    Shared by ``import_evidence`` and ``fetch_market_data``: future
    dates are rejected, records deduplicate on canonical URL, and the
    store is saved back to the workspace search cache.
    """
    store = load_evidence_store(
        workspace,
        analysis_date=request.analysis_date,
        include_materials=False,
    )
    before = store.unique_source_count
    rejected_future = 0
    for item in items:
        published_on = coerce_date(item.published_at)
        if published_on and published_on > request.analysis_date:
            rejected_future += 1
            continue
        source_type = item.source_type or infer_source_type(
            item.url, item.title, item.content
        )
        store.add(EvidenceRecord(
            category=item.category,
            provider=item.provider,
            query=item.query,
            title=item.title,
            url=item.url,
            content=item.content,
            published_at=item.published_at,
            source_type=source_type,
            upstream_origin=item.upstream_origin,
            relevance_score=item.relevance_score,
            quality_score=(
                item.quality_score
                if item.quality_score is not None
                else source_weight(source_type)
            ),
            freshness_score=(
                item.freshness_score
                if item.freshness_score is not None
                else recency_score(item.published_at)
            ),
        ))
    added = store.unique_source_count - before
    _save_evidence_store(workspace, store, imported=added)
    return {
        "received": len(items),
        "rejected_future_records": rejected_future,
        "added_unique_sources": added,
        "total_unique_sources": store.unique_source_count,
        "search_cache": str(workspace.search_cache_file),
        "source_ids": sorted(store.source_ids),
    }


def import_evidence(
    subject: str,
    input_path: str | Path,
    *,
    root: str | Path = ".",
) -> dict[str, Any]:
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    raw = json.loads(Path(input_path).read_text(encoding="utf-8"))
    raw_items = raw.get("evidence", []) if isinstance(raw, dict) else raw
    if not isinstance(raw_items, list):
        raise ValueError("Evidence input must be an array or an object with `evidence`.")

    items = [EvidenceImportItem.model_validate(item) for item in raw_items]
    return {"ok": True, **_merge_import_items(workspace, request, items)}


def fetch_market_data(
    subject: str,
    *,
    asset_class: str,
    code: str | None = None,
    data_types: list[str] | None = None,
    as_of: str | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    """Fetch structured market data and merge it as evidence.

    Accuracy-first and fail-closed: cross-validation failures and
    single-aggregator situations yield zero price records; every
    failure reason is surfaced so the host agent can fall back to the
    search + import-evidence path.
    """
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    settings = MarketDataConfig()
    if not settings.enabled:
        return {
            "ok": False,
            "asset_class": asset_class,
            "received": 0,
            "rejected_future_records": 0,
            "added_unique_sources": 0,
            "total_unique_sources": 0,
            "categories": [],
            "cross_validation": {"passed": [], "failed": []},
            "degraded": [
                "market data channel disabled (MARKET_DATA_ENABLED=false)"
            ],
            "failures": [],
            "search_cache": str(workspace.search_cache_file),
            "source_ids": [],
        }
    analysis_date = (
        coerce_date(as_of) if as_of else request.analysis_date
    )
    if analysis_date is None:
        raise ValueError("--date must use YYYY-MM-DD")
    result = collect_market_data(
        subject=subject,
        asset_class=asset_class,
        code=code,
        types=set(data_types) if data_types else None,
        analysis_date=analysis_date,
        tolerance=settings.price_tolerance,
        timeout=settings.timeout,
        lookback_days=settings.lookback_days,
        fred_api_key=_env_value(Path(root).resolve(), "FRED_API_KEY"),
    )
    items = [
        EvidenceImportItem.model_validate(record)
        for record in result.records
    ]
    # Anchor future-date rejection to the effective analysis date: a
    # backdated --date must reject observations published after it,
    # even when the workspace request was initialized on a later day
    # (look-ahead leakage). The stored request stays untouched.
    request_for_market = request.model_copy(
        update={"analysis_date": analysis_date}
    )
    merged = _merge_import_items(workspace, request_for_market, items)
    # ok means at least one record survived future-date rejection: the
    # channel produced data usable on the effective analysis date. An
    # idempotent rerun (valid records, all deduplicated, added=0) must
    # stay ok=true — the data being in the store is success — so this
    # is never gated on added_unique_sources.
    accepted = len(items) - merged["rejected_future_records"]
    return {
        "ok": accepted > 0,
        "asset_class": asset_class,
        **merged,
        "categories": sorted({item.category for item in items}),
        "cross_validation": {
            "passed": result.cross_validation_passed,
            "failed": result.cross_validation_failed,
        },
        "degraded": result.degraded,
        "failures": result.failures,
    }


def collect_provider_evidence(
    subject: str,
    *,
    root: str | Path = ".",
    refresh: bool = False,
) -> dict[str, Any]:
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    root_path = Path(root).resolve()
    collector = DataCollector(
        api_key=_env_value(root_path, "TAVILY_API_KEY") or None,
        anysearch_key=_env_value(root_path, "ANYSEARCH_API_KEY") or None,
        output_dir=str(workspace.search_dir),
        industry=subject,
        cache_only=False,
    )
    collector.set_analysis_date(request.analysis_date)
    loaded = 0
    if workspace.search_cache_file.exists() and not refresh:
        loaded = collector.load_cache(
            workspace.search_cache_file,
            cache_only=False,
        )
    collector.collect_initial(
        industry=subject,
        region=request.region,
        peer_set=request.peer_set or None,
        discover_competitors=False,
    )
    path = collector.save_to_directory(workspace.search_dir)
    return {
        "ok": True,
        "loaded": loaded,
        "total_unique_sources": collector.total_sources,
        "failed_requests": collector.failed_requests,
        "search_cache": str(path),
    }


def _load_stage_component(
    input_path: str | Path,
    stage: str,
) -> BaseModel:
    if stage not in STAGE_FILES:
        raise ValueError(f"Unsupported analysis stage: {stage}")
    raw = json.loads(Path(input_path).read_text(encoding="utf-8"))
    payload_key = STAGE_PAYLOAD_KEYS[stage]
    if (
        isinstance(raw, dict)
        and payload_key in raw
        and isinstance(raw[payload_key], dict)
    ):
        raw = raw[payload_key]
    _, model = STAGE_FILES[stage]
    return model.model_validate(raw)


def _stage_artifact(
    run_dir: Path,
    stage: str,
) -> Path:
    filename, _ = STAGE_FILES[stage]
    return run_dir / filename


def _read_stage(
    run_dir: Path,
    stage: str,
) -> BaseModel:
    path = _stage_artifact(run_dir, stage)
    if not path.exists():
        raise FileNotFoundError(
            f"Required prior stage is missing: {path}"
        )
    _, model = STAGE_FILES[stage]
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def _provider_collector(
    workspace: ResearchWorkspace,
    request: ResearchRequest,
    root: Path,
) -> DataCollector | None:
    tavily_key = _env_value(root, "TAVILY_API_KEY")
    anysearch_key = _env_value(root, "ANYSEARCH_API_KEY")
    if not tavily_key and not anysearch_key:
        return None
    collector = DataCollector(
        api_key=tavily_key or None,
        anysearch_key=anysearch_key or None,
        output_dir=str(workspace.search_dir),
        industry=request.subject,
        cache_only=False,
    )
    collector.set_analysis_date(request.analysis_date)
    if workspace.search_cache_file.exists():
        collector.load_cache(
            workspace.search_cache_file,
            cache_only=False,
        )
    profile_path = workspace.data_dir / "entity_profile.json"
    if profile_path.exists():
        profile = EntityProfile.model_validate_json(
            profile_path.read_text(encoding="utf-8")
        )
        collector.set_profile_context(profile_context(profile))
    system_type_path = workspace.data_dir / "system_type.json"
    if system_type_path.exists():
        try:
            system_type = json.loads(
                system_type_path.read_text(encoding="utf-8")
            ).get("system_type", "")
        except json.JSONDecodeError:
            system_type = ""
        if system_type:
            collector.set_template(system_type)
    return collector


def _search_after_stage(
    workspace: ResearchWorkspace,
    request: ResearchRequest,
    root: Path,
    stage: str,
    value: BaseModel,
) -> dict[str, Any]:
    if stage == "l7-final":
        return {
            "status": "not-required",
            "reason": "L7 final consumes evidence acquired from L7 draft.",
        }
    collector = _provider_collector(workspace, request, root)
    if collector is None:
        return {
            "status": "not-configured",
            "reason": (
                "No Tavily/AnySearch key is configured. Run `structflow setup` "
                "or import evidence acquired by the host agent."
            ),
        }
    before = collector.total_sources
    discovered_peers: list[str] = []
    if stage == "profile":
        collector.collect_profile_gaps(value)
        if (
            isinstance(value, EntityProfile)
            and value.input_kind == InputKind.INDUSTRY
            and not request.peer_set
        ):
            discovered_peers = collector.collect_competitors(
                request.subject, request.region
            )
            if discovered_peers:
                request.peer_set = discovered_peers
                _write_json(
                    workspace.data_dir / "request.json",
                    request.model_dump(mode="json"),
                )
    elif stage == "l0":
        assert isinstance(value, MetaSystemDefinition)
        template = collector.set_template(value.system_type)
        _write_json(
            workspace.data_dir / "system_type.json",
            {
                "system_type": value.system_type,
                "template": template.name if template else None,
            },
        )
        collector.collect_after_l0(
            request.subject, value, request.region
        )
    elif stage == "l1":
        collector.collect_after_l1(request.subject, value)
    elif stage == "l2":
        collector.collect_after_l2(request.subject, value)
    elif stage == "l3":
        collector.collect_after_l3(request.subject, value)
    elif stage == "nonlinear":
        collector.collect_after_nonlinear(request.subject, value)
    elif stage == "l4":
        collector.collect_after_l4(request.subject, value)
    elif stage == "l5":
        collector.collect_after_l5(request.subject, value)
        collector.collect_contradiction(request.subject, value)
    elif stage == "l6":
        collector.collect_after_l6(request.subject, value)
    elif stage == "l7-draft":
        collector.collect_after_l7(request.subject, value)
    else:
        raise ValueError(f"Unsupported search stage: {stage}")
    path = collector.save_to_directory(workspace.search_dir)
    return {
        "status": (
            "degraded" if collector.failed_requests else "completed"
        ),
        "sources_before": before,
        "sources_after": collector.total_sources,
        "new_unique_sources": collector.total_sources - before,
        "failed_requests": collector.failed_requests,
        "search_cache": str(path),
        "discovered_peers": discovered_peers,
    }


def compile_layer_context(
    subject: str,
    layer: str,
    *,
    root: str | Path = ".",
    max_tokens: int = 12_000,
) -> str:
    normalized_layer = layer.lower()
    if normalized_layer not in LAYER_CONTEXT_PREFIXES:
        raise ValueError(
            f"Unknown layer `{layer}`. Choose from: "
            + ", ".join(LAYER_CONTEXT_PREFIXES)
        )
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    store = load_evidence_store(
        workspace, analysis_date=request.analysis_date
    )
    prefixes = LAYER_CONTEXT_PREFIXES[normalized_layer]
    relevant = [
        category
        for category in store.categories()
        if category == "user_material"
        or any(
            category == prefix or category.startswith(prefix)
            for prefix in prefixes
        )
    ]
    parts = [
        f"# StructFlow Context: {subject} / {normalized_layer}",
        temporal_contract(request.analysis_date),
    ]
    schema_block = _layer_schema_block(normalized_layer)
    if schema_block:
        parts.append(schema_block)
    profile_path = workspace.data_dir / "entity_profile.json"
    if profile_path.exists():
        profile = EntityProfile.model_validate_json(
            profile_path.read_text(encoding="utf-8")
        )
        parts.append(profile_context(profile))
    evidence = store.compile_context(
        relevant,
        max_tokens=max_tokens,
        max_per_category=10,
        max_per_domain=4,
        focus_text=f"{subject} {normalized_layer}",
    )
    if evidence:
        parts.append(evidence)
    else:
        parts.append(
            "## Evidence Gap\nNo eligible evidence is available for this layer."
        )
    return "\n\n".join(parts)


_LAYER_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "profile": EntityProfile,
    "l0": MetaSystemDefinition,
    "l1": VariableMapping,
    "l2": DriverSpace,
    "l3": FlowFeedbackSystem,
    "nonlinear": NonlinearDynamics,
    "l4": RegimeEngine,
    "l5": DistortionEngine,
    "l6": AlphaEngine,
    "l7": InvestmentMapping,
}


def _layer_schema_block(layer: str) -> str:
    """Embed the exact output schema so the generator never has to guess
    numeric ranges or enums from prose (discovered via host-agent testing:
    prose-only contracts caused avoidable validation failures)."""
    model = _LAYER_SCHEMA_MODELS.get(layer)
    if model is None:
        return ""
    schema = json.dumps(
        model.model_json_schema(), ensure_ascii=False, separators=(",", ":")
    )
    return (
        "## Output JSON Schema (binding)\n"
        "Generate output that validates against this exact schema; field "
        "descriptions carry the semantic contract (ranges, enums, units):\n"
        f"```json\n{schema}\n```"
    )


def save_profile(
    subject: str,
    input_path: str | Path,
    *,
    root: str | Path = ".",
) -> dict[str, Any]:
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    profile = EntityProfile.model_validate_json(
        Path(input_path).read_text(encoding="utf-8")
    )
    store = load_evidence_store(
        workspace, analysis_date=request.analysis_date
    )
    snapshot = resolve_consensus_market_snapshot(
        store.records(), profile, request.analysis_date
    )
    if snapshot:
        profile = profile.model_copy(update={"market_snapshot": snapshot})

    gates = [
        GateResult(
            gate_name="Hard_InputResolution",
            passed=profile.input_kind != InputKind.UNKNOWN,
            reason=f"input_kind={profile.input_kind.value}",
        ),
        ResearchValidator().validate_entity_profile(
            profile, store.source_ids
        ),
        FinancialConsistencyValidator().validate(
            profile, request.analysis_date
        ),
    ]
    hard_failures = _hard_failures(gates)
    result = {
        "ok": not hard_failures,
        "gates": [gate.model_dump() for gate in gates],
        "market_snapshot_resolved": snapshot is not None,
    }
    if hard_failures:
        result["error"] = "Canonical profile rejected by hard gates."
        return result

    path = workspace.data_dir / "entity_profile.json"
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    result["profile"] = str(path)
    return result


def _load_profile(workspace: ResearchWorkspace) -> EntityProfile:
    path = workspace.data_dir / "entity_profile.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Canonical profile is missing: {path}. Run `save-profile` first."
        )
    return EntityProfile.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _basic_l0_gate(meta: MetaSystemDefinition) -> GateResult:
    issues = []
    for name, minimum in (
        ("system_type", 3),
        ("core_function", 10),
        ("system_boundary", 10),
        ("failure_mode", 10),
    ):
        value = str(getattr(meta, name, "") or "").strip()
        if len(value) < minimum:
            issues.append(f"{name} too short")
    return GateResult(
        gate_name="L0_BasicValidation",
        passed=not issues,
        reason="L0 valid" if not issues else "; ".join(issues),
    )


def _mode_gate(
    mode: GenerationMode, portfolio: InvestmentMapping | None
) -> GateResult:
    if mode == GenerationMode.FULL:
        passed = portfolio is not None
        reason = "full mode includes L7" if passed else "full mode requires L7"
    elif mode == GenerationMode.CORE:
        passed = portfolio is None
        reason = (
            "core mode omits L7"
            if passed
            else "core mode must omit portfolio; use full mode for L7"
        )
    else:
        passed = True
        reason = "validate-only accepts the draft's declared scope"
    return GateResult(
        gate_name="Hard_GenerationMode",
        passed=passed,
        reason=reason,
    )


def validate_draft(
    draft: AnalysisDraft,
    profile: EntityProfile,
    evidence_store: EvidenceStore,
    analysis_date: date,
    mode: GenerationMode,
) -> GateValidationReport:
    source_ids = evidence_store.source_ids
    records_by_id = {
        record.source_id: record for record in evidence_store.records()
    }
    domains = {
        record.domain for record in records_by_id.values() if record.domain
    }
    high_quality = [
        record
        for record in records_by_id.values()
        if record.quality_score >= 0.78
    ]
    base = run_all_gates(
        draft.variables,
        draft.drivers,
        draft.flow_feedback,
        draft.regime,
        draft.alpha,
    ).gates
    output_validator = OutputValidator(collected_data={})
    research = ResearchValidator()
    coverage = CoverageValidator()
    gates = [
        _mode_gate(mode, draft.portfolio),
        GateResult(
            gate_name="Hard_EvidenceAvailability",
            passed=(
                len(source_ids) >= 3
                and len(domains) >= 2
                and bool(high_quality)
            ),
            reason=(
                f"sources={len(source_ids)}; independent_domains="
                f"{len(domains)}; high_quality={len(high_quality)}"
            ),
        ),
        _basic_l0_gate(draft.meta),
        *base,
        *output_validator.run_all_validations(
            draft.variables,
            draft.drivers,
            draft.flow_feedback,
            draft.regime,
            draft.distortion,
            draft.alpha,
            draft.portfolio,
        ),
        ResearchValidator().validate_entity_profile(profile, source_ids),
        FinancialConsistencyValidator().validate(profile, analysis_date),
        coverage.validate_l0(draft.meta, profile),
        coverage.validate_l1(draft.variables, profile),
        coverage.validate_l2(draft.drivers, profile),
        research.validate_citations(
            draft.distortion, source_ids, "L5"
        ),
        _citation_independence_gate(
            "L5", draft.distortion, records_by_id
        ),
        research.validate_citations(draft.alpha, source_ids, "L6"),
        _citation_independence_gate(
            "L6", draft.alpha, records_by_id
        ),
        research.validate_confidence_evidence_cap(
            draft.alpha, records_by_id
        ),
        research.validate_prior_decomposition(
            draft.alpha, source_ids
        ),
        research.validate_chokepoint_closure(
            draft.meta, draft.flow_feedback, draft.alpha
        ),
        TemporalGroundingValidator().validate_alpha(
            draft.alpha, profile, analysis_date
        ),
        research.validate_financial_quality(draft.alpha, profile),
        research.validate_advice_boundary(draft.alpha),
        research.validate_regime_alpha_reconciliation(
            draft.regime, draft.alpha
        ),
        InvestmentValidator().validate(
            draft.portfolio, profile, analysis_date, source_ids
        ),
    ]
    return GateValidationReport(gates=gates)


def _citation_independence_gate(
    layer: str,
    value: DistortionEngine | AlphaEngine,
    records_by_id: dict[str, EvidenceRecord],
) -> GateResult:
    """Independence is counted by upstream origin, not URL: two pages
    repeating one upstream report are one source."""
    support = list(value.supporting_evidence_ids)
    contradiction = list(value.contradicting_evidence_ids)
    support_origins = {
        records_by_id[source_id].origin_key
        for source_id in support
        if source_id in records_by_id
    }
    contradiction_origins = {
        records_by_id[source_id].origin_key
        for source_id in contradiction
        if source_id in records_by_id
    }
    passed = (
        len(support_origins) >= 2
        and bool(contradiction_origins)
    )
    return GateResult(
        gate_name=f"Hard_{layer}SourceIndependence",
        passed=passed,
        reason=(
            f"support_origins={len(support_origins)}; "
            f"contradiction_origins={len(contradiction_origins)}"
        ),
    )


def _stage_validation(
    stage: str,
    value: BaseModel,
    *,
    profile: EntityProfile,
    store: EvidenceStore,
    analysis_date: date,
    run_dir: Path,
    mode: GenerationMode,
) -> GateValidationReport:
    output = OutputValidator(collected_data={})
    research = ResearchValidator()
    coverage = CoverageValidator()
    source_ids = store.source_ids
    records_by_id = {
        record.source_id: record for record in store.records()
    }

    if stage == "l0":
        assert isinstance(value, MetaSystemDefinition)
        gates = [
            _basic_l0_gate(value),
            coverage.validate_l0(value, profile),
        ]
    elif stage == "l1":
        assert isinstance(value, VariableMapping)
        gates = [
            output.validate_variable_completeness(value),
            output.validate_de_entity(value),
            output.validate_de_narrative(value),
            coverage.validate_l1(value, profile),
        ]
    elif stage == "l2":
        assert isinstance(value, DriverSpace)
        gates = [
            output.validate_driver_binding(value),
            coverage.validate_l2(value, profile),
        ]
    elif stage == "l3":
        assert isinstance(value, FlowFeedbackSystem)
        gates = [
            output.validate_feedback_completeness(value),
            output.validate_chokepoints(value),
        ]
    elif stage == "nonlinear":
        assert isinstance(value, NonlinearDynamics)
        gates = [
            GateResult(
                gate_name="NonlinearSchema",
                passed=True,
                reason="Inventory, capacity lag, and elasticity are present",
            )
        ]
    elif stage == "l4":
        assert isinstance(value, RegimeEngine)
        gates = [output.validate_regime(value)]
    elif stage == "l5":
        assert isinstance(value, DistortionEngine)
        gates = [
            output.validate_distortion(value),
            research.validate_citations(value, source_ids, "L5"),
            _citation_independence_gate(
                "L5", value, records_by_id
            ),
        ]
    elif stage == "l6":
        assert isinstance(value, AlphaEngine)
        regime = _read_stage(run_dir, "l4")
        assert isinstance(regime, RegimeEngine)
        meta = _read_stage(run_dir, "l0")
        assert isinstance(meta, MetaSystemDefinition)
        flow = _read_stage(run_dir, "l3")
        assert isinstance(flow, FlowFeedbackSystem)
        gates = [
            output.validate_alpha_completeness(value),
            research.validate_citations(value, source_ids, "L6"),
            _citation_independence_gate(
                "L6", value, records_by_id
            ),
            research.validate_confidence_evidence_cap(
                value, records_by_id
            ),
            research.validate_prior_decomposition(value, source_ids),
            research.validate_chokepoint_closure(meta, flow, value),
            TemporalGroundingValidator().validate_alpha(
                value, profile, analysis_date
            ),
            research.validate_financial_quality(value, profile),
            research.validate_advice_boundary(value),
            research.validate_regime_alpha_reconciliation(
                regime, value
            ),
        ]
    elif stage == "l7-draft":
        assert isinstance(value, InvestmentMapping)
        gates = [
            GateResult(
                gate_name="L7DraftSchema",
                passed=mode != GenerationMode.CORE,
                reason=(
                    "L7 draft ready for asset-specific search"
                    if mode != GenerationMode.CORE
                    else "Core mode omits L7"
                ),
            )
        ]
    elif stage == "l7-final":
        assert isinstance(value, InvestmentMapping)
        alpha = _read_stage(run_dir, "l6")
        assert isinstance(alpha, AlphaEngine)
        gates = [
            output.validate_l7_consistency(alpha, value),
            InvestmentValidator().validate(
                value, profile, analysis_date, source_ids
            ),
        ]
    else:
        raise ValueError(f"Unsupported stage: {stage}")
    return GateValidationReport(gates=gates)


def _required_prior_stage(stage: str) -> str | None:
    return {
        "l0": None,
        "l1": "l0",
        "l2": "l1",
        "l3": "l2",
        "nonlinear": "l3",
        "l4": "nonlinear",
        "l5": "l4",
        "l6": "l5",
        "l7-draft": "l6",
        "l7-final": "l7-draft",
    }[stage]


def _record_stage_progress(
    run_dir: Path,
    stage: str,
    search: dict[str, Any],
) -> None:
    manifest_path = run_dir / "run_manifest.json"
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        manifest = {}
    stages = manifest.setdefault("stages", {})
    stages[stage] = {
        "status": "completed",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "artifact": str(
            run_dir / "profile.json"
            if stage == "profile"
            else _stage_artifact(run_dir, stage)
        ),
        "search": search,
    }
    manifest["status"] = "in_progress"
    _write_json(manifest_path, manifest)


def advance_stage(
    subject: str,
    stage: str,
    input_path: str | Path,
    *,
    root: str | Path = ".",
    run_dir: str | Path,
) -> dict[str, Any]:
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    target = _validated_run_dir(workspace, run_dir)
    root_path = Path(root).resolve()

    if stage == "profile":
        profile_result = save_profile(
            subject, input_path, root=root_path
        )
        if not profile_result.get("ok"):
            return profile_result
        profile = _load_profile(workspace)
        (target / "profile.json").write_text(
            profile.model_dump_json(indent=2), encoding="utf-8"
        )
        search = _search_after_stage(
            workspace, request, root_path, "profile", profile
        )
        _record_stage_progress(target, "profile", search)
        return {
            **profile_result,
            "stage": "profile",
            "search": search,
            "next": (
                "Regenerate the profile from refreshed evidence when gaps "
                "were searched; otherwise continue to L0."
            ),
        }

    if stage not in STAGE_FILES:
        raise ValueError(
            "Stage must be profile, l0, l1, l2, l3, nonlinear, l4, "
            "l5, l6, l7-draft, or l7-final."
        )
    prior = _required_prior_stage(stage)
    if prior and not _stage_artifact(target, prior).exists():
        raise FileNotFoundError(
            f"Stage `{stage}` requires completed `{prior}` first."
        )
    if stage == "l0" and _pending_resolution(workspace, target):
        return {
            "ok": False,
            "stage": stage,
            "error": (
                "Falsifier review pending: grade the previous run's "
                "commitments in prior_commitments.json and record them "
                "with `resolve` before starting L0."
            ),
            "prior_commitments": str(target / "prior_commitments.json"),
        }
    profile = _load_profile(workspace)
    value = _load_stage_component(input_path, stage)
    store = load_evidence_store(
        workspace, analysis_date=request.analysis_date
    )
    validation = _stage_validation(
        stage,
        value,
        profile=profile,
        store=store,
        analysis_date=request.analysis_date,
        run_dir=target,
        mode=request.generation_mode,
    )
    failures = validation.failed_gates
    if failures:
        return {
            "ok": False,
            "stage": stage,
            "error": "Stage validation failed; revise before continuing.",
            "gates": [gate.model_dump() for gate in validation.gates],
            "failed_gates": [gate.model_dump() for gate in failures],
        }

    artifact = _stage_artifact(target, stage)
    artifact.write_text(
        value.model_dump_json(indent=2), encoding="utf-8"
    )
    search = _search_after_stage(
        workspace, request, root_path, stage, value
    )
    _record_stage_progress(target, stage, search)
    return {
        "ok": True,
        "stage": stage,
        "artifact": str(artifact),
        "gates": [gate.model_dump() for gate in validation.gates],
        "search": search,
    }


def _hard_failures(gates: Iterable[GateResult]) -> list[GateResult]:
    return [
        gate
        for gate in gates
        if not gate.passed and gate.gate_name.startswith("Hard_")
    ]


def _extract_fragilities(draft: AnalysisDraft) -> list[str]:
    if draft.key_fragilities:
        return draft.key_fragilities
    fragilities: list[str] = []
    if draft.regime.current_regime in {"bubble", "collapse", "shock"}:
        fragilities.append(
            f"System in {draft.regime.current_regime} regime "
            f"(confidence={draft.regime.confidence:.0%})"
        )
    transition = draft.regime.transition_probability
    if (
        transition.probability > 0.5
        and transition.next_regime
        in {"collapse", "shock", "contraction"}
    ):
        fragilities.append(
            f"{transition.probability:.0%} transition probability to "
            f"{transition.next_regime}"
        )
    fragilities.extend(
        f"Single-point chokepoint: {point.name} ({point.flow_type})"
        for point in draft.flow_feedback.chokepoints
        if point.concentration == "single_point"
    )
    if draft.alpha.irreversibility == "absorbing":
        fragilities.append(
            "Absorbing downside state: "
            + (draft.alpha.ruin_path[:140] or "see ruin path")
        )
    if draft.distortion.distortion_score > 0.6:
        fragilities.append(
            f"High evidence-contingent distortion "
            f"({draft.distortion.distortion_score:.0%})"
        )
    fragilities.extend(
        f"Mispricing: {item[:140]}"
        for item in draft.distortion.mispricing_sources[:3]
    )
    return fragilities


def _validated_output(
    draft: AnalysisDraft, report: GateValidationReport
) -> ScanOutput:
    companies = ScoreCalibrator.calibrate_companies(
        draft.companies_ranked
    )
    return ScanOutput(
        industry=draft.industry,
        region=draft.region,
        time_horizon=draft.time_horizon,
        meta=draft.meta,
        variables=draft.variables,
        drivers=draft.drivers,
        flow_feedback=draft.flow_feedback,
        nonlinear_dynamics=draft.nonlinear_dynamics,
        regime=draft.regime,
        distortion=draft.distortion,
        alpha=draft.alpha,
        portfolio=draft.portfolio,
        industry_score=draft.industry_score,
        companies_ranked=companies,
        gate_validation=report,
        key_fragilities=_extract_fragilities(draft),
    )


def _validated_run_dir(
    workspace: ResearchWorkspace, run_dir: str | Path | None
) -> Path:
    target = (
        Path(run_dir).expanduser().resolve()
        if run_dir
        else workspace.create_report_run().resolve()
    )
    report_root = workspace.report_dir.resolve()
    if not target.is_relative_to(report_root):
        raise ValueError(
            f"run-dir must be inside the subject report directory: {report_root}"
        )
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "run_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            manifest = {}
        if manifest.get("status") == "completed":
            raise ValueError(
                "This run is already completed. Initialize a new run "
                "instead of replacing a published report."
            )
    return target


def compose_draft_from_stages(
    subject: str,
    *,
    root: str | Path = ".",
    run_dir: str | Path,
) -> AnalysisDraft:
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    target = _validated_run_dir(workspace, run_dir)
    values = {
        stage: _read_stage(target, stage)
        for stage in (
            "l0",
            "l1",
            "l2",
            "l3",
            "nonlinear",
            "l4",
            "l5",
            "l6",
        )
    }
    portfolio: InvestmentMapping | None = None
    if request.generation_mode == GenerationMode.FULL:
        loaded_portfolio = _read_stage(target, "l7-final")
        assert isinstance(loaded_portfolio, InvestmentMapping)
        portfolio = loaded_portfolio
    elif request.generation_mode == GenerationMode.VALIDATE_ONLY:
        l7_path = _stage_artifact(target, "l7-final")
        if l7_path.exists():
            loaded_portfolio = _read_stage(target, "l7-final")
            assert isinstance(loaded_portfolio, InvestmentMapping)
            portfolio = loaded_portfolio

    return AnalysisDraft(
        industry=request.subject,
        region=request.region,
        time_horizon=request.time_horizon,
        meta=values["l0"],
        variables=values["l1"],
        drivers=values["l2"],
        flow_feedback=values["l3"],
        nonlinear_dynamics=values["nonlinear"],
        regime=values["l4"],
        distortion=values["l5"],
        alpha=values["l6"],
        portfolio=portfolio,
    )


def finalize_draft(
    subject: str,
    input_path: str | Path | None = None,
    *,
    root: str | Path = ".",
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace = workspace_for(subject, root)
    request = _load_request(workspace)
    profile = _load_profile(workspace)
    target = _validated_run_dir(workspace, run_dir)
    draft = (
        AnalysisDraft.model_validate_json(
            Path(input_path).read_text(encoding="utf-8")
        )
        if input_path
        else compose_draft_from_stages(
            subject, root=root, run_dir=target
        )
    )
    if draft.industry.strip() != request.subject.strip():
        raise ValueError(
            f"Draft industry `{draft.industry}` does not match "
            f"workspace subject `{request.subject}`."
        )
    if draft.region != request.region:
        raise ValueError(
            f"Draft region `{draft.region}` does not match "
            f"request region `{request.region}`."
        )
    if draft.time_horizon != request.time_horizon:
        raise ValueError(
            "Draft time horizon does not match the initialized request."
        )

    _write_json(target / "analysis_draft.json", draft.model_dump(mode="json"))
    store = load_evidence_store(
        workspace, analysis_date=request.analysis_date
    )
    report = validate_draft(
        draft,
        profile,
        store,
        request.analysis_date,
        request.generation_mode,
    )
    hard_failures = _hard_failures(report.gates)
    validation_payload = {
        "all_passed": report.all_passed,
        "publication_blocked": bool(hard_failures),
        "hard_failures": [
            gate.model_dump() for gate in hard_failures
        ],
        "gates": [gate.model_dump() for gate in report.gates],
        "known_source_ids": sorted(store.source_ids),
        "evidence_summary": {
            "unique_sources": store.unique_source_count,
            "independent_domains": len({
                record.domain for record in store.records()
            }),
            "high_quality_sources": sum(
                record.quality_score >= 0.78
                for record in store.records()
            ),
        },
    }
    _write_json(target / "validation.json", validation_payload)

    manifest = {
        "status": "blocked" if hard_failures else "completed",
        "subject": request.subject,
        "generation_mode": request.generation_mode.value,
        "analysis_date": request.analysis_date.isoformat(),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(workspace.data_dir),
        "run_dir": str(target),
        "validation": str(target / "validation.json"),
        "report": None,
    }
    result: dict[str, Any] = {
        "ok": not hard_failures,
        "status": manifest["status"],
        "run_dir": str(target),
        "validation": str(target / "validation.json"),
        "hard_failures": [
            gate.model_dump() for gate in hard_failures
        ],
    }
    if hard_failures:
        _write_json(target / "run_manifest.json", manifest)
        result["error"] = (
            "Research integrity gates failed; report publication blocked."
        )
        return result

    output = _validated_output(draft, report)
    output_path = target / "scan_output.json"
    report_path = target / "scan_report.md"
    output_path.write_text(
        output.model_dump_json(indent=2), encoding="utf-8"
    )
    resolution_log = _load_resolution_log(workspace)
    calibration = (
        resolution_log.get("calibration")
        or (_calibration_summary(resolution_log["entries"])
            if resolution_log["entries"] else None)
    )
    report_path.write_text(
        render_report(output, calibration=calibration), encoding="utf-8"
    )
    manifest["report"] = str(report_path)
    manifest["output"] = str(output_path)
    _write_json(target / "run_manifest.json", manifest)
    result.update({
        "report": str(report_path),
        "output": str(output_path),
        "soft_failures": [
            gate.model_dump()
            for gate in report.failed_gates
            if not gate.gate_name.startswith("Hard_")
        ],
    })
    return result


def schema_for(kind: str) -> dict[str, Any]:
    schemas = {
        "profile": EntityProfile.model_json_schema,
        "analysis": AnalysisDraft.model_json_schema,
        "evidence": EvidenceImportItem.model_json_schema,
    }
    if kind not in schemas:
        raise ValueError("Schema must be profile, analysis, or evidence.")
    return schemas[kind]()


def methodology_for(system_type: str) -> dict[str, Any]:
    template = match_template(system_type)
    return {
        "matched": template is not None,
        "template": template.name if template else None,
        "methodology": get_template_methodology(template),
    }
