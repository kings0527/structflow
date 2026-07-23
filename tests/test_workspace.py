import json
from pathlib import Path

from structflow.data_collector import DataCollector
from structflow.evidence import EvidenceRecord
from structflow.workspace import MaterialLibrary, ResearchWorkspace


def _cached_record() -> EvidenceRecord:
    return EvidenceRecord(
        category="industry_overview",
        provider="fixture",
        query="cached query",
        title="Cached evidence",
        url="https://cache.example/evidence",
        content="This evidence came from the persistent cache.",
        published_at="2026-01-01",
        source_type="industry_research",
        relevance_score=0.8,
        quality_score=0.8,
        freshness_score=0.5,
    )


def _write_cache(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    record = _cached_record().to_dict()
    record["categories"] = ["industry_overview"]
    record["queries"] = ["cached query"]
    path = directory / "search_data.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "queries_executed": ["cached query"],
                    "logical_query_keys": [
                        "industry_overview:cached query"
                    ],
                },
                "categories": {
                    "industry_overview": ["cached raw content"]
                },
                "evidence": [record],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_subject_workspace_separates_data_and_report_runs(tmp_path):
    workspace = ResearchWorkspace(tmp_path / "scans", "示例/公司")
    workspace.prepare()
    first = workspace.create_report_run("20300101_120000")
    second = workspace.create_report_run("20300101_120000")

    assert workspace.search_dir == workspace.root / "data" / "search"
    assert workspace.materials_dir == workspace.root / "data" / "materials"
    assert first.parent == workspace.root / "report"
    assert second.name == "20300101_120000_01"


def test_workspace_migrates_latest_legacy_search_cache(tmp_path):
    base = tmp_path / "scans"
    older = _write_cache(base / "示例公司_20290101_000000")
    newer = _write_cache(base / "示例公司_20300101_000000")
    older.touch()
    newer.touch()
    workspace = ResearchWorkspace(base, "示例公司")

    migrated = workspace.migrate_legacy_cache()

    assert migrated == workspace.search_cache_file
    assert workspace.search_cache_file.read_text() == newer.read_text()


def test_markdown_material_is_hash_deduplicated_and_compiled(tmp_path):
    source = tmp_path / "brief.md"
    source.write_text(
        "# Research brief\n\nA material fact with a source reference.",
        encoding="utf-8",
    )
    library = MaterialLibrary(tmp_path / "materials")

    first = library.sync([source])
    second = library.sync([source])
    records = library.evidence_records()

    assert first["ready"] == 1
    assert second["ready"] == 1
    assert len(records) == 1
    assert records[0].source_type == "user_material"
    assert "material fact" in records[0].content


def test_cached_collector_works_without_network_client(tmp_path, monkeypatch):
    cache_dir = tmp_path / "search"
    _write_cache(cache_dir)
    monkeypatch.setattr("structflow.data_collector.config.tavily.api_key", "")
    monkeypatch.setattr("structflow.data_collector.config.anysearch.api_key", "")
    collector = DataCollector(
        industry="示例公司",
        cache_only=True,
        output_dir=str(cache_dir),
    )

    loaded = collector.load_cache(cache_dir)
    context = collector.get_resolution_context()

    assert loaded == 1
    assert "persistent cache" in context
    assert collector._reserve_logical_query("new query", "new_category") is False


def test_collector_accepts_anysearch_as_the_only_provider(monkeypatch):
    monkeypatch.setattr("structflow.data_collector.config.tavily.api_key", "")
    monkeypatch.setattr(
        "structflow.data_collector.config.anysearch.api_key",
        "test-anysearch-key",
    )

    collector = DataCollector(
        industry="示例公司",
        cache_only=False,
    )

    assert collector.tavily is None
    assert collector.anysearch is not None


def test_material_evidence_is_available_to_every_layer(tmp_path, monkeypatch):
    source = tmp_path / "memo.md"
    source.write_text("Locally supplied operational evidence.", encoding="utf-8")
    library = MaterialLibrary(tmp_path / "materials")
    library.sync([source])
    monkeypatch.setattr("structflow.data_collector.config.tavily.api_key", "")
    monkeypatch.setattr("structflow.data_collector.config.anysearch.api_key", "")
    collector = DataCollector(industry="示例公司", cache_only=True)
    collector.context.add_evidence(library.evidence_records())

    for layer in ("l0", "l1", "l2", "l3", "l4", "l5", "l6", "l7"):
        assert "Locally supplied operational evidence" in (
            collector.get_context_for_layer(layer)
        )
