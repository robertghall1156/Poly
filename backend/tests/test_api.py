"""End-to-end API flow through FastAPI: dashboard → story → think → brief → content → images → jobs."""
from __future__ import annotations

import io

from .conftest import FIXTURES


def test_health_and_dashboard(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"]
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["principles"] >= 30
    assert body["privacy"]["local_ai_only"] is True


def test_principle_crud(client):
    r = client.post("/api/principles", json={"title": "Test principle", "category": "Testing", "current_position": "Position A", "rationale": "Because"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.patch(f"/api/principles/{pid}", json={"current_position": "Position B", "reason_for_change": "changed mind"})
    assert r.json()["current_position"] == "Position B"
    r = client.get(f"/api/principles/{pid}")
    assert len(r.json()["revisions"]) == 2
    r = client.post(f"/api/principles/{pid}/counterarguments", json={"argument": "But what about X?", "strength": "strong"})
    assert r.status_code == 201
    r = client.post(f"/api/principles/{pid}/evidence", json={"source": "GAO", "url": "https://gao.gov/x", "publication_date": "2026-01-02"})
    assert r.status_code == 201


def test_feed_ingest_via_api_with_local_file(client, data_dir):
    """Feeds can be local file URLs too — used here so the pipeline runs without network."""
    fixture = FIXTURES / "sample_feed_c.xml"
    r = client.post("/api/feeds", json={"name": "Local fixture", "url": f"file://{fixture}", "category": "test"})
    assert r.status_code == 201
    fid = r.json()["id"]
    r = client.post(f"/api/feeds/{fid}/fetch")
    assert r.status_code == 200
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] in ("succeeded", "failed")
    r = client.get("/api/stories?days=36500")
    assert r.status_code == 200
    titles = [s["title"] for s in r.json()]
    assert any("premiums" in t for t in titles) and any("apprenticeship" in t.lower() for t in titles)
    sid = next(s["id"] for s in r.json() if "premiums" in s["title"])
    story = client.get(f"/api/stories/{sid}").json()
    assert "articles" in story and "principles" in story and "events" in story
    r = client.post(f"/api/stories/{sid}/action", json={"action": "develop_position"})
    assert r.json()["dashboard_action"] == "develop_position"


def test_think_and_content_flow(client):
    stories = client.get("/api/stories?days=36500").json()
    sid = stories[0]["id"]
    r = client.post("/api/think/sessions", json={"title": "Think about it", "story_id": sid})
    assert r.status_code == 201
    s = r.json()
    assert s["messages"][-1]["role"] == "assistant"
    r = client.post(f"/api/think/sessions/{s['id']}/answer", json={"text": "I think the incentives are the issue."})
    assert len(r.json()["messages"]) == 3
    r = client.post(f"/api/think/sessions/{s['id']}/brief")
    assert r.status_code == 200
    bid = r.json()["id"]
    r = client.post(f"/api/think/briefs/{bid}/approve", json={"mode": "new", "title": "API-created principle", "category": "Positions"})
    assert r.status_code == 200 and r.json()["principle"]["title"] == "API-created principle"
    r = client.post("/api/content/generate", json={"format": "podcast", "story_id": sid, "brief_id": bid, "background": False})
    assert r.status_code == 200
    item = r.json()["item"]
    assert item["lineage"]["brief"]["id"] == bid
    r = client.post(f"/api/content/{item['id']}/social")
    assert r.status_code == 200
    tree = client.get(f"/api/content/{item['id']}/tree").json()
    assert len(tree["children"]) >= 5
    r = client.post(f"/api/content/{item['id']}/status", json={"status": "READY"})
    assert r.status_code == 409  # fact check gate
    r = client.post(f"/api/content/{item['id']}/fact-check")
    assert r.status_code == 200
    board = client.get("/api/content/calendar/board").json()
    assert "SCRIPTING" in board and any(c["id"] == item["id"] for c in board["SCRIPTING"])
    r = client.post("/api/book/notes", json={"title": "Save this", "kind": "chapter_idea", "story_id": sid, "content_item_id": item["id"]})
    assert r.status_code == 201
    r = client.get("/api/search?q=corporate tax")
    assert r.status_code == 200 and r.json()["hits"]


def test_images_and_settings(client):
    r = client.post("/api/images", json={"kind": "quote_card", "params": {"quote": "Power needs a counterweight.", "attribution": "Poly"}})
    assert r.status_code == 201
    iid = r.json()["id"]
    assert r.json()["approved"] is False
    assert client.get(f"/api/images/{iid}/file").status_code == 200
    r = client.post("/api/images", json={"kind": "chart", "params": {"title": "Effective corporate tax rate", "labels": ["2000", "2010", "2020"], "values": [30, 25, 18], "unit": "%", "source": "CBO"}})
    assert r.status_code == 201
    r = client.post("/api/images", json={"kind": "generated", "params": {"prompt": "x"}})
    assert r.status_code == 503  # no local image model configured → disabled, never cloud
    r = client.patch("/api/settings/privacy", json={"allow_cloud_ai": True})
    assert r.status_code == 400  # needs explicit confirmation
    r = client.get("/api/local-ai")
    assert r.status_code == 200 and r.json()["assignments"]["REASONING"]
    r = client.post("/api/content/metrics/import-csv", files={"file": ("m.csv", io.BytesIO(b"title,platform,views,likes\nnope,youtube,10,1\n"), "text/csv")})
    assert r.status_code == 200 and r.json()["skipped"] == 1


def test_persistence_survives_new_session(engine):
    """State written through the API is in the database, not in memory."""
    from sqlalchemy import text

    with engine.connect() as conn:
        n = conn.execute(text("select count(*) from principles")).scalar()
        assert n >= 30
        assert conn.execute(text("select count(*) from content_items")).scalar() >= 1
        assert conn.execute(text("select count(*) from embeddings")).scalar() > 0
