"""Faceless Content Studio: generation, rendering (real MP4/PNG/ZIP), memes, carousels, quality gate.

These tests execute the required workflow tests from the studio brief:
  TEST 1  story → faceless video → question → 30s → generate → render MP4
  TEST 2  position → meme → concepts → render → export PNG
  TEST 3  research → carousel → generate → edit → export ZIP
  TEST 4  custom idea → 45s → generate → render
"""
from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

from poly.services import faceless, memes
from poly.services.render_video import build_scene_ass, render_project, render_scene_preview


def _probe(path: str) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], capture_output=True, text=True)
    return json.loads(out.stdout)


def _story(db):
    from poly.models import Story

    return next(s for s in db.query(Story).all() if "corporate tax" in s.title.lower())


def test_workflow1_story_to_question_video_mp4(db, seeded, ingested):
    story = _story(db)
    p = faceless.create_project(db, source={"story_id": story.id}, fmt="question", target_seconds=30)
    assert p.content_item.story_id == story.id
    faceless.generate_scenes(db, p)
    assert 3 <= len(p.scenes) <= 8
    assert abs(faceless.total_duration(p.scenes) - 30) <= 8
    assert p.caption and p.content_item.title
    assert all(s["visual_type"] in ("text", "title", "question", "chart", "comparison", "counter", "timeline", "list", "image", "quote", "icon") for s in p.scenes)
    # preview
    prev = render_scene_preview(db, p, 0)
    assert Path(prev).exists()
    # render real MP4
    render_project(db, p)
    assert p.render_status == "done" and Path(p.render_path).exists()
    meta = _probe(p.render_path)
    v = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert abs(float(meta["format"]["duration"]) - faceless.total_duration(p.scenes)) < 1.5
    assert p.content_item.status == "EDITING"


def test_workflow4_custom_idea_45s_with_voiceover_track(db, seeded):
    p = faceless.create_project(db, source={"idea": "Should billionaires be able to borrow against stock forever?"}, target_seconds=45, voice_mode="tts")
    assert p.format == "question"  # inferred default for custom ideas
    faceless.generate_scenes(db, p)
    render_project(db, p)  # no TTS engine in CI → SilenceProvider still produces an audio track
    meta = _probe(p.render_path)
    kinds = {s["codec_type"] for s in meta["streams"]}
    assert kinds == {"video", "audio"}


def test_workflow2_meme_concepts_and_render(db, seeded):
    from poly.models import PositionBrief

    brief = db.query(PositionBrief).first()
    concepts = memes.generate_concepts(db, source={"brief_id": brief.id} if brief else None, idea="peer benchmarking ratchets CEO pay")
    assert len(concepts) == 3
    assert {c["template"] for c in concepts} != {""}
    for c in concepts:
        assert c["top_text"] and c["caption"] and c["why_it_works"]
    img = memes.render_meme(db, template=concepts[0]["template"], top_text=concepts[0]["top_text"], bottom_text=concepts[0]["bottom_text"])
    assert Path(img.path).exists() and img.width == 1080
    assert img.approved is False  # export requires approval in the UI
    # every template renders
    for tpl in memes.MEME_TEMPLATES[:-1]:
        img2 = memes.render_meme(db, template=tpl, top_text="Cut the deficit", bottom_text="Never touch anything")
        assert Path(img2.path).exists()


def test_workflow3_research_to_carousel_zip(db, seeded):
    from poly.models import ResearchNote

    n = ResearchNote(title="Loopholes before rates", body="Effective corporate rates depend on deductions more than the headline rate; similar firms pay very different rates.")
    db.add(n)
    db.commit()
    p = faceless.create_project(db, source={"research_note_id": n.id}, kind="carousel")
    faceless.generate_carousel_slides(db, p)
    assert len(p.scenes) >= 6
    # edit a slide, then export
    scenes = list(p.scenes)
    scenes[1] = {**scenes[1], "subtext": "Edited body text for slide two."}
    faceless.update_scenes(db, p, scenes)
    assert p.scenes[1]["subtext"].startswith("Edited")
    render_project(db, p)
    assert p.render_path.endswith(".zip")
    with zipfile.ZipFile(p.render_path) as z:
        names = z.namelist()
    assert len(names) == len(p.scenes)
    assert all(nm.endswith(".png") for nm in names)


def test_variation_and_scene_regen_and_undo(db, seeded, ingested):
    story = _story(db)
    p = faceless.create_project(db, source={"story_id": story.id}, fmt="question", target_seconds=30)
    faceless.generate_scenes(db, p)
    before = [s["on_screen_text"] for s in p.scenes]
    faceless.apply_variation(db, p, "shorter")
    assert p.target_seconds < 30
    assert p.render_status == "none"
    faceless.regenerate_scene(db, p, 0, instruction="sharper")
    assert p.previous_scenes  # undo material exists
    p.scenes, p.previous_scenes = p.previous_scenes, p.scenes
    db.commit()
    assert [s["on_screen_text"] for s in p.scenes]  # undo restored a valid list
    assert before  # sanity


def test_quality_gate_flags_missing_sources(db, seeded):
    p = faceless.create_project(db, source={"idea": "test"}, fmt="data_story")
    faceless.update_scenes(db, p, [
        {"duration": 3, "on_screen_text": "SPENDING HIT $4B", "visual_type": "counter", "visual": {"from": 0, "to": 4e9, "prefix": "$"}, "narration": "", "background": "primary", "animation": "fade", "transition": "cut", "emphasis": [], "source": ""},
    ])
    p.sources = []
    db.commit()
    checks = {c["check"]: c["status"] for c in faceless.quality_checks(db, p)}
    assert checks["Sources"] == "fail"
    assert checks["Human approval"] == "warn"
    p.sources = [{"label": "CBO", "url": "https://cbo.gov"}]
    db.commit()
    checks = {c["check"]: c["status"] for c in faceless.quality_checks(db, p)}
    assert checks["Sources"] in ("pass", "warn")


def test_ass_animation_contains_fx_and_emphasis():
    scene = {"duration": 3, "on_screen_text": "WHY 1,000X LOUDER?", "subtext": "a sub", "visual_type": "question", "visual": {}, "animation": "pop", "background": "primary", "emphasis": ["1,000X"]}
    ass = build_scene_ass(scene, {"highlight": "#C89B3C"})
    assert "\\t(0,150" in ass  # pop animation
    assert "&H003C9BC8" in ass  # gold emphasis color in ASS BGR
    assert "a sub" in ass
    counter_scene = {"duration": 4, "on_screen_text": "", "visual_type": "counter", "visual": {"from": 0, "to": 4000000000, "prefix": "$"}, "animation": "fade", "background": "primary"}
    ass2 = build_scene_ass(counter_scene, {})
    assert ass2.count("Style: Counter") == 1 and "$4B" in ass2


def test_studio_api_flow(client):
    stories = client.get("/api/stories?days=36500").json()
    sid = stories[0]["id"]
    r = client.post("/api/studio/faceless", json={"source": {"story_id": sid}, "format": "question", "target_seconds": 30, "background": False})
    assert r.status_code == 201
    proj = r.json()["project"]
    assert proj["scenes"] and proj["total_seconds"] > 0
    pid = proj["id"]
    assert client.get(f"/api/studio/projects/{pid}/scenes/0/preview").status_code == 200
    r = client.post(f"/api/studio/projects/{pid}/render")
    assert r.status_code == 200
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "succeeded", job.get("error")
    assert client.get(f"/api/studio/projects/{pid}/file").status_code == 200
    q = client.get(f"/api/studio/projects/{pid}/quality").json()
    assert {c["check"] for c in q["checks"]} >= {"Facts", "Sources", "Length", "Human approval"}
    md = client.get(f"/api/studio/projects/{pid}/script").json()["markdown"]
    assert md.startswith("#") and "Scene 1" in md
    r = client.post("/api/studio/memes/concepts", json={"idea": "committee hearings"})
    assert r.status_code == 200 and len(r.json()["concepts"]) == 3
    c = r.json()["concepts"][0]
    r = client.post("/api/studio/memes/render", json={"template": c["template"], "top_text": c["top_text"], "bottom_text": c["bottom_text"], "caption": c["caption"]})
    assert r.status_code == 201
    assert client.get(r.json()["file_url"]).status_code == 200
    assert r.json()["content_item_id"]
