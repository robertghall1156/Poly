# Poly — Product Specification

## What Poly is

Poly is a personal political intelligence, research, reasoning and content-creation operating
system. It watches the news, groups it into stories, connects those stories to a living document of
political principles, challenges the owner's thinking, and only then helps produce podcasts, videos,
shorts, posts, memes, visuals and book material — with full lineage from source to published piece.

Poly is **not** a chatbot wrapper. It is a database, a job system, a set of workflows and a
professional UI. It is built for one person and runs on that person's machine.

## Product principle

> Poly should help me think before it helps me publish.

Canonical workflow:

`News → Research → Connect to worldview → Challenge → Develop position → Approve → Create content → Edit → Publish/export → Track`

Hard rules:

- Never automatically post political content. Every export requires an explicit approval action.
- No voter microtargeting, no psychological profiling, no persuasion scoring, no customisation by
  sensitive personal characteristics. Poly analyses public policy, public news and aggregate
  audiences only.
- Never fabricate quotes, statistics, evidence or images presented as real events.
- Local AI only by default. Private material never leaves the machine unless *Allow Cloud AI* is
  explicitly switched on, and the UI makes any such call visually obvious.

## Areas (sidebar)

| Area | Purpose | Key actions |
|---|---|---|
| **Home** | "What matters today?" | Today's top developments; Think About (stories that challenge or connect with principles); Create (best content opportunities); Continue (in-progress positions/content); Recent video opportunities. |
| **Today** | Daily dashboard of 5–10 relevant stories | Per story: headline, summary, why it matters, principles touched, strongest arguments on multiple sides, primary sources, content opportunity and recommended format. Actions: Ignore, Research, Develop Position, Create Content, Save for Book. |
| **Stories** | Story clusters over time | Timeline of how a story evolved, article list (deduplicated), major claims with provenance and claim type (FACT / ANALYSIS / OPINION / COUNTERFACTUAL / PREDICTION), unresolved questions, competing interpretations. |
| **Think** | Think Mode | One-question-at-a-time interview against a story or policy question; produces a Position Brief; approve into the operating system. |
| **Principles** | The Political Operating System | Add/edit principles, status (provisional/established/retired), confidence, evidence, counterarguments, linked content, revision history, markdown export. |
| **Research** | Notes and briefs | Research notes attached to stories/principles; research briefs; source management with reliability notes. |
| **Content** | Content database | Items by format/status, generators (long-form, social derivatives), content tree (lineage), fact check gate, export. |
| **Videos** | Video library | Configure folders, index metadata, transcribe, find clip opportunities, render 9:16 shorts with captions. |
| **Book** | Book workspace | Concepts, themes, chapters, personal stories, notes; Save to Book from anywhere; episode-to-book conversion. |
| **Calendar** | Content pipeline board | Columns IDEA → RESEARCHING → POSITION DEVELOPED → SCRIPTING → RECORDED → EDITING → READY → PUBLISHED; drag-and-drop; platform destinations. |
| **Analytics** | Performance | Manual/CSV metrics import; substantive-value vs engagement view. |
| **Settings** | Configuration | AI (local models, task assignment), Local AI status page, Privacy & Network, News sources/RSS/topics, Media (folders, FFmpeg, transcription), Content defaults/branding, GitHub info. |

Global search (⌘K) finds principles, articles, stories, scripts, videos, transcript segments, clips,
book notes and research using hybrid keyword + semantic retrieval.

## Feature specifications

### Political Operating System
- Seeded from `knowledge/political_operating_system.md`; the markdown file stays the human-readable
  export and can be re-imported.
- Principle fields: title, category, current_position, rationale, status, confidence, timestamps.
- Every position change writes a `PrincipleRevision` with reason.
- Evidence and counterarguments attach to a principle with source metadata and strength.
- Content and position briefs link back to principles.

### News intelligence
- Modular `NewsProvider`s; RSS ships enabled with a curated multi-perspective feed list (wire
  services, national papers, government feeds — Federal Register, White House, Congress, SCOTUS,
  CBO, GAO, BLS, Fed — and think tanks from several perspectives).
- Daily pipeline: search → normalise → dedupe → cluster → new/continuing → claims → primary sources
  → topics → compare with principles → relevance → content opportunities → save.
- Topics (minimum): government, elections, congress, presidency, courts, taxes, wealth,
  corporate power, labor, executive compensation, ai, automation, healthcare, education, immigration,
  defense, veterans, foreign policy, technology, economic policy, housing, energy, infrastructure.
- Claims retain provenance and are typed FACT / ANALYSIS / OPINION / COUNTERFACTUAL / PREDICTION.

### Think Mode
- Interview loop; one substantive question at a time.
- The model is instructed to: surface initial instinct, compare with existing principles, find
  contradictions, present the strongest opposing argument, challenge weak assumptions, list facts
  needing verification, ask which tradeoffs are acceptable.
- Output: Position Brief (issue, position, rationale, governing principle, strongest for/against,
  response, factual assumptions, unresolved questions, policy mechanisms, confidence).
- Approve → creates or revises a principle.

### Content engine
- Formats: podcast, youtube, youtube_short, tiktok, instagram_reel, x_post, x_thread,
  facebook_post, instagram_post, linkedin_post, newsletter, article, book_note, meme, infographic,
  talking_points.
- Long-form generator produces the full package (titles, hook, opening, thesis, outline in the
  default 11-section structure, research needed, arguments, counterarguments, examples, evidence,
  transitions, conclusion, call to discussion, show notes, sources).
- Social derivative generator: 3–5 posts, thread, quote cards, short video ideas, 5 hooks, 5 titles,
  thumbnail text, 3 meme concepts.
- Voice guide is enforced through a shared system prompt (`services/voice.py`).
- Content items have `parent_id` for lineage; the Content Tree renders the family.
- Fact Check extracts assertions and labels VERIFIED / SUPPORTED BUT UNCERTAIN / OPINION /
  COUNTERFACTUAL / UNVERIFIED / OUTDATED. A script cannot become FACT_CHECKED with unresolved
  assertions unless the user records an explicit override with a reason.

### Media
- Video folders are indexed by metadata only (ffprobe). Files are never copied into the repo.
- Transcription is local (mlx-whisper / faster-whisper / whisper.cpp) with word timestamps.
- Clip discovery: semantic sectioning + scoring on hook, self-containment, energy, clarity,
  surprise, educational value, controversy-without-distortion, news relevance.
- Rendering: 9:16 crop (center/face), animated word captions, styles, optional intro text, progress
  bar, watermark, safe-zone padding. Originals preserved; outputs go to `data/renders/`.

### Images
- Deterministic renderers for text memes, quote cards, charts and simple infographics.
- `ImageProvider` interface with a local generative adapter (disabled until configured).
- Every generated image stores prompt + metadata; approval required before export; generated or
  satirical imagery is labelled.

### Analytics
- Metrics per content item (views, watch time, retention, likes, comments, shares, subscribers,
  completion). Manual entry and CSV import now; platform API adapters later.
- A *substantive value* score (owner-rated + fact-check density) is shown against engagement so the
  system never optimises for outrage alone.

## MVP acceptance checklist

1. Start locally. 2. Open dashboard. 3. See principles. 4. Edit/add principles. 5. Ingest real news via
RSS. 6. See deduplicated stories. 7. Open a story. 8. See principle relevance. 9. Start Think Mode.
10. Develop and save a position. 11. Generate a YouTube/podcast outline. 12. Generate social
derivatives. 13. Add a local video folder. 14. Transcribe a video. 15. Identify clip opportunities.
16. Render a vertical short with captions. 17. Persist everything. 18. Search across the system.
19. Restart without losing state.
