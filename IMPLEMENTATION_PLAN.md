# Poly — Implementation Plan

Build order follows the brief. Each phase ends in a working, committed state.

## Phase 1 — Foundation
- [x] Repository, `.gitignore`, `.env.example`, `docker-compose.yml`, Makefile-style scripts
- [x] FastAPI app, config, SQLAlchemy models, Alembic, SQLite default / Postgres optional
- [x] Provider interfaces + local model registry + task router + startup detection
- [x] Privacy policy gate (`Local AI Only`, `Allow Internet Research`, `Allow Cloud AI`)
- [x] Political operating system seeded from `knowledge/political_operating_system.md`
- [x] Principles CRUD with revisions, evidence, counterarguments, markdown export
- [x] Hybrid search (keyword + local embeddings, hashing fallback)
- [x] Huey job system with `Job` tracking rows

## Phase 2 — News
- [x] `RSSProvider` (feedparser + article extraction), curated feed list, Google News RSS queries
- [x] Adapters for Brave / Tavily / NewsAPI (disabled unless keys exist)
- [x] Normalise → dedupe (URL canonical hash, title simhash, content hash) → cluster into stories
- [x] Story analysis with local LLM (claims, topics, why it matters, arguments, opportunities) and heuristic fallback
- [x] Story timeline, Today dashboard, dashboard actions
- [x] Daily periodic job + manual "Run ingest now"

## Phase 3 — Thinking
- [x] Think sessions: one question at a time, principles retrieved by search
- [x] Position Brief generation, approve → principle create/revise with revision row

## Phase 4 — Content
- [x] Content items with lineage, statuses, calendar board (drag-and-drop)
- [x] Long-form generator (11-section structure) and social derivative generator
- [x] Fact check gate with override
- [x] Book workspace + Save to Book from stories/content/videos
- [x] Content tree view

## Phase 5 — Media
- [x] Video folders, ffprobe indexing (metadata only)
- [x] Local transcription providers (mlx-whisper, faster-whisper, whisper.cpp) + detection
- [x] Clip discovery and scoring; clip cards with timestamps and reasons
- [x] 9:16 render with animated captions, optional intro text, progress bar, watermark, safe zones

## Phase 6 — Images
- [x] Deterministic renderer (text meme, quote card, chart, quick infographic)
- [x] `ImageProvider` + local generative adapter (disabled until configured); metadata + approval

## Phase 7 — Analytics
- [x] Metrics table, manual entry + CSV import, substance-vs-engagement view
- [ ] Platform API adapters (YouTube / TikTok / Instagram / podcast hosts) — future

## Verification
- [x] Pytest suite (models, normalisation, dedupe, provider fallback, clustering, principle linking, lineage, video indexing, clip validity, fact-check gate, privacy gate)
- [x] Frontend type-check and production build
- [x] End-to-end smoke: ingest fixtures → story → think → brief → content → render clip
- [x] README, GitHub push instructions

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-08-30 | SQLite default, Postgres optional | Zero-setup daily use; identical models |
| 2026-08-30 | Huey (SQLite storage) for jobs | Real queue/periodic tasks without Redis |
| 2026-08-30 | Ollama primary runtime | Already installed on the target Mac |
| 2026-08-30 | Hashing embedding fallback | Search must work even with no embedding model pulled yet; upgraded transparently once `nomic-embed-text` (or any embedding model) is available |
| 2026-08-30 | Heuristic analysis fallback | Ingestion must never block on a model; LLM enrichment is queued and re-run when a model is available |
| 2026-08-30 | Single `models.py` | One file to read the schema; easier for a developer new to the codebase |
