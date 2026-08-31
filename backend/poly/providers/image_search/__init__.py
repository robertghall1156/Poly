"""Open-license picture search providers.

Adding a source means adding an `ImageSearchProvider` here — nothing outside this package
names a specific service.
"""
from __future__ import annotations

from ..base import ImageSearchProvider
from .openverse import OpenverseImageProvider
from .wikimedia import WikimediaImageProvider
from .wikipedia import WikipediaImageProvider

PROVIDERS: list[type[ImageSearchProvider]] = [WikipediaImageProvider, WikimediaImageProvider, OpenverseImageProvider]


def all_providers() -> list[ImageSearchProvider]:
    """In precision order.

    The encyclopedia article about a subject is curated by people and its pictures are *of*
    the subject, so it goes first. Commons full-text only knows what a file's description
    mentions, and Openverse is the widest net and the loosest match — both are fallbacks.
    """
    return [cls() for cls in PROVIDERS]


__all__ = ["OpenverseImageProvider", "WikimediaImageProvider", "WikipediaImageProvider", "PROVIDERS", "all_providers"]
