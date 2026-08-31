"""Open-license picture search providers.

Adding a source means adding an `ImageSearchProvider` here — nothing outside this package
names a specific service.
"""
from __future__ import annotations

from ..base import ImageSearchProvider
from .openverse import OpenverseImageProvider
from .wikimedia import WikimediaImageProvider

PROVIDERS: list[type[ImageSearchProvider]] = [WikimediaImageProvider, OpenverseImageProvider]


def all_providers() -> list[ImageSearchProvider]:
    """In preference order: Commons first (richest provenance), then Openverse (widest net)."""
    return [cls() for cls in PROVIDERS]


__all__ = ["OpenverseImageProvider", "WikimediaImageProvider", "PROVIDERS", "all_providers"]
