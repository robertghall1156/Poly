# Poly — Current State Audit (2026-08-30, before the simplification / faceless-studio pass)

Method: traced every API router (`backend/poly/api/*.py`) to its service and model code, ran the
backend test suite (29 tests), and exercised the running app (backend + frontend) against seeded
data. Classification is based on traced code paths, not on the existence of buttons.

Legend: **WORKING** functional end-to-end · **PARTIAL** functionality exists, workflow incomplete ·
**DEMO** simulated · **NOT IMPLEMENTED** · **BROKEN**

## Data & persistence

| Capability | Status | Notes |
|---|---|---|
| SQLite default / Postgres+pgvector optional | WORKING | Same models both; Alembic initial migration; WAL; UTC datetimes |
| 30 tables incl. principles/revisions/evidence/counterarguments, articles/stories/claims/events, think sessions/briefs, content items/fact-check/metrics, videos/segments/clips, book, images, jobs, local_models, embeddings, settings | WORKING | Verified by tests and live use |
| Background jobs (Huey, SQLite queue) with Job tracking rows, retry, daily ingest schedule, 6-hourly re-embed | WORKING | Worker runs via `poly worker`; UI polls job rows |

## News intelligence

| Capability | Status | Notes |
|---|---|---|
| RSS provider (incl. `file://` fixtures, Google News RSS) | WORKING | Fetch, normalise, topic-tag |
| Brave / Tavily / NewsAPI adapters | PARTIAL | Code complete + unit-shaped; only activate with keys; never exercised against live APIs |
| Dedupe (URL hash, content hash, title simhash) | WORKING | Tested |
| Story clustering (TF cosine + entities + topics, 5-day window) | WORKING | Tested; merge endpoint exists |
| Story analysis: claims (typed), arguments, unresolved questions, competing interpretations, content potential, principle links, relevance | WORKING with local LLM; heuristic fallback always runs | Mock-verified end-to-end; live Ollama path verified only via wire-format fake |
| Default feed list (46 feeds) | PARTIAL | Curated but network-unverifiable from the build sandbox; failures surface per-feed in UI |
| Daily scheduled ingest | WORKING | Huey periodic task |

## Knowledge / thinking

| Capability | Status | Notes |
|---|---|---|
| Principles CRUD + revisions + evidence + counterarguments + markdown import/export | WORKING | Tested incl. roundtrip |
| Think Mode (one question at a time, staged interview) → Position Brief → approve into principle | WORKING | Tested end-to-end via API |
| Hybrid search (keyword + embeddings, RRF; hashing fallback until an embedding model exists) | WORKING | pgvector path also tested |

## Content

| Capability | Status | Notes |
|---|---|---|
| Long-form generator (11-section structure) | WORKING | |
| Social bundle (posts/thread/quote cards/hooks/titles/thumbnail text/meme concepts) → child items | WORKING | |
| Content statuses + calendar board + drag-and-drop | WORKING | |
| Fact-check gate (extract claims, block READY, override with reason) | WORKING | Tested |
| Content tree / lineage | WORKING | |
| Metrics: manual + CSV import; substance-vs-engagement view | WORKING | Platform APIs NOT IMPLEMENTED (by design, phase 7) |
| Meme/infographic **concepts** via generator | PARTIAL | Text concepts only; no template rendering, no editing loop |

## Media

| Capability | Status | Notes |
|---|---|---|
| Video folder indexing (ffprobe metadata only) | WORKING | Tested |
| Local transcription (mlx-whisper / faster-whisper / whisper.cpp) + import | WORKING (code + detection); real Whisper run pending first use on the Mac | Sandbox couldn't reach model downloads |
| Clip discovery + scoring + LLM titles/captions | WORKING | Tested with realistic transcript |
| 9:16 render with animated word captions, face-track crop, progress bar, watermark | WORKING | Real FFmpeg render asserted in tests |

## Images

| Capability | Status | Notes |
|---|---|---|
| Deterministic renderers: text meme, quote card, bar chart, infographic | WORKING | Pillow; approval flag; labels |
| Local generative provider (ComfyUI/A1111/OpenAI-images) | PARTIAL | Adapter written, disabled until configured; never run against a live server |

## System

| Capability | Status | Notes |
|---|---|---|
| Local AI registry, detection, task routing, local-only fallback, per-model test | WORKING | Ollama adapter verified against protocol-accurate fake |
| Privacy gate (Local AI Only / Internet Research / Cloud AI with confirm) | WORKING | Tested |
| Settings (news/media/content/github/brand-ish colors in content) | WORKING | |
| Cloud adapters (Anthropic/OpenAI) | PARTIAL | Written, policy-gated, disabled by default, never live-tested |

## Buttons that do nothing / demo features

None found. Every frontend action calls a real endpoint (the previous pass verified all 27 routes
with Playwright and zero console errors). The only "simulated" component in the codebase is the
**mock LLM provider**, which is explicitly a test/dev fixture behind `POLY_MOCK_LLM=1` and never
registered otherwise.

## Duplicated / confusing workflows (feeds into UX_AUDIT.md)

- Creating content is reachable from four places (story page, brief page, content page, generate
  dialog) with slightly different parameter sets.
- "Today" duplicates the Home "Today" section with filters.
- Research page mixes three unrelated admin concerns (notes, sources, feeds).
- The sidebar exposes 12 equally-weighted destinations; several (Analytics, Research, Book) are
  rarely-used relative to their prominence.
- The user must understand internal objects (Story, Position Brief, Principle, Content Item,
  fact_check_status) to navigate.

## Not implemented (as of this audit)

- Faceless/text-explainer video generation and rendering (no scene model, no scripted-video renderer)
- Meme templates (two buttons, expectation/reality, …) and a meme editing loop
- Carousels
- TTS / voiceover of any kind
- Central brand token system (colors exist as two settings fields + Tailwind classes)
- Universal "+ Create" launcher, "Create From This", one-click variations, unified review screen
- Platform analytics APIs; publishing integrations (intentionally out of scope)
