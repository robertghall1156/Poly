"""News normalisation, duplicate detection, clustering, principle linking."""
from __future__ import annotations

from datetime import UTC, datetime

from poly.providers.base import RawArticle
from poly.providers.news.rss import parse_feed_bytes
from poly.services import ingest
from poly.services.analysis import analyze_story
from poly.services.clustering import similarity
from poly.services.topics import tag_topics

from .conftest import FIXTURES


def _raws(name: str) -> list[RawArticle]:
    return parse_feed_bytes((FIXTURES / name).read_bytes())


def test_rss_parsing_extracts_fields():
    raws = _raws("sample_feed_a.xml")
    assert len(raws) == 3
    a = raws[0]
    assert a.title.startswith("Senate passes bill")
    assert a.publication == "Example Wire"
    assert a.author == "Jane Reporter"
    assert a.published_at == datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    assert "52-48" in a.summary


def test_normalize_canonicalizes_urls_and_titles():
    raw = _raws("sample_feed_a.xml")[0]
    norm = ingest.normalize(raw)
    assert norm["canonical_url"] == "https://example-wire.com/politics/senate-corporate-tax"
    assert "utm_source" not in norm["canonical_url"]
    assert norm["url_hash"] == ingest.url_hash("http://www.example-wire.com/politics/senate-corporate-tax/")
    assert ingest.normalize_title("Some headline - Example Daily") == "Some headline"
    assert "taxes" in norm["topics"]


def test_title_simhash_is_close_for_near_duplicates():
    a = ingest.title_simhash("Senate passes bill raising corporate tax rate to 25% after loophole review")
    b = ingest.title_simhash("Senate passes bill raising corporate tax rate to 25% after loophole review - Example Daily")
    c = ingest.title_simhash("City council approves new bike lanes downtown")
    assert ingest.hamming(a, b) <= 3
    assert ingest.hamming(a, c) > 10


def test_topic_tagging_minimum_taxonomy():
    assert "executive compensation" in tag_topics("The board approved a new CEO pay package with stock options")
    assert "immigration" in tag_topics("Lawmakers debate a new visa program at the border")
    assert "ai" in tag_topics("OpenAI released a new large language model")


def test_ingest_dedupes_and_clusters(db, seeded, ingested):
    stats_a, stats_b = ingested["a"], ingested["b"]
    assert stats_a["inserted"] == 3 and stats_a["duplicates"] == 0
    # exact URL copy + near-identical title copy are duplicates; two new articles remain
    assert stats_b["duplicates"] == 2
    assert stats_b["inserted"] == 2
    from poly.models import Article, Story

    visible = [a for a in db.query(Article).all() if not a.duplicate_of_id and a.publication in ("Example Wire", "Example Daily")]
    assert len(visible) == 5
    tax_articles = [a for a in visible if "corporate tax" in a.title.lower() or "Corporate tax" in a.title]
    stories = {a.story_id for a in tax_articles}
    assert len(stories) == 1, "the Senate vote and the House follow-up should share one story"
    story = db.get(Story, stories.pop())
    assert len([a for a in story.articles if not a.duplicate_of_id]) == 2
    assert story.status in ("developing", "new")
    bike = next(a for a in visible if "bike" in a.title.lower())
    assert bike.story_id != story.id
    assert len(story.events) >= 2  # first-seen + follow-up


def test_similarity_separates_unrelated():
    hi = similarity("Senate passes corporate tax bill", ["taxes"], "Corporate tax hike heads to House after Senate vote", ["taxes", "congress"])
    lo = similarity("Senate passes corporate tax bill", ["taxes"], "City council approves new bike lanes downtown", ["infrastructure"])
    assert hi > lo
    assert lo < 0.32


def test_story_analysis_links_principles_and_extracts_claims(db, seeded, ingested):
    from poly.models import Story

    story = next(s for s in db.query(Story).all() if "corporate tax" in s.title.lower())
    analyze_story(db, story)
    db.refresh(story)
    assert story.analysis_source.startswith("llm:")
    assert story.relevance_score > 0
    titles = {l.principle.title for l in story.principle_links}
    assert any("loophole" in t.lower() or "tax" in t.lower() for t in titles), titles
    types = {c.claim_type for c in story.claims}
    assert "FACT" in types and "OPINION" in types
    assert story.why_it_matters
    assert story.recommended_format


def test_provider_fallback_never_goes_to_cloud(db, seeded):
    """When the first local model fails, the router tries the next LOCAL model, never cloud."""
    from poly.models import LocalModel
    from poly.providers.base import ChatMessage, ProviderError
    from poly.providers.registry import Router, candidates

    broken = LocalModel(name="broken-local", runtime="openai_compat", endpoint="http://127.0.0.1:1/v1", tasks=["FAST"], priority=0, enabled=True, detected=True)
    cloud = LocalModel(name="claude-cloud", runtime="anthropic", endpoint="https://api.anthropic.com", tasks=["FAST"], priority=0, enabled=True, detected=True, locality="cloud")
    db.add_all([broken, cloud])
    db.commit()
    try:
        order = candidates(db, "FAST")
        assert order[0].name == "broken-local"
        assert all(m.locality == "local" for m in order)
        res = Router(db).chat("FAST", [ChatMessage("user", "hi")])
        assert res.provider == "mock"
        assert res.model == "mock-model"
        db.refresh(broken)
        assert broken.last_error  # failure recorded for the UI
        # disable the mock → no local model left → hard failure, not cloud
        mock = next(m for m in candidates(db, "FAST") if m.runtime == "mock")
        mock.enabled = False
        db.commit()
        try:
            Router(db).chat("FAST", [ChatMessage("user", "hi")])
            raise AssertionError("should have raised")
        except ProviderError as e:
            assert "No local model" in str(e)
        mock.enabled = True
        db.commit()
    finally:
        db.delete(broken)
        db.delete(cloud)
        db.commit()
