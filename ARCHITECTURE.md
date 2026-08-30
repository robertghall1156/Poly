# Poly — Architecture

Poly is a local-first political intelligence and content operating system. This document explains
how it is put together and why.

## Guiding constraints

1. **Local-first.** Everything that touches Rob's own material (principles, notes, scripts, transcripts,
   video) is processed on the machine. Only *public* retrieval (RSS, government feeds, optional news
   APIs) leaves the machine, and those requests carry only the query — never private context.
2. **Think before publish.** Workflows are gated by explicit human approval. Nothing is ever posted
   automatically; "publish" means *export* plus a manual link/metrics record.
3. **Replaceable providers.** Every external capability sits behind an interface
   (`LLMProvider`, `EmbeddingProvider`, `TranscriptionProvider`, `ImageProvider`, `NewsProvider`).
   Nothing outside `poly/providers/` knows the name of a runtime.
4. **Real persistence and real jobs.** SQLAlchemy models, Alembic migrations, and a real background
   worker (Huey). No fake async in the UI.
5. **Simple to run.** One backend, one frontend, no mandatory Docker.

## Topology

```
┌───────────────────────────── Mac (localhost) ─────────────────────────────┐
│                                                                           │
│  Next.js 15 (frontend/)  ── HTTP ──▶  FastAPI (backend/)                  │
│      :3000                                 :8000                          │
│                                              │                            │
│                                     SQLAlchemy 2.0                        │
│                            ┌──────────────┴──────────────┐                │
│                       SQLite (default)          Postgres 16 + pgvector    │
│                       data/poly.db              (docker compose, optional)│
│                                              │                            │
│                                     Huey worker (backend/)                │
│                                     periodic: daily ingest, embeddings,   │
│                                     transcription, clip render            │
│                                              │                            │
│        ┌─────────────────────────────────────┼──────────────────────┐     │
│   Ollama :11434        FFmpeg / ffprobe      mlx-whisper /          │     │
│   (LLM + embeddings)   (media)               faster-whisper         │     │
│   or any OpenAI-compatible local server                             │     │
└───────────────────────────────────────────────────────────────────────────┘
                 ▲ public internet only: RSS, gov feeds, optional news APIs
```

## Why this stack

| Decision | Choice | Why |
|---|---|---|
| Backend | **Python / FastAPI** | The heavy lifting (NLP, FFmpeg, Whisper, clustering, embeddings) is all Python-native. One backend keeps the codebase simple for a solo developer. Next.js server routes are used only for proxying. |
| Frontend | **Next.js 15 + TypeScript + Tailwind** | Spec preference; App Router pages map 1:1 to the sidebar. Components are a small, hand-maintained shadcn-style set (no generator dependency). |
| ORM | **SQLAlchemy 2.0 + Alembic** | Works identically against SQLite and Postgres, so the same models run zero-setup and "production". |
| Database | **SQLite by default, Postgres + pgvector optional** | Rob asked for a zero-Docker daily workflow. `POLY_DATABASE_URL` switches to Postgres; vector search uses pgvector when present and an in-process cosine index on SQLite. At personal scale (tens of thousands of chunks) the SQLite path is fast enough. |
| Jobs | **Huey (SQLite storage)** | A real job framework (queues, retries, periodic tasks, separate worker process) that needs no Redis. Swapping to Redis storage is one line if Poly ever scales. |
| Local AI | **Ollama first, OpenAI-compatible second** | Rob already runs Ollama. `OllamaProvider` and `OpenAICompatibleProvider` (LM Studio, llama.cpp, vLLM, MLX server) share the `LLMProvider` interface. Cloud adapters exist but are disabled unless *Allow Cloud AI* is switched on. |
| Model routing | **Model registry + task router** | Tasks are typed (`FAST`, `REASONING`, `WRITING`, `EMBEDDING`, `VISION`, `TRANSCRIPTION`). The router picks the highest-priority enabled local model for that task and falls back to the next local model — never silently to cloud. |
| Transcription | **mlx-whisper on Apple Silicon, faster-whisper otherwise, whisper.cpp CLI if present** | Detected at startup; all local. |
| Media | **FFmpeg** | Indexing (ffprobe), audio extraction, clip cutting, 9:16 crop, caption burn-in via ASS subtitles. |
| Images | **Deterministic renderer (Pillow) + optional local generative provider** | Memes, quote cards, charts and infographics never need a diffusion model. A `LocalImageProvider` stub targets ComfyUI / A1111 / any OpenAI-images-compatible local endpoint, disabled until configured. |

## Backend layout

```
backend/
  poly/
    config.py            # settings from env (.env), paths, defaults
    db.py                # engine/session, SQLite pragmas, pgvector detection
    models.py            # all SQLAlchemy models (single file on purpose — one place to read the schema)
    schemas.py           # Pydantic request/response models
    main.py              # FastAPI app factory, startup detection, router registration
    api/                 # one router per sidebar area
      principles.py stories.py think.py content.py videos.py book.py search.py settings.py jobs.py dashboard.py images.py
    providers/
      base.py            # interfaces + shared types
      registry.py        # LocalModelRegistry, task router, health/latency probes
      llm/               # ollama.py, openai_compat.py, anthropic.py (cloud, off), openai.py (cloud, off), mock.py (tests)
      embeddings/        # ollama.py, openai_compat.py, hashing.py (deterministic fallback so search always works)
      transcription/     # mlx_whisper.py, faster_whisper.py, whisper_cpp.py
      image/             # deterministic.py (Pillow), local_generative.py (ComfyUI/A1111/OpenAI-compatible)
      news/              # rss.py, brave.py, tavily.py, newsapi.py, google_news_rss.py
      detect.py          # startup scan of local runtimes
    services/            # business logic, provider-agnostic
      privacy.py         # NetworkPolicy gate every provider call passes through
      principles.py      # operating-system CRUD, revisions, markdown export/import
      ingest.py          # normalize → dedupe → cluster → analyze
      clustering.py      # story clustering (TF-IDF + embedding similarity, time-windowed)
      analysis.py        # claims, topics, relevance vs principles, opportunities (LLM with heuristic fallback)
      think.py           # Think Mode interview state machine + position brief
      content.py         # long-form / social generators, lineage, calendar
      factcheck.py       # claim extraction + status gating
      search.py          # hybrid keyword + vector search
      media.py           # ffprobe indexing, transcription orchestration, clip scoring, rendering
      images.py          # meme / quote-card / chart rendering
    jobs/
      huey_app.py        # Huey instance
      tasks.py           # ingest_daily, process_article, embed_entity, transcribe_video, render_clip ...
    cli.py               # `poly` command: init-db, detect, ingest, worker, seed
  alembic/               # migrations
  tests/                 # pytest, realistic fixtures
```

## Request flow examples

**Daily ingest** — Huey periodic task (default 06:30 local) → `NewsProvider.fetch()` for each enabled
source → `ingest.normalize()` → `ingest.dedupe()` (URL canonicalisation, title simhash, content hash)
→ `clustering.assign_story()` → `analysis.analyze_story()` (local LLM: claims, topics, relevance,
opportunities; heuristic fallback if no model) → embeddings queued → rows committed.

**Think Mode** — POST `/think/sessions` with story or question → the REASONING model is asked for one
question given the transcript so far and the relevant principles (retrieved via hybrid search) → user
answers → repeat → `finish` produces a Position Brief → `approve` writes a Principle (new or revised,
with a `PrincipleRevision` row) and links the brief.

**Clip render** — POST `/videos/{id}/clips/{clip}/render` enqueues `render_clip` → FFmpeg cuts
`[start,end]`, crops to 9:16 (center or face-tracked using OpenCV Haar cascade when available), burns
word-timed ASS captions, writes to `data/renders/` — the source file is never modified.

## Privacy enforcement

`services/privacy.py` exposes `NetworkPolicy` with three switches persisted in settings:
`local_ai_only` (default ON), `allow_internet_research` (default ON), `allow_cloud_ai` (default OFF).
Every provider declares `locality: "local" | "cloud"` and `purpose: "ai" | "research"`. The router
refuses to construct or call a cloud AI provider unless `allow_cloud_ai` is ON *and*
`local_ai_only` is OFF. Failed local calls are recorded on the `Job` row with `retryable=True`; the
UI shows the failure and offers retry or (if enabled) a one-time cloud override.

## Frontend layout

```
frontend/src/app/(app)/{page}/page.tsx      # home, today, stories, think, principles, research, content, videos, book, calendar, analytics, settings
frontend/src/components/ui/*               # button, input, textarea, badge, dialog, tabs, select … (shadcn-style)
frontend/src/components/*                  # app shell, sidebar, search palette, story card, content tree, calendar board
frontend/src/lib/api.ts                    # typed fetch client for the FastAPI backend
```

The Next.js app talks to FastAPI at `NEXT_PUBLIC_POLY_API` (default `http://localhost:8000`).

## Testing strategy

Pytest with an isolated SQLite database per test session, a `MockLLMProvider` that returns
deterministic structured output, a fake Ollama HTTP server (to test the real adapter's wire format),
fixture RSS files, and a generated test video (FFmpeg `testsrc`) so media tests run anywhere.
