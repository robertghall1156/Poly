"""Principles/revisions, Think Mode, content lineage, fact-check gate, privacy gate, search."""
from __future__ import annotations

import pytest

from poly.services import content as content_svc
from poly.services import factcheck, principles, think
from poly.services.privacy import NetworkPolicy
from poly.services.search import search


def test_markdown_roundtrip(db, seeded):
    rows = principles.list_principles(db)
    assert len(rows) >= 30
    md = principles.to_markdown(rows)
    parsed = principles.parse_markdown(md)
    assert len(parsed) == len(rows)
    assert {p["title"] for p in parsed} == {r.title for r in rows}


def test_update_creates_revision(db, seeded):
    p = principles.list_principles(db)[0]
    before = len(p.revisions)
    principles.update_principle(db, p, {"current_position": p.current_position + " (refined)"}, reason="test")
    db.refresh(p)
    assert len(p.revisions) == before + 1
    assert p.revisions[-1].reason_for_change == "test"
    assert p.revisions[-1].new_position.endswith("(refined)")


def test_think_mode_interview_to_approved_principle(db, seeded):
    s = think.start_session(db, title="Should unrealized gains be taxed?", question="Should unrealized gains above $100M be taxed annually?")
    q1 = think.next_question(db, s)
    assert q1["role"] == "assistant" and q1["content"].endswith("?")
    assert s.principle_ids_considered, "relevant principles should be retrieved"
    think.answer(db, s, "My instinct is yes, but only at extreme wealth levels.")
    q2 = think.next_question(db, s)
    assert q2["content"]
    brief = think.generate_brief(db, s)
    assert brief.position and brief.strongest_against
    assert s.status == "completed"
    n_before = len(principles.list_principles(db))
    p = think.approve_brief(db, brief, mode="new", title="Taxing extreme unrealized gains", category="Taxation")
    assert p.status == "provisional"
    assert len(principles.list_principles(db)) == n_before + 1
    assert brief.status == "approved" and brief.approved_principle_id == p.id
    assert p.counterarguments and p.counterarguments[0].argument == brief.strongest_against
    assert p.revisions[0].reason_for_change.startswith("Created from position brief")


def test_content_generation_and_lineage(db, seeded, ingested):
    from poly.models import Story

    story = next(s for s in db.query(Story).all() if "corporate tax" in s.title.lower())
    parent = content_svc.generate(db, fmt="youtube", story_id=story.id)
    assert parent.status == "SCRIPTING"
    sections = [o["section"] for o in parent.package["outline"]]
    assert sections == content_svc.LONGFORM_SECTIONS
    assert "QUESTION" in parent.script
    bundle = content_svc.generate_social_bundle(db, parent)
    assert len(bundle["children"]) >= 5
    db.refresh(parent)
    tree = content_svc.content_tree(db, parent.children[0])
    assert tree["id"] == parent.id
    assert len(tree["children"]) == len(bundle["children"])
    lin = content_svc.lineage(db, parent.children[0])
    assert lin["parents"][0]["id"] == parent.id
    assert lin["story"]["id"] == story.id
    assert parent.principle_ids


def test_fact_check_gate_blocks_ready_until_resolved(db, seeded):
    from poly.models import ContentItem

    item = ContentItem(title="Script", format="youtube", script="The corporate rate is 21%. Most billionaires pay nothing.", status="SCRIPTING")
    db.add(item)
    db.commit()
    with pytest.raises(PermissionError):
        content_svc.set_status(db, item, "READY")
    claims = factcheck.run_fact_check(db, item)
    assert {c.status for c in claims} == {"VERIFIED", "UNVERIFIED"}
    assert item.fact_check_status == "pending"
    with pytest.raises(PermissionError):
        content_svc.set_status(db, item, "READY")
    unresolved = next(c for c in claims if not c.resolved)
    factcheck.resolve_claim(db, unresolved, status="OPINION", notes="reframed as my view")
    assert item.fact_check_status == "fact_checked"
    content_svc.set_status(db, item, "READY")
    assert item.status == "READY" and item.approved_at
    # override path
    item2 = ContentItem(title="Script 2", format="podcast", script="In 2019 the rate was 35%.", status="SCRIPTING")
    db.add(item2)
    db.commit()
    factcheck.run_fact_check(db, item2)
    content_svc.set_status(db, item2, "READY", override_reason="verified offline against IRS tables")
    assert item2.fact_check_status == "overridden"


def test_privacy_policy_blocks_cloud_ai_by_default(db):
    pol = NetworkPolicy.load(db)
    assert pol.local_ai_only and pol.allow_internet_research and not pol.allow_cloud_ai
    pol.check(locality="local", purpose="ai")
    pol.check(locality="cloud", purpose="research")
    from poly.providers.base import PrivacyViolation

    with pytest.raises(PrivacyViolation):
        pol.check(locality="cloud", purpose="ai", provider="anthropic")
    pol.allow_cloud_ai = True
    with pytest.raises(PrivacyViolation):  # still blocked while Local AI Only is on
        pol.check(locality="cloud", purpose="ai")
    pol.local_ai_only = False
    pol.check(locality="cloud", purpose="ai")


def test_hybrid_search_finds_principles_and_stories(db, seeded, ingested):
    hits = search(db, "executive compensation vesting", limit=10)
    assert hits
    assert any(h.entity_type == "principle" for h in hits)
    hits2 = search(db, "corporate tax loophole", types=["story", "article"], limit=5)
    assert hits2 and hits2[0].entity_type in ("story", "article")
