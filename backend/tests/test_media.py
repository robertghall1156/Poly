"""Video indexing, transcript storage, clip discovery, caption building and 9:16 rendering."""
from __future__ import annotations

import subprocess

from poly.services import media

from .conftest import fixture_transcript


def test_probe_and_index_folder(db, test_video):
    meta = media.probe(str(test_video))
    assert 29 <= meta["duration"] <= 31
    assert meta["width"] == 1280 and meta["height"] == 720
    folder = media.add_folder(db, str(test_video.parent))
    stats = media.scan_folder(db, folder)
    assert stats["found"] == 1 and stats["added"] == 1
    v = folder.videos[0]
    assert v.filename == "sample_talk.mp4" and v.duration > 0 and v.fingerprint
    # rescanning is idempotent
    stats2 = media.scan_folder(db, folder)
    assert stats2["added"] == 0 and stats2["updated"] == 0


def test_transcript_and_clip_candidates(db, test_video):
    from poly.models import Video

    v = db.query(Video).filter(Video.filename == "sample_talk.mp4").one()
    media.save_transcript(db, v, fixture_transcript(), language="en", provider="fixture")
    assert v.transcript_status == "done" and len(v.segments) >= 4
    clips = media.discover_clips(db, v, max_candidates=5)
    assert clips, "should find at least one candidate in a 30s talk"
    for c in clips:
        assert 0 <= c.start < c.end <= v.duration + 0.5
        assert media.MIN_CLIP <= c.end - c.start <= media.MAX_CLIP
        assert c.title and c.why_it_works and c.transcript_text
        assert 0 < c.score <= 1
        assert set(c.score_breakdown) >= {"hook", "self_contained", "educational", "total"}
    # candidates do not overlap by more than the 3s tolerance
    for a in clips:
        for b in clips:
            if a is not b:
                assert a.end <= b.start + 3 or a.start >= b.end - 3


def test_build_ass_captions_have_word_highlights():
    words = [{"w": "Here's", "s": 0.0, "e": 0.3}, {"w": "why", "s": 0.3, "e": 0.5}, {"w": "CEO", "s": 0.5, "e": 0.8}, {"w": "pay.", "s": 0.8, "e": 1.2}]
    ass = media.build_ass(words, duration=2.0, intro_text="Why CEO pay rises", watermark_text="@poly")
    assert "[V4+ Styles]" in ass and "Style: Cap" in ass
    assert ass.count("Dialogue: 2,") == 4  # one event per word
    assert "\\c&H" in ass  # highlight colour override
    assert "Why CEO pay rises" in ass and "@poly" in ass


def test_render_vertical_clip_with_captions(db, test_video):
    from poly.models import Clip, Video

    v = db.query(Video).filter(Video.filename == "sample_talk.mp4").one()
    clip = Clip(video_id=v.id, start=1.0, end=6.0, title="Render test", status="selected", transcript_text="test")
    db.add(clip)
    db.commit()
    media.render_clip(db, clip, settings={"intro_text": "Test intro", "progress_bar": True, "watermark_text": "Poly", "face_tracking": False})
    assert clip.status == "rendered" and clip.render_path
    meta = media.probe(clip.render_path)
    assert (meta["width"], meta["height"]) == (1080, 1920)
    assert 4.5 <= meta["duration"] <= 5.6
    # source untouched
    assert media.probe(str(test_video))["width"] == 1280
    # thumbnail + waveform helpers work
    thumb = media.thumbnail(clip.render_path, 1.0, clip.render_path + ".jpg")
    assert subprocess.run(["ffprobe", "-v", "error", thumb], capture_output=True).returncode == 0
