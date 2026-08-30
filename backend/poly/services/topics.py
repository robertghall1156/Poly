"""Topic taxonomy and keyword-based tagging (used as the fast path and the LLM fallback)."""
from __future__ import annotations

import re

TOPICS: dict[str, list[str]] = {
    "government": ["government", "federal", "agency", "bureaucra", "regulation", "administration", "civil service"],
    "elections": ["election", "ballot", "voter", "campaign", "primary", "midterm", "poll", "candidate", "redistrict", "gerrymander"],
    "congress": ["congress", "senate", "house of representatives", "senator", "representative", "speaker", "filibuster", "bill ", "legislation", "lawmakers"],
    "presidency": ["president", "white house", "executive order", "administration", "oval office", "veto"],
    "courts": ["supreme court", "court", "judge", "ruling", "justice", "appeals", "lawsuit", "scotus", "judicial"],
    "taxes": ["tax", "irs", "deduction", "capital gains", "estate tax", "tariff", "revenue"],
    "wealth": ["billionaire", "wealth", "inequality", "net worth", "inheritance", "top 1%", "millionaire"],
    "corporate power": ["antitrust", "monopoly", "merger", "corporate", "lobby", "shareholder", "big tech", "ftc", "consolidation"],
    "labor": ["union", "strike", "workers", "labor", "wage", "employment", "layoff", "nlrb", "collective bargaining", "jobs report"],
    "executive compensation": ["ceo pay", "executive compensation", "executive pay", "stock options", "golden parachute", "pay ratio", "say on pay", "compensation committee"],
    "ai": ["artificial intelligence", " ai ", "openai", "anthropic", "large language model", "chatgpt", "machine learning", "generative"],
    "automation": ["automation", "robot", "automate", "self-driving", "autonomous"],
    "healthcare": ["health", "medicare", "medicaid", "insurance", "hospital", "drug price", "pharma", "affordable care", "obamacare", "premium"],
    "education": ["school", "education", "student", "college", "university", "tuition", "teacher", "apprentice", "student loan"],
    "immigration": ["immigra", "border", "asylum", "visa", "deport", "citizenship", "migrant", "h-1b", "ice "],
    "defense": ["pentagon", "defense", "military", "army", "navy", "air force", "procurement", "weapons", "nato", "contractor"],
    "veterans": ["veteran", " va ", "veterans affairs", "gi bill"],
    "foreign policy": ["foreign", "diplomat", "sanction", "ukraine", "china", "russia", "israel", "iran", "treaty", "ally", "nato", "taiwan"],
    "technology": ["tech", "software", "semiconductor", "chip", "data", "privacy", "cyber", "platform", "social media"],
    "economic policy": ["economy", "inflation", "gdp", "federal reserve", "interest rate", "recession", "fiscal", "deficit", "debt ceiling", "budget", "stimulus"],
    "housing": ["housing", "rent", "mortgage", "zoning", "homeless", "home price", "affordab"],
    "energy": ["energy", "oil", "gas", "climate", "solar", "wind", "nuclear", "electric", "grid", "epa", "emissions"],
    "infrastructure": ["infrastructure", "bridge", "highway", "transit", "rail", "broadband", "water system"],
}

TOPIC_LIST = list(TOPICS.keys())


def tag_topics(text: str, *, max_topics: int = 5) -> list[str]:
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    scores: dict[str, int] = {}
    for topic, kws in TOPICS.items():
        s = 0
        for kw in kws:
            s += t.count(kw)
        if s:
            scores[topic] = s
    return [k for k, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:max_topics]]


def normalize_topics(topics) -> list[str]:
    out = []
    for t in topics or []:
        t = str(t).strip().lower().replace("_", " ")
        if t in TOPICS and t not in out:
            out.append(t)
    return out
