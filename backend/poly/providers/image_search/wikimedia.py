"""Wikimedia Commons picture search.

Commons is the right first stop for political imagery: US federal work (White House,
Congress, agencies) is public domain, and everything else carries an explicit license in
`extmetadata`. This adapter returns *only* licenses that permit republication — anything
non-free, unknown, or non-commercial is dropped rather than guessed at.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..base import ImageCandidate, ImageSearchProvider, ProviderError

API = "https://commons.wikimedia.org/w/api.php"
UA = "Poly/0.1 (personal political research tool; local-first)"

# Licenses that allow republication with attribution. Anything not matching is rejected.
_FREE = re.compile(r"^(cc[\s-]?(0|by(-sa)?(\s|-)?\d(\.\d)?)|public domain|pd(-|\s)|no restrictions)", re.I)
_NONFREE = re.compile(r"non[- ]?commercial|\bnc\b|\bnd\b|fair use|copyright", re.I)
_TAGS = re.compile(r"<[^>]+>")


def _plain(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _TAGS.sub("", str(value.get("value", ""))).strip()


def license_is_free(short_name: str, usage_terms: str = "") -> bool:
    text = f"{short_name} {usage_terms}".strip()
    if not text or _NONFREE.search(text):
        return False
    return bool(_FREE.match(short_name.strip()) or _FREE.match(usage_terms.strip()))


class WikimediaImageProvider(ImageSearchProvider):
    name = "wikimedia"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def available(self) -> bool:
        try:
            return httpx.get(API, params={"action": "query", "format": "json", "meta": "siteinfo"}, timeout=6, headers={"User-Agent": UA}).status_code == 200
        except httpx.HTTPError:
            return False

    def search(self, query: str, *, limit: int = 12) -> list[ImageCandidate]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,  # File:
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrlimit": min(50, max(1, limit * 3)),  # over-fetch: most results fail the license filter
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": 1600,
        }
        try:
            r = httpx.get(API, params=params, timeout=self.timeout, headers={"User-Agent": UA})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ProviderError(f"Wikimedia search failed: {e}", provider=self.name) from e

        out: list[ImageCandidate] = []
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            short = _plain(meta.get("LicenseShortName"))
            terms = _plain(meta.get("UsageTerms"))
            if not license_is_free(short, terms):
                continue
            mime = str(info.get("mime") or "")
            if mime and not mime.startswith("image/"):
                continue
            out.append(
                ImageCandidate(
                    url=info.get("thumburl") or info.get("url", ""),
                    thumb_url=info.get("thumburl", ""),
                    title=re.sub(r"^File:|\.\w+$", "", str(page.get("title", ""))).strip(),
                    source_page=info.get("descriptionurl", ""),
                    license=short or terms,
                    license_url=_plain(meta.get("LicenseUrl")),
                    author=_plain(meta.get("Artist")) or _plain(meta.get("Credit")),
                    width=int(info.get("thumbwidth") or info.get("width") or 0),
                    height=int(info.get("thumbheight") or info.get("height") or 0),
                    provider=self.name,
                    mime=mime,
                )
            )
            if len(out) >= limit:
                break
        return out
