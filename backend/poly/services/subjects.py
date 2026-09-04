"""Who and what a story is physically about.

A slide headline is an abstraction — "WHY DOES TRUMP'S FOCUS MATTER?" — and there is no
photograph of an abstraction. Searching those words returns whatever a picture archive's
full-text index happens to associate with them, which is how a deck about a president ends
up illustrated with a historian who once wrote about him, and a line about Congress ends up
with a church in Toronto.

So the subject of a picture is taken from the *story*, not from the slide: the named people,
places, buildings and objects that actually appear in the reporting, ranked by how much of the
coverage they carry. A search then runs against a real name, and a candidate whose title does
not contain that name is rejected rather than accepted as a near-miss.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Headline furniture, section names and wire-service noise. These are capitalised in the
# sources but name nothing you could photograph.
NOISE = {
    "watch", "listen", "read", "exclusive", "analysis", "opinion", "editorial", "live", "updates",
    "breaking", "scoop", "week", "politics", "news", "topics", "report", "video", "photos",
    "first", "new", "why", "how", "what", "when", "where", "who", "the", "a", "an", "this", "that",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "today", "tomorrow", "yesterday",
    "americans", "american", "people", "voters", "critics", "supporters", "sources", "officials",
    "president", "senator", "congressman", "governor", "mr", "ms", "mrs", "dr",
    # "Source" heads the attribution line the writer appends to almost every slide. Left in,
    # it reads as a capitalised name and searches an archive for the word — which is how two
    # slides about campaign spending were illustrated with a Seychelles beach and a spring.
    "source", "credit", "via", "photo", "image", "courtesy", "getty",
}

# The trailing attribution a slide carries ("… risking a Democratic edge. Source: Washington
# Post"). It is furniture, not content: cut it before looking for what the slide is about.
ATTRIBUTION = re.compile(r"\s*(?:source|credit|photo|via)\s*[::]\s*[^.]*\.?\s*$", re.I)


def strip_attribution(text: str) -> str:
    """Drop a trailing 'Source: X' so it cannot be mistaken for the slide's subject."""
    return ATTRIBUTION.sub("", text or "").strip()
# Bylines and outlets. They appear in almost every story and are never what it is about —
# without this, "WHAT DID SOURCES SAY?" searches for a newspaper's head office.
PUBLICATIONS = {
    "reuters", "axios", "npr", "pbs", "wsj", "politico", "nbc", "cbs", "abc", "cnn", "bbc",
    "bloomberg", "guardian", "newsweek", "vox", "semafor", "punchbowl", "msnbc", "fox",
    "washington post", "new york times", "wall street journal", "the hill", "associated press",
    "los angeles times", "usa today", "financial times", "the atlantic", "new yorker",
    "pbs news hour", "npr topics", "fox news", "news hour", "hill", "post", "times", "journal", "nyt", "wapo", "ap", "afp",
}
# Words that make a phrase a category rather than a thing.
_ABSTRACT = {
    "focus", "legacy", "leadership", "priorities", "perspective", "context", "implication",
    "strategy", "argument", "view", "impact", "role", "matter", "matters", "change", "trust",
    "power", "policy", "policies", "future", "past", "history", "economy", "war", "prices",
}

_PLACE_WORD = re.compile(r"^(lake|mount|mt|river|fort|port|cape|bay|gulf|city|county|state|island|sea|ocean)\b", re.I)
_RUN = re.compile(r"\b([A-Z][\w’'.\-]*(?:\s+(?:of|the|de|van|von)\s+[A-Z][\w’'.\-]*|\s+[A-Z][\w’'.\-]*){0,3})")
_POSSESSIVE = re.compile(r"[’']s\b")
# Headlines capitalise verbs, so a run of capitals often glues an actor to its action
# ("Kennedy Center Doubles Down"). Cut the run at the verb.
_HEADLINE_VERBS = {
    "doubles", "backs", "signs", "claps", "plans", "moves", "renames", "requests", "says", "said",
    "wants", "seeks", "calls", "urges", "files", "sues", "wins", "loses", "faces", "hits", "sets",
    "takes", "gives", "holds", "keeps", "adds", "cuts", "pushes", "blocks", "rejects", "defends",
    "reinstall", "counter", "fight", "reverses", "orders", "warns", "slams", "responds",
}

# A picture of a person is usually wanted in one of a few framings. The frame is appended to
# the name so the archive returns something usable rather than a passport crop.
# Only actions make a usable search. "Trump building sign" finds nothing; the concrete noun
# from the scene (thing_in) is what turns a name into a specific picture.
FRAMES = {
    "portrait": "",
    "building": "",
    "crowd": "",
    "speaking": "speaking",
    "signing": "signing executive order",
}


def _has_word(haystack: str, needle: str) -> bool:
    """Substring matching turns 'Americans' into a mention of 'Lake America'."""
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


@dataclass
class Subject:
    name: str
    weight: int = 1
    tokens: list[str] = field(default_factory=list)
    # True when the deck's own words name this. Coverage is for ranking, not for deciding what
    # a slide is about — otherwise a paper quoted in one headline becomes a slide's subject.
    from_deck: bool = False

    def query(self, frame: str = "portrait", thing: str = "") -> str:
        """The search that will actually be run. A concrete noun from the scene beats a
        generic frame — "Trump arch" finds the arch, "Trump building sign" finds nothing."""
        extra = thing or FRAMES.get(frame, "")
        return f"{self.name} {extra}".strip()

    @property
    def words(self) -> list[str]:
        return [w for w in re.split(r"\W+", self.name.lower()) if len(w) > 2 and w not in ("the", "and", "for", "of")]

    def mentioned_in(self, text: str) -> int:
        """Length of the longest part of this name that appears — used to pick which subject
        a scene is about when several share a word ("Lake Ontario" vs "Lake America")."""
        low = (text or "").lower()
        return max((len(t) for t in self.tokens if _has_word(low, t)), default=0)

    def named_by(self, text: str) -> bool:
        """Strict: every significant word of the name is present, as a word. A search result
        must clear this — sharing one word ("Ontario") is how a church in Toronto illustrates
        Congress, and matching inside a word is how "Americans" becomes "Lake America"."""
        low = (text or "").lower()
        return bool(self.words) and all(_has_word(low, w) for w in self.words)

    @property
    def is_place(self) -> bool:
        return bool(_PLACE_WORD.match(self.name))


def _clean(phrase: str) -> str:
    # A possessive ends the name: "Trump's Focus" is Trump and a thing he has, not a person
    # called Trump Focus — which then gets thrown out as an abstraction, taking the real
    # subject of the deck with it.
    possessive = _POSSESSIVE.search(phrase)
    if possessive:
        phrase = phrase[: possessive.start()]
    phrase = phrase.strip(" .,:;—-'’\"“”")
    words = phrase.split()
    while words and words[0].lower() in ("a", "an", "the"):
        words = words[1:]
    cut = next((i for i, w in enumerate(words) if w.lower().strip(".,") in _HEADLINE_VERBS), None)
    if cut is not None:
        words = words[:cut]
    return re.sub(r"\s+", " ", " ".join(words)).strip(" .,:;—-'’\"“”")


def _is_shouting(chunk: str) -> bool:
    """ALL-CAPS carries no capitalisation signal — every word reads as a proper noun.

    Slide headlines are set in caps, so without this a headline becomes a subject and the
    picture search runs against "WHAT DOES THIS REVEAL" instead of the person it is about.
    """
    letters = [c for c in chunk if c.isalpha()]
    return len(letters) > 6 and not any(c.islower() for c in letters)


_CONTRACTION = re.compile(r"^\w{1,4}[’'](ll|ve|re|d|m|s|t)$", re.I)
# "APOLogy" — a model half-uppercasing a word. It is a typo, not a name.
_MANGLED = re.compile(r"^[A-Z]{2,}[a-z]")


def _is_nameable(phrase: str) -> bool:
    words = phrase.split()
    if not words:
        return False
    if phrase.lower() in PUBLICATIONS:
        return False
    low = [w.lower().strip(".,") for w in words]
    if any(_CONTRACTION.match(w) for w in words):
        return False  # "I'll", "We've" — capitalised, but not names
    if any(_MANGLED.match(w) for w in words):
        return False
    if all(w in NOISE for w in low):
        return False
    if len(words) == 1 and (low[0] in NOISE or low[0] in _ABSTRACT or len(low[0]) < 3):
        return False
    # a phrase whose head noun is an abstraction names an idea, not a thing
    return low[-1] not in _ABSTRACT


def extract(texts: list[str], *, limit: int = 8) -> list[Subject]:
    """Rank the named things across a story's reporting. Longer names absorb their own
    surnames, so 'Donald Trump' and 'Trump' count once and search as the full name."""
    # Document frequency, not raw count: a name in seven of eight reports is the story's
    # subject; a name repeated three times in one report is that report's phrasing.
    counts: Counter[str] = Counter()
    for text in texts:
        seen_here = {
            _clean(m.group(1))
            for chunk in re.split(r"[.;:!?\n]", text or "")
            if not _is_shouting(chunk)
            for m in _RUN.finditer(chunk)
        }
        for phrase in seen_here:
            if _is_nameable(phrase):
                counts[phrase] += 1

    merged: dict[str, Subject] = {}
    for phrase, n in counts.most_common(60):
        key = phrase.lower()
        parent = next(
            (s for k, s in merged.items() if key != k and (f" {key}" in f" {k}" or f"{key} " in f"{k} ")),
            None,
        )
        if parent is not None:  # "Trump" folds into "Donald Trump"
            parent.weight += n
            if key not in parent.tokens:
                parent.tokens.append(key)
            continue
        subject = Subject(name=phrase, weight=n, tokens=[key])
        # the distinctive word of a name is what a result must contain
        for w in phrase.split():
            wl = w.lower().strip(".,")
            if len(wl) > 3 and wl not in NOISE and wl not in ("of", "the", "and", "for"):
                if wl not in subject.tokens:
                    subject.tokens.append(wl)
        merged[key] = subject

    # A one-off phrase that contains an established name is that name wearing a headline
    # ("Reinstall Trump Name" is Trump). Recurring distinct names are left alone.
    established = sorted(merged.values(), key=lambda s: -s.weight)
    for subject in list(merged.values()):
        if subject.weight > 1:
            continue
        words = set(subject.name.lower().replace(",", " ").split())
        host = next((e for e in established if e is not subject and e.weight >= 3 and e.tokens[0] in words), None)
        if host is not None:
            host.weight += subject.weight
            merged.pop(subject.name.lower(), None)

    ranked = sorted(merged.values(), key=lambda s: (-s.weight, -len(s.name)))
    return ranked[:limit]


def lead(cast: list[Subject]) -> Subject | None:
    """The story's principal subject. On a tie a person beats a place: a deck about an act
    wants whoever did it, not the scenery it was done to."""
    if not cast:
        return None
    return max(cast, key=lambda s: (s.weight, not s.is_place, len(s.name)))


def for_scene(scene_text: str, cast: list[Subject]) -> Subject | None:
    """The subject this scene is about: whichever name it states most fully, else the lead."""
    if not cast:
        return None
    principal = lead(cast)
    if _PRONOUN.search(scene_text or "") and principal is not None and not principal.is_place:
        return principal
    hits = [(s, m) for s, m in ((s, s.mentioned_in(scene_text)) for s in cast) if m]
    # Prefer names the deck itself uses. A subject that exists only because it appeared in a
    # related headline is background, not what this slide is about.
    owned = [pair for pair in hits if pair[0].from_deck]
    hits = owned or hits
    # A name mentioned once in passing is not what the slide is about. Requiring a quarter of
    # the lead's weight keeps genuine secondary subjects and drops the incidental ones — the
    # paper that reported it, the adjective in front of a city.
    if principal is not None:
        strong = [pair for pair in hits if pair[0].weight * 4 >= principal.weight]
        hits = strong or []
    if hits:
        return max(hits, key=lambda pair: (pair[1], pair[0].weight))[0]
    return principal


# "His arch", "he signed" — the deck's lead is who that refers to. Real coreference is out of
# scope, but a pronoun with no other person named almost always means the principal subject.
_PRONOUN = re.compile(r"\b(he|him|his|she|her|hers|they|them|their)\b", re.I)
_SIGNING = re.compile(r"\bsign\w*|executive order|decree\b", re.I)
_SPEAKING = re.compile(r"\bsaid|says|speech|address|announc\w+|declar\w+\b", re.I)
_CROWD = re.compile(r"\brally|protest|crowd|march|voters\b", re.I)
_BUILDING = re.compile(r"\bbuilding|tower|hotel|center|centre|arch|monument|statue|airport|park\b", re.I)


_THINGS = re.compile(r"\b(arch|tower|hotel|casino|golf course|building|monument|statue|plaza|airport|park|bridge|library|centre|center|wall|fence|jet|plane|helicopter|motorcade|podium|desk|flag|sign|plaque|lake|river|mountain)\b", re.I)


def thing_in(scene_text: str) -> str:
    """The physical object a scene names, if any."""
    m = _THINGS.search(scene_text or "")
    return m.group(1).lower() if m else ""


def frame_for(scene_text: str) -> str:
    """What the picture should show the subject doing."""
    if _BUILDING.search(scene_text):
        return "building"
    if _SIGNING.search(scene_text):
        return "signing"
    if _CROWD.search(scene_text):
        return "crowd"
    if _SPEAKING.search(scene_text):
        return "speaking"
    return "portrait"


def score_candidate(title: str, subject: Subject, *, thing: str = "") -> int:
    """How well a result depicts the subject. 0 means reject — a picture that is not of the
    thing you are talking about is worse than no picture, because the reader believes it."""
    low = (title or "").lower()
    if not subject.named_by(low):
        return 0
    score = 2
    if low.startswith(subject.words[0]):
        score += 2  # a file named for the subject is usually of the subject
    if thing and thing in low:
        score += 3  # it shows the specific object the scene is about
    if len(low) < 60:
        score += 1  # terse titles are catalogue photos; long ones are usually incidental
    return score
