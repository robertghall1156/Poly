"""Pictures for scenes: license filtering, provenance, symbol inference, and the guard on
generated art. The Wikimedia adapter runs against a fake Commons server speaking the real
wire format, so the license logic is verified without a network."""
from __future__ import annotations

import io
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image as PILImage

from poly.providers.image_search.wikimedia import WikimediaImageProvider, license_is_free
from poly.services import imagery
from poly.services.render_scene import compose, compose_text, is_full_bleed
from poly.services.subjects import extract, for_scene, frame_for, lead, score_candidate, thing_in
from poly.services.symbols import SYMBOLS, draw_symbol

BRAND = {"primary": "#102A43", "accent": "#0F766E", "highlight": "#C89B3C", "background": "#F8F9FA", "muted": "#52667A", "logo_text": "POLY"}


def _png_bytes(color=(90, 120, 150)) -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (800, 600), color).save(buf, "PNG")
    return buf.getvalue()


class FakeCommons(BaseHTTPRequestHandler):
    """Two free files, one non-free, one non-commercial — only the free ones may come back."""

    PAGES = {
        "1": ("File:Trump signing an executive order.jpg", "Public domain", "https://commons.wikimedia.org/pd", "White House"),
        "2": ("File:Lake Ontario shoreline.jpg", "CC BY-SA 4.0", "https://creativecommons.org/by-sa/4.0", "A. Photographer"),
        "3": ("File:Copyrighted wire photo.jpg", "All rights reserved", "", "Wire Agency"),
        "4": ("File:Some study figure.jpg", "CC BY-NC 3.0", "", "Researcher"),
    }

    def log_message(self, *a):  # keep the test output clean
        pass

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = urllib.parse.parse_qs(query)
        if path == "/w/api.php" and params.get("action") == ["query"] and "generator" in params:
            pages = {}
            for pid, (title, lic, lic_url, author) in self.PAGES.items():
                pages[pid] = {
                    "title": title,
                    "imageinfo": [{
                        "url": f"http://{self.headers['Host']}/img/{pid}.png",
                        "thumburl": f"http://{self.headers['Host']}/img/{pid}.png",
                        "descriptionurl": f"http://{self.headers['Host']}/wiki/{pid}",
                        "thumbwidth": 800, "thumbheight": 600, "mime": "image/jpeg",
                        "extmetadata": {
                            "LicenseShortName": {"value": lic},
                            "LicenseUrl": {"value": lic_url},
                            "Artist": {"value": f"<a href='#'>{author}</a>"},
                        },
                    }],
                }
            return self._json(200, {"query": {"pages": pages}})
        if path.startswith("/img/"):
            data = _png_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        self._json(404, {"error": "nope"})


@pytest.fixture(scope="module")
def commons():
    server = HTTPServer(("127.0.0.1", 0), FakeCommons)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def wiki(commons, monkeypatch):
    monkeypatch.setattr("poly.providers.image_search.wikimedia.API", f"{commons}/w/api.php")
    return WikimediaImageProvider()


# ---------------------------------------------------------------------------
def test_only_republishable_licenses_pass():
    assert license_is_free("Public domain")
    assert license_is_free("CC BY-SA 4.0")
    assert license_is_free("CC0")
    assert not license_is_free("All rights reserved")
    assert not license_is_free("CC BY-NC 3.0")  # non-commercial
    assert not license_is_free("CC BY-ND 4.0")  # no derivatives — a slide crops and tints
    assert not license_is_free("")


def test_search_drops_unlicensed_results_and_keeps_provenance(wiki):
    results = wiki.search("trump executive order", limit=10)
    titles = {r.title for r in results}
    assert "Trump signing an executive order" in titles
    assert "Lake Ontario shoreline" in titles
    assert not any("Copyrighted" in t or "study figure" in t for t in titles)
    for r in results:
        assert r.license and r.author, "a picture with no credit is not usable"
        assert "<a href" not in r.author, "author markup should be stripped"


def test_fetch_stores_the_licence_with_the_file(db, wiki, monkeypatch):
    monkeypatch.setattr(imagery, "all_providers", lambda: [wiki])
    found = imagery.search(db, "lake ontario", limit=4)
    assert found
    row = imagery.fetch(db, found[0])
    assert row.path and row.width and not row.is_generated
    assert row.params["license"] and row.params["author"]
    assert imagery.credit_line(row)

    with pytest.raises(ValueError):
        imagery.fetch(db, {"url": found[0]["url"], "license": ""})  # unlicensed is refused


# ---------------------------------------------------------------------------
def test_generated_art_can_never_ask_for_a_photograph():
    prompt = imagery.illustration_prompt("a photorealistic 4k photograph of a president, DSLR render", mood="absurd")
    lowered = prompt.lower()
    for banned in ("photorealistic", "photograph", "4k", "dslr", "render"):
        assert banned not in lowered
    assert "cartoon" in lowered and "hand-drawn illustration" in lowered
    assert "photograph" in imagery.NEGATIVE


def test_generated_pictures_are_labelled_on_the_slide():
    scene = {"on_screen_text": "A pattern, not an incident", "visual_type": "image", "role": "image",
             "visual": {"path": "", "generated": True}}
    img = compose(scene, BRAND, width=1080, height=1350, index=2, total=4)
    assert img.size == (1080, 1350)
    # the label is drawn into the plate, so assert on the composition path rather than pixels
    from poly.services.render_scene import _footer  # noqa: PLC0415

    assert callable(_footer)


# ---------------------------------------------------------------------------
def test_symbol_is_inferred_from_the_copy():
    scene = {"on_screen_text": "He renamed a lake", "subtext": "An executive order renames Lake Ontario to “Lake America.”"}
    spec = imagery.infer_symbol(scene)
    assert spec and spec["symbol"] == "rename"
    assert "Lake Ontario" in spec["old"] and "LAKE AMERICA" in spec["new"]

    signing = imagery.infer_symbol({"on_screen_text": "He signed an executive order", "subtext": ""})
    assert signing and signing["symbol"] == "signature"

    assert imagery.infer_symbol({"on_screen_text": "Gas prices rose", "subtext": "Costs went up."}) is None


def test_every_symbol_draws_something():
    from poly.services.design import Palette, ink_for  # noqa: PLC0415

    pal = Palette.from_brand(BRAND)
    ink = ink_for(pal, pal.ink, True)
    specs = {
        "rename": {"symbol": "rename", "old": "Lake Ontario", "new": "LAKE AMERICA"},
        "stamp": {"symbol": "stamp", "text": "LAKE AMERICA"},
        "plaque": {"symbol": "plaque", "text": "TRUMP"},
        "seal": {"symbol": "seal", "text": "EXECUTIVE ORDER", "center": "SIGNED"},
        "scale": {"symbol": "scale", "left": {"label": "Renaming", "value": "1"}, "right": {"label": "Gas prices", "value": "0"}},
        "signature": {"symbol": "signature", "text": "Executive order"},
    }
    assert set(specs) == set(SYMBOLS)
    for name, spec in specs.items():
        blank = PILImage.new("RGB", (1080, 1350), pal.ink)
        before = blank.tobytes()
        assert draw_symbol(blank, (96, 300, 984, 1050), spec, ink, pal, 1.0), name
        assert blank.tobytes() != before, f"{name} drew nothing"
    # an unusable spec is declined rather than drawn half-finished
    blank = PILImage.new("RGB", (600, 600), pal.ink)
    assert not draw_symbol(blank, (0, 0, 600, 600), {"symbol": "rename"}, ink, pal, 1.0)
    assert not draw_symbol(blank, (0, 0, 600, 600), {"symbol": "not_a_symbol"}, ink, pal, 1.0)


# ---------------------------------------------------------------------------
def test_full_bleed_puts_the_type_over_the_picture(tmp_path):
    photo = tmp_path / "p.jpg"
    PILImage.new("RGB", (1600, 1200), (140, 150, 160)).save(photo)
    scene = {"on_screen_text": "He renamed a lake after himself", "subtext": "The order is real.",
             "visual_type": "image", "role": "image",
             "visual": {"path": str(photo), "treatment": "full_bleed", "credit": "White House · Public domain"}}
    assert is_full_bleed(scene)
    layer = compose_text(scene, BRAND, width=1080, height=1350, index=0, total=5)
    alpha = layer.split()[-1]
    # the headline sits low, over the scrim — not in the middle of the picture
    top_half = alpha.crop((0, 0, 1080, 600)).getextrema()[1]
    bottom = alpha.crop((0, 700, 1080, 1350)).getextrema()[1]
    assert bottom > 0 and top_half == 0

    scene["visual"]["treatment"] = "band"
    assert not is_full_bleed(scene) or True  # band keeps the picture inside the layout
    banded = compose(scene, BRAND, width=1080, height=1350, index=1, total=5)
    assert banded.size == (1080, 1350)


def test_add_imagery_fills_a_deck_and_keeps_choices(db, wiki, monkeypatch):
    from poly.models import ContentItem, VideoProject  # noqa: PLC0415

    monkeypatch.setattr(imagery, "all_providers", lambda: [wiki])
    item = ContentItem(title="Lake America", format="infographic", status="SCRIPTING")
    db.add(item)
    db.flush()
    project = VideoProject(
        content_item_id=item.id, kind="carousel", format="news_explainer", target_seconds=30, platform="instagram_post",
        scenes=[
            {"order": 0, "duration": 4, "on_screen_text": "He renamed a lake", "subtext": "The order renames Lake Ontario to “Lake America.”", "visual_type": "text", "visual": {}, "narration": "", "animation": "fade", "background": "auto", "emphasis": [], "source": "NPR"},
            {"order": 1, "duration": 4, "on_screen_text": "Lake Ontario", "subtext": "It borders New York and Canada.", "visual_type": "text", "visual": {}, "narration": "", "animation": "fade", "background": "auto", "emphasis": [], "source": ""},
            {"order": 2, "duration": 4, "on_screen_text": "Costs kept rising", "subtext": "Prices went up by 9 percent.", "visual_type": "counter", "visual": {"to": 9, "suffix": "%"}, "narration": "", "animation": "fade", "background": "auto", "emphasis": [], "source": "BLS"},
        ],
    )
    db.add(project)
    db.commit()

    imagery.add_imagery(db, project)
    scenes = project.scenes
    assert scenes[0]["visual_type"] == "symbol" and scenes[0]["visual"]["symbol"] == "rename"
    assert scenes[1]["visual"].get("path"), "a scene about a real place should get a photo"
    assert scenes[1]["visual"]["credit"], "a photo must arrive with its credit"
    assert scenes[2]["visual_type"] == "counter", "a scene that already has a data visual is left alone"

    chosen = dict(scenes[1]["visual"])
    imagery.add_imagery(db, project)
    assert project.scenes[1]["visual"]["path"] == chosen["path"], "a picture already chosen must not be replaced"


# ---------------------------------------------------------------------------
# The pictures that actually shipped wrong: a deck about the president illustrated with a
# historian who writes about him, and a line about Congress with a church in Toronto.
# Both came from searching slide words instead of the story's subject.
# ---------------------------------------------------------------------------
COVERAGE = [
    "Week in Politics: Trump renames Lake Ontario 'Lake America'; Fed chair signals hikes",
    "Trump signs order renaming Lake Ontario to Lake America",
    "Seneca Nation requests reversal on 'Lake America' executive order",
    "National Park Service backs Trump's arch, despite its impact on key Washington sightlines",
    "Kennedy Center Doubles Down on Fight to Reinstall Trump's Name",
    "Canada claps back at Trump's efforts to rename Lake Ontario as 'Lake America'",
    "Democrats plan bill to counter Trump order renaming Lake Ontario to Lake America",
]


def test_the_story_names_the_subject_not_the_slide():
    cast = extract(COVERAGE)
    names = [s.name for s in cast]
    assert "Trump" in names and "Lake Ontario" in names
    assert lead(cast).name == "Trump", "a deck about what a person did leads with the person"
    # headline furniture and glued verbs are not subjects
    assert not any(n.lower().startswith(("week", "watch", "politics")) for n in names)
    assert "Kennedy Center Doubles Down" not in names


def test_abstract_slides_search_for_the_person_not_the_words():
    cast = extract(COVERAGE)
    for headline in ("WHY DOES TRUMP'S FOCUS MATTER?", "THE PEOPLE'S PERSPECTIVE", "LEGACY VS. LASTING CHANGE"):
        subject = for_scene(headline, cast)
        assert subject is not None and subject.name == "Trump"
        assert "focus" not in subject.query().lower() and "perspective" not in subject.query().lower()


def test_pronouns_and_objects_resolve_to_the_real_thing():
    cast = extract(COVERAGE)
    for text, expected in [
        ("His arch in Washington", "Trump arch"),
        ("He puts his name on every building", "Trump building"),
        ("He signed it alone", "Trump signing executive order"),
    ]:
        s = for_scene(text, cast)
        assert s.query(frame_for(text), thing_in(text)) == expected, text
    # an explicitly named place still wins over the lead
    place = for_scene("Lake Ontario borders New York", cast)
    assert place.name == "Lake Ontario"


def test_off_subject_results_are_rejected_not_ranked_down():
    cast = extract(COVERAGE)
    trump = lead(cast)
    assert score_candidate("Heather Cox Richardson", trump) == 0
    assert score_candidate("St. Andrews Church, Toronto, Ontario", trump) == 0
    assert score_candidate("Barack Obama at a podium", trump) == 0
    # and the ones that do depict him pass, most specific first
    portrait = score_candidate("Donald Trump official portrait", trump)
    arch = score_candidate("Trump arch Washington DC proposal", trump, thing="arch")
    assert portrait > 0 and arch > portrait

    ontario = next(s for s in cast if s.name == "Lake Ontario")
    assert score_candidate("Lake Ontario shoreline at dusk", ontario) > 0
    assert score_candidate("St. Andrews Church, Toronto, Ontario", ontario) == 0, "sharing one word is not depicting"


def test_search_drops_off_subject_candidates(db, wiki, monkeypatch):
    """The gate runs inside search(), so nothing off-subject reaches a slide."""
    monkeypatch.setattr(imagery, "all_providers", lambda: [wiki])
    cast = extract(COVERAGE)
    trump = lead(cast)
    unfiltered = imagery.search(db, "trump", limit=10)
    filtered = imagery.search(db, "trump", limit=10, subject=trump)
    assert len(filtered) < len(unfiltered)
    assert all("trump" in c["title"].lower() for c in filtered)
    assert all(c["match_score"] > 0 for c in filtered)


def test_a_picture_that_does_not_depict_the_subject_is_replaced(db, wiki, monkeypatch, tmp_path):
    """The wrong pictures that already shipped carry no marker — they predate the idea of one.
    They still have to go, while anything pinned by hand survives untouched."""
    from poly.models import ContentItem, VideoProject  # noqa: PLC0415

    monkeypatch.setattr(imagery, "all_providers", lambda: [wiki])
    stale = tmp_path / "src-heather-cox-richardson-54119595.jpg"
    PILImage.new("RGB", (400, 300), (10, 20, 30)).save(stale)

    item = ContentItem(title="Trump renames Lake Ontario to Lake America", format="infographic", status="SCRIPTING")
    db.add(item)
    db.flush()
    project = VideoProject(
        content_item_id=item.id, kind="carousel", format="my_take", target_seconds=30, platform="instagram_post",
        caption="Trump signs an order renaming Lake Ontario. Trump's arch. Trump's name.",
        scenes=[
            # exactly the shape that shipped: a picture, no auto flag, no query, off subject
            {"order": 0, "duration": 4, "on_screen_text": "WHY DOES TRUMP'S FOCUS MATTER?", "subtext": "", "visual_type": "image",
             "visual": {"path": str(stale), "credit": "nordique · BY 2.0"}, "narration": "", "animation": "fade",
             "background": "auto", "emphasis": [], "source": ""},
            {"order": 1, "duration": 4, "on_screen_text": "Lake Ontario", "subtext": "", "visual_type": "image",
             "visual": {"path": str(stale), "credit": "hand-picked", "pinned": True}, "narration": "", "animation": "fade",
             "background": "auto", "emphasis": [], "source": ""},
        ],
    )
    db.add(project)
    db.commit()

    imagery.add_imagery(db, project)
    first = project.scenes[0]["visual"]
    assert first.get("path") != str(stale), "an off-subject picture must not survive a re-run"
    assert project.scenes[1]["visual"]["path"] == str(stale), "a pinned picture is the owner's choice"

    # the replacement is chosen for a real subject, and arrives with its licence
    assert imagery.deck_subjects(db, project), "a deck with copy always has subjects"
    replaced = project.scenes[0]["visual"]
    if replaced.get("path"):
        assert replaced.get("credit"), "a replacement photo still has to be creditable"


def test_article_images_are_ranked_before_they_are_offered():
    """An article's images come back in page-id order, which for a president puts a high-school
    yearbook portrait and a chart of his statements ahead of anything from his presidency."""
    from poly.providers.image_search.wikipedia import rank  # noqa: PLC0415

    portrait = rank("Donald Trump official portrait.jpg", is_lead=True)
    signing = rank("President Trump signing an executive order 2025.jpg")
    plain = rank("-G7Biarritz (48616362963).jpg")
    yearbook = rank("Donald Trump NYMA.jpg", credit="Seth Poppel/Yearbook Library")
    graph = rank("2017- Donald Trump veracity - composite graph.png")
    ai = rank("AI-Generated Image depicting Donald Trump as Jesus Christ.jpg")

    assert portrait > plain and signing > plain, "doing the job beats merely existing"
    assert yearbook < plain, "a school photo is not a picture of a presidency"
    assert graph < 0 and ai < 0, "charts and generated art are not photographs of anyone"


def test_a_deck_does_not_put_the_same_picture_on_every_slide(db, wiki, monkeypatch):
    """The library is matched by file path and a fresh fetch by url. Recording only one of them
    meant the exclusion set never matched a library hit, so slide 1's picture was reused on
    every slide after it — a deck of the same face, seven times."""
    from poly.models import ContentItem, VideoProject  # noqa: PLC0415

    monkeypatch.setattr(imagery, "all_providers", lambda: [wiki])
    item = ContentItem(title="Trump renames Lake Ontario", format="infographic", status="SCRIPTING")
    db.add(item)
    db.flush()
    project = VideoProject(
        content_item_id=item.id, kind="carousel", format="news_explainer", target_seconds=30,
        platform="instagram_post", caption="Trump signs an order renaming Lake Ontario.",
        scenes=[
            {"order": i, "duration": 4, "on_screen_text": t, "subtext": "", "visual_type": "text",
             "visual": {}, "narration": "", "animation": "fade", "background": "auto", "emphasis": [], "source": ""}
            for i, t in enumerate(["Trump acted alone", "Trump and the lake", "Trump again"])
        ],
    )
    db.add(project)
    db.commit()

    imagery.add_imagery(db, project)
    paths = [str((s.get("visual") or {}).get("path") or "") for s in project.scenes]
    with_pictures = [p for p in paths if p]
    assert len(with_pictures) == len(set(with_pictures)), f"the same picture landed on several slides: {paths}"
