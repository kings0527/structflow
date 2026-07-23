from structflow.data_collector import (
    DataCollector,
    SearchContext,
    shorten_for_query,
)
from structflow.evidence import EvidenceRecord
from structflow.system_templates import match_template


def test_query_shortening_keeps_english_phrase():
    assert shorten_for_query(
        "AI Workload Growth", max_len=50
    ) == "AI Workload Growth"


def test_query_shortening_stops_at_punctuation():
    assert shorten_for_query(
        "产能上升；价格承压", max_len=50
    ) == "产能上升"


def test_short_template_token_does_not_match_word_fragment():
    assert match_template("hospitality market") is None


def test_layer_routes_close_evidence_handoffs():
    routes = DataCollector.LAYER_CONTEXT_PREFIXES
    assert "l4_" in routes["l5"]
    assert "l4_" in routes["l6"]
    assert "l6_" in routes["l7"]
    assert "l7_" in routes["l7"]


def test_total_sources_counts_unique_evidence():
    context = SearchContext()
    record = EvidenceRecord(
        category="pricing",
        provider="test",
        query="q",
        title="t",
        url="https://example.com/a",
        content="evidence",
    )
    context.add_evidence([record, record])
    assert context.total_sources == 1
