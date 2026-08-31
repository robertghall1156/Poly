"""Pictures from the encyclopedia article about the subject.

Full-text picture search is the wrong tool for "give me a photo of this person". Commons
indexes every word ever written about a file, so searching a name returns anything that
mentions it — a historian who writes about a president, a church in the province a lake is
named after. Precision is terrible and there is no way to ask for "of", only "mentions".

The article about a subject, on the other hand, is curated by people: its images are of the
subject, chosen to illustrate it. So this resolves the name to a Wikipedia article first and
takes that article's pictures. Two requests, and the hit rate is a different category.

Everything returned still comes from Commons, so the licence check is identical.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..base import ImageCandidate, ImageSearchProvider, ProviderError
from .wikimedia import license_is_free

API = "https://en.wikipedia.org/w/api.php"
UA = "Poly/0.1 (personal political research tool; local-first)"

# Interface furniture, maps, flags and icons that appear on almost every article and
# illustrate nothing about the subject.
_CHROME = re.compile(
    r"commons-logo|wiki\w*-?logo|edit[-_]icon|ambox|question_book|symbol[_-]|padlock|"
    r"disambig|red_pencil|folder_hexagon|wikiquote|wikisource|wiktionary|portal|"
    r"blank\w*\.|magnify-clip|loudspeaker|speakerlink|increase2?\.|decrease2?\.|steady\.|"
    r"^flag_of|coat_of_arms|^map_of|location_map|locator|orthographic|blue_pog|red_pog",
    re.I,
)
_TAGS = re.compile(r"<[^>]+>")
MIN_EDGE = 500

# An article's images are returned in page-id order, which has nothing to do with usefulness:
# for a sitting president that puts a high-school yearbook portrait and a chart of his
# statements ahead of anything from his presidency. Rank them.
# Word boundaries matter: without them "Photographer" contains "graph", and every picture
# with a credited photographer was penalised as if it were a chart.
_WEAK = re.compile(
    r"(?<![A-Za-z])(?:yearbook|ai[-_ ]generated|graph|chart|composite|diagram|timeline|signature|autograph|"
    r"logo|book_?cover|cartoon|caricature|grave|birthplace|childhood|young|school|"
    r"family_?tree|residence|plaque|ballot|sticker|badge|screenshot|meme|word_?cloud)(?![A-Za-z])",
    re.I,
)
_STRONG = re.compile(
    r"(?<![A-Za-z])(?:official_?portrait|white_?house|oval_?office|president|inaugurat|address|speech|"
    r"press_?conference|podium|rally|signing|summit|state_?of_the_union|briefing|"
    r"cabinet|air_?force_?one|motorcade|debate)(?![A-Za-z])",
    re.I,
)
_YEAR = re.compile(r"(19|20)\d{2}")


def rank(file_name: str, *, is_lead: bool = False, credit: str = "") -> int:
    """Higher is better. A picture of the subject doing the job beats a picture of them existing.

    The credit line is read too: a school portrait is often filed under an opaque name and only
    the source ("Yearbook Library") gives it away.
    """
    name = f"{file_name} {credit}".replace(" ", "_")
    score = 50
    if is_lead:
        score += 60  # the article's lead image is the canonical portrait
    if _STRONG.search(name):
        score += 25
    if _WEAK.search(name):
        score -= 60
    year = _YEAR.findall(name)
    if year:
        score += min(20, max(0, int(f"{year[-1]}") - 2000))  # recent beats archival
    return score


def _plain(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _TAGS.sub("", str(value.get("value", ""))).strip()


class WikipediaImageProvider(ImageSearchProvider):
    """Images from the encyclopedia article that best matches the query."""

    name = "wikipedia"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def available(self) -> bool:
        try:
            return httpx.get(API, params={"action": "query", "format": "json", "meta": "siteinfo"}, timeout=6, headers={"User-Agent": UA}).status_code == 200
        except httpx.HTTPError:
            return False

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            r = httpx.get(API, params={"format": "json", **params}, timeout=self.timeout, headers={"User-Agent": UA})
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ProviderError(f"Wikipedia request failed: {e}", provider=self.name) from e

    def resolve(self, query: str) -> str | None:
        """The article a query is about. Returns its exact title, or None."""
        data = self._get({"action": "query", "list": "search", "srsearch": query, "srlimit": 3, "srnamespace": 0})
        hits = ((data.get("query") or {}).get("search") or [])
        if not hits:
            return None
        # A query like "Trump arch" should prefer an article naming both words, but the
        # encyclopedia's own ranking is a reasonable fallback.
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        for hit in hits:
            title = str(hit.get("title", ""))
            if terms and all(t in title.lower() for t in terms):
                return title
        return str(hits[0].get("title", "")) or None

    def search(self, query: str, *, limit: int = 12) -> list[ImageCandidate]:
        page = self.resolve(query)
        if not page:
            return []
        lead = ""
        try:
            head = self._get({"action": "query", "titles": page, "prop": "pageimages", "piprop": "name"})
            for entry in (head.get("query") or {}).get("pages", {}).values():
                lead = str(entry.get("pageimage") or "")
        except ProviderError:
            pass  # ranking still works without it
        data = self._get({
            "action": "query",
            "titles": page,
            "generator": "images",
            "gimlimit": 50,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": 1600,
        })
        scored: list[tuple[int, ImageCandidate]] = []
        for entry in (data.get("query") or {}).get("pages", {}).values():
            title = str(entry.get("title", ""))
            file_name = re.sub(r"^File:", "", title)
            if _CHROME.search(file_name.replace(" ", "_")):
                continue
            stem = re.sub(r"\.\w+$", "", file_name)
            info = (entry.get("imageinfo") or [{}])[0]
            mime = str(info.get("mime") or "")
            if mime and not mime.startswith("image/"):
                continue
            if "svg" in mime or file_name.lower().endswith(".svg"):
                continue  # diagrams and icons, not photographs
            meta = info.get("extmetadata") or {}
            short, terms_txt = _plain(meta.get("LicenseShortName")), _plain(meta.get("UsageTerms"))
            if not license_is_free(short, terms_txt):
                continue
            width = int(info.get("thumbwidth") or info.get("width") or 0)
            height = int(info.get("thumbheight") or info.get("height") or 0)
            if width and width < MIN_EDGE:
                continue
            scored.append((
                rank(
                    file_name,
                    is_lead=bool(lead) and file_name.replace(" ", "_") == lead.replace(" ", "_"),
                    credit=_plain(meta.get("Artist")) or _plain(meta.get("Credit")),
                ),
                ImageCandidate(
                    url=info.get("thumburl") or info.get("url", ""),
                    thumb_url=info.get("thumburl", ""),
                    # the article is the subject, so name the candidate for it — the relevance
                    # gate reads this, and "Donald Trump — <file>" is what it is a picture of
                    title=f"{page} — {stem}",
                    source_page=info.get("descriptionurl", ""),
                    license=short or terms_txt,
                    license_url=_plain(meta.get("LicenseUrl")),
                    author=_plain(meta.get("Artist")) or _plain(meta.get("Credit")) or "Wikimedia Commons",
                    width=width,
                    height=height,
                    provider=self.name,
                    mime=mime,
                ),
            ))
        scored.sort(key=lambda pair: -pair[0])
        return [c for _, c in scored[:limit]]
