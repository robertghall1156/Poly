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
from poly.services.render_scene import compose, compose_text
from poly.services.render_video import build_counter_ass, render_project, render_scene_preview, scene_filter


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
    assert checks["Approved by you"] == "warn"
    p.sources = [{"label": "CBO", "url": "https://cbo.gov"}]
    db.commit()
    checks = {c["check"]: c["status"] for c in faceless.quality_checks(db, p)}
    assert checks["Sources"] in ("pass", "warn")


BRAND = {"primary": "#102A43", "accent": "#0F766E", "highlight": "#C89B3C", "background": "#F8F9FA", "muted": "#52667A", "logo_text": "POLY"}


def test_text_never_bleeds_outside_the_safe_margins():
    """The failure that made early slides unusable: a long line drawn unwrapped, running
    off both edges of the frame. Nothing may be drawn in the outer margins."""
    scene = {
        "duration": 3,
        "on_screen_text": "Michigan Senate nominee apologized for comments about a synagogue attack",
        "subtext": "A long supporting sentence that would certainly overflow the frame if it were drawn on a single unwrapped line.",
        "visual_type": "text",
        "visual": {},
        "background": "background",
    }
    for w, h in ((1080, 1920), (1080, 1350)):
        layer = compose_text(scene, BRAND, width=w, height=h, index=1, total=4)
        alpha = layer.split()[-1]
        margin = int(w * 0.089) - 24  # the design column, less a hairline of tolerance
        left = alpha.crop((0, 0, max(1, margin), h)).getextrema()[1]
        right = alpha.crop((w - max(1, margin), 0, w, h)).getextrema()[1]
        assert left == 0 and right == 0, f"text bled into the margin at {w}x{h}"


def test_scenes_are_composed_not_flat_text():
    """A designed frame has a graded surface and brand furniture — not one flat fill."""
    scene = {"duration": 3, "on_screen_text": "Two economies, one country", "subtext": "The gap is a policy choice.", "visual_type": "text", "visual": {}, "background": "primary"}
    img = compose(scene, BRAND, width=1080, height=1920, index=0, total=5)
    assert img.size == (1080, 1920)
    assert len(img.convert("RGB").getcolors(maxcolors=1 << 20) or []) > 500  # gradient + grain, not a flat plate

    # consecutive slides in a deck must not all look identical
    deck = [dict(scene, on_screen_text=f"Point {i}") for i in range(4)]
    plates = [compose(s, BRAND, width=1080, height=1350, index=i, total=4).resize((32, 40)).tobytes() for i, s in enumerate(deck)]
    assert len(set(plates)) == len(plates)


def test_emphasis_paints_the_highlight_color():
    scene = {"duration": 3, "on_screen_text": "WHY 1,000X LOUDER?", "subtext": "a sub", "visual_type": "question", "visual": {}, "background": "primary", "emphasis": ["1,000X"]}
    layer = compose_text(scene, BRAND, width=1080, height=1920, index=1, total=3).convert("RGB")
    colors = {c for _, c in (layer.getcolors(maxcolors=1 << 20) or [])}
    assert any(r > 150 and 110 < g < 210 and b < 130 for r, g, b in colors), "no gold emphasis pixels"


def test_counter_animation_counts_up_where_the_still_draws_it():
    scene = {"duration": 4, "on_screen_text": "What one number tells you", "visual_type": "counter", "visual": {"from": 0, "to": 4000000000, "prefix": "$"}, "animation": "fade", "background": "primary"}
    ass = build_counter_ass(scene, BRAND, width=1080, height=1920, index=1, total=3)
    assert ass and ass.count("Style: Counter") == 1
    assert "$4B" in ass and "$0" in ass  # ends on the real number, starts from zero
    assert "\\pos(540," in ass  # centred on the frame, where _stat draws it
    assert build_counter_ass({"on_screen_text": "no counter here", "visual_type": "text"}, BRAND) is None


def test_scene_filter_animates_the_text_layer():
    f = scene_filter({"animation": "slide_up", "transition": "fade"}, width=1080, height=1920, frames=90, duration=3.0)
    assert "[bg][tx]overlay" in f and "alpha=1" in f and "fade=t=out" in f
    assert scene_filter({"animation": "none"}, width=1080, height=1920, frames=60, duration=2.0).count("alpha=1") == 0


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
    # the gate speaks plain English — nobody reads "Asset provenance" and thinks faster
    assert {c["check"] for c in q["checks"]} >= {"Checked", "Sources", "Length", "Approved by you"}
    md = client.get(f"/api/studio/projects/{pid}/script").json()["markdown"]
    assert md.startswith("#") and "Scene 1" in md
    r = client.post("/api/studio/memes/concepts", json={"idea": "committee hearings"})
    assert r.status_code == 200 and len(r.json()["concepts"]) == 3
    c = r.json()["concepts"][0]
    r = client.post("/api/studio/memes/render", json={"template": c["template"], "top_text": c["top_text"], "bottom_text": c["bottom_text"], "caption": c["caption"]})
    assert r.status_code == 201
    assert client.get(r.json()["file_url"]).status_code == 200
    assert r.json()["content_item_id"]
