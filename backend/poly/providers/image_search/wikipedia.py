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
        data = self._get({
            "action": "query",
            "titles": page,
            "generator": "images",
            "gimlimit": 50,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": 1600,
        })
        out: list[ImageCandidate] = []
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
            out.append(
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
                )
            )
            if len(out) >= limit:
                break
        return out
