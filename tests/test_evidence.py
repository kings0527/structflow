from datetime import datetime, timezone

from structflow.evidence import (
    EvidenceRecord,
    EvidenceStore,
    canonicalize_url,
    infer_source_type,
    recency_score,
)


def _record(
    category: str, url: str, score: float = 0.8
) -> EvidenceRecord:
    return EvidenceRecord(
        category=category,
        provider="test",
        query="test query",
        title="Evidence title",
        url=url,
        content=(
            "A factual excerpt with enough detail "
            "for model grounding."
        ),
        source_type="industry_research",
        relevance_score=score,
        quality_score=0.8,
        freshness_score=0.8,
    )


def test_canonicalize_url_removes_tracking_parameters():
    assert canonicalize_url(
        "https://www.example.com/report/"
        "?utm_source=x&id=7#top"
    ) == "https://example.com/report?id=7"


def test_store_deduplicates_source_across_categories():
    store = EvidenceStore()
    store.add(_record(
        "market_structure",
        "https://example.com/report?utm_source=a",
    ))
    store.add(_record(
        "contradiction_bear",
        "https://example.com/report",
    ))
    assert store.unique_source_count == 1
    assert store.manifest()[0]["categories"] == [
        "contradiction_bear",
        "market_structure",
    ]
    assert store.manifest()[0]["queries"] == ["test query"]


def test_context_preserves_provenance_and_budget():
    store = EvidenceStore()
    store.add(_record(
        "pricing", "https://example.com/price"
    ))
    context = store.compile_context(
        ["pricing"],
        max_tokens=500,
        max_per_category=3,
        max_per_domain=2,
    )
    assert "[src_" in context
    assert "https://example.com/price" in context
    assert "untrusted external evidence" in context
    assert len(context) <= 1500


def test_source_type_and_recency_are_explicit():
    assert infer_source_type(
        "https://www.sec.gov/Archives/test", "10-K"
    ) == "regulator"
    recent = recency_score(
        "2026-07-01",
        now=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    stale = recency_score(
        "2020-01-01",
        now=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    assert recent > stale
