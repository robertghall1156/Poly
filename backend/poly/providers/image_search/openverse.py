"""Openverse picture search — CC-licensed and public-domain images across many sources.

Used after Commons: broader catalogue, but the metadata is thinner, so the license filter
here is the API's own (`license_type=commercial,modification`) plus a local re-check.
"""
from __future__ import annotations

import httpx

from ..base import ImageCandidate, ImageSearchProvider, ProviderError

API = "https://api.openverse.org/v1/images/"
UA = "Poly/0.1 (personal political research tool; local-first)"
_ALLOWED = {"cc0", "pdm", "by", "by-sa"}  # attribution-only or freer; no NC, no ND


class OpenverseImageProvider(ImageSearchProvider):
    name = "openverse"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def available(self) -> bool:
        try:
            return httpx.get(API, params={"q": "test", "page_size": 1}, timeout=6, headers={"User-Agent": UA}).status_code < 500
        except httpx.HTTPError:
            return False

    def search(self, query: str, *, limit: int = 12) -> list[ImageCandidate]:
        params = {"q": query, "page_size": min(40, max(1, limit * 2)), "license_type": "commercial,modification", "mature": "false"}
        try:
            r = httpx.get(API, params=params, timeout=self.timeout, headers={"User-Agent": UA})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ProviderError(f"Openverse search failed: {e}", provider=self.name) from e

        out: list[ImageCandidate] = []
        for row in data.get("results", []):
            code = str(row.get("license") or "").lower()
            if code not in _ALLOWED:
                continue
            out.append(
                ImageCandidate(
                    url=row.get("url", ""),
                    thumb_url=row.get("thumbnail", ""),
                    title=str(row.get("title") or "")[:200],
                    source_page=row.get("foreign_landing_url", ""),
                    license=f"{code.upper()} {row.get('license_version', '')}".strip(),
                    license_url=row.get("license_url", ""),
                    author=str(row.get("creator") or "")[:120],
                    width=int(row.get("width") or 0),
                    height=int(row.get("height") or 0),
                    provider=self.name,
                    mime=str(row.get("filetype") or ""),
                )
            )
            if len(out) >= limit:
                break
        return out
