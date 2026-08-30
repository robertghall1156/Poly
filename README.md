# Poly

**A local-first political intelligence, research, reasoning and content operating system.**

Poly watches the news, groups it into stories, connects those stories to a living document of your
political principles, challenges your thinking *before* you write anything, and then helps you turn
approved positions into podcasts, videos, shorts, posts, memes, charts and book material — with
full lineage from source to published piece.

Everything that touches your own material runs on your machine: local LLMs (Ollama or any
OpenAI-compatible local server), local embeddings, local Whisper transcription, FFmpeg. Only
*public* retrieval (RSS, government feeds, optional news APIs) leaves the machine, and it carries
only the query. Cloud AI adapters exist but are **off by default** and require an explicit switch.

> Product principle: **Poly should help you think before it helps you publish.**
> `News → Research → Connect to worldview → Challenge → Develop position → Approve → Create content → Edit → Publish/export → Track`
>
> Nothing is ever posted automatically.

Docs: [ARCHITECTURE.md](ARCHITECTURE.md) · [PRODUCT_SPEC.md](PRODUCT_SPEC.md) · [DATA_MODEL.md](DATA_MODEL.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

---

## Architecture at a glance

```
Next.js 15 UI (:3000)  ──▶  FastAPI (:8000)  ──▶  SQLAlchemy  ──▶  SQLite (default)  |  Postgres 16 + pgvector (optional, docker compose)
                                  │
                           Huey worker (SQLite queue) — daily ingest, analysis, embeddings, transcription, clip rendering
                                  │
              Ollama / LM Studio / llama.cpp (LLM + embeddings)   ·   mlx-whisper / faster-whisper (transcription)   ·   FFmpeg (media)
```

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic | NLP, FFmpeg, Whisper and clustering are Python-native |
| Frontend | Next.js 15 · TypeScript · Tailwind v4 · hand-built shadcn-style components | Clean, dense, professional UI |
| Database | SQLite by default; Postgres + pgvector via `docker compose` | Zero-setup daily use; identical models on both |
| Jobs | Huey (SQLite storage) | Real queue, retries and a daily schedule without Redis |
| Local AI | Provider interfaces + model registry + task router | Nothing outside `poly/providers/` knows what Ollama is |

## Requirements

- macOS (Apple Silicon recommended) or Linux
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — manages Python 3.11 and the venv
- Node 20+ (`brew install node`)
- FFmpeg (`brew install ffmpeg`)
- [Ollama](https://ollama.com) running locally (or LM Studio / llama.cpp / vLLM / MLX server — see *AI providers*)
- Optional: Docker Desktop, only if you want Postgres

## Quick start

```bash
git clone <your-repo-url> Poly && cd Poly
./scripts/setup.sh          # creates .env, installs backend (uv) + frontend (npm), seeds the DB
./scripts/dev.sh            # starts API :8000, worker, and UI :3000 together
```

Open <http://localhost:3000>. On first start Poly:

1. creates the database (SQLite at `data/poly.db`)
2. imports your principles from `knowledge/political_operating_system.md`
3. adds the curated default feeds
4. scans for local AI runtimes (Ollama, LM Studio/OpenAI-compatible servers, Whisper) and recommends task assignments — see **Settings → Local AI**

Recommended Ollama models (pull once; Poly auto-detects them on *Refresh local models*):

```bash
ollama pull nomic-embed-text   # local embeddings → semantic search (until then a lexical fallback is used)
ollama pull qwen2.5:14b        # REASONING / WRITING on a 32 GB Apple Silicon Mac
ollama pull llama3.2:3b        # FAST classification, summaries, tagging
```

Then click **Run ingest now** on Home (or `make ingest`) to pull today's news.

### Running the pieces separately

```bash
make backend    # API with autoreload      (cd backend && .venv/bin/poly serve --reload)
make worker     # background jobs + daily schedule
make frontend   # Next.js dev server
make test       # backend test suite
make build      # frontend production build
```

API docs (OpenAPI) are at <http://localhost:8000/docs>.

## Environment variables

Copy `.env.example` to `.env` (setup does this). Secrets are never committed.

| Variable | Default | Purpose |
|---|---|---|
| `POLY_DATABASE_URL` | `sqlite:///./data/poly.db` | `postgresql+psycopg://poly:poly@localhost:5432/poly` for Postgres |
| `POLY_DATA_DIR` | `./data` | database, job queue, renders, generated images, caches |
| `POLY_KNOWLEDGE_FILE` | `./knowledge/political_operating_system.md` | the markdown form of your principles |
| `POLY_FFMPEG_PATH` / `POLY_FFPROBE_PATH` | `ffmpeg` / `ffprobe` | media tools |
| `POLY_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `POLY_OPENAI_COMPAT_URLS` | `http://localhost:1234/v1` | comma-separated local OpenAI-compatible servers (LM Studio, llama.cpp, vLLM, MLX) |
| `POLY_LOCAL_AI_ONLY` / `POLY_ALLOW_INTERNET_RESEARCH` / `POLY_ALLOW_CLOUD_AI` | `true` / `true` / `false` | initial privacy switches (editable in Settings) |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | empty | optional cloud AI, only used if *Allow Cloud AI* is on |
| `BRAVE_API_KEY`, `TAVILY_API_KEY`, `NEWSAPI_KEY` | empty | optional news/search providers; RSS needs no key |
| `POLY_LOCAL_IMAGE_URL`, `POLY_LOCAL_IMAGE_KIND` | empty | optional local image-generation server (see below) |
| `POLY_DAILY_INGEST_HOUR` / `_MINUTE` | `6` / `30` | daily news job time (local time of the worker) |
| `NEXT_PUBLIC_POLY_API` | `http://localhost:8000` | where the UI finds the API |

Development-only flags: `POLY_MOCK_LLM=1` registers a deterministic mock model (used by tests);
`POLY_JOBS_IMMEDIATE=1` runs jobs inline instead of through the worker.

## Docker (optional Postgres + pgvector)

```bash
docker compose up -d                       # pgvector/pgvector:pg16 on :5432 (user/pass/db = poly)
# in .env:
POLY_DATABASE_URL=postgresql+psycopg://poly:poly@localhost:5432/poly
cd backend && .venv/bin/alembic upgrade head
```

The same code runs on both databases; on Postgres semantic search uses pgvector's cosine operator,
on SQLite it uses an in-process cosine index (fast enough at personal scale). The test suite runs
against Postgres too: `POLY_TEST_DATABASE_URL=postgresql+psycopg://poly:poly@localhost:5432/poly make test`.

## Database migrations

Alembic lives in `backend/alembic`. A fresh database is created automatically at startup
(`create_all`); for schema upgrades of an existing database:

```bash
cd backend
.venv/bin/alembic upgrade head                    # apply
.venv/bin/alembic revision --autogenerate -m "…"  # after changing poly/models.py
```

## The Political Operating System

`knowledge/political_operating_system.md` is the human-readable form of your principles. Each
`##` heading is a category, each `###` heading a principle with `status`, `confidence`,
`Position:` and `Rationale:`. It is imported on first run; afterwards the database is the source of
truth and the file is an export you can regenerate:

```bash
cd backend && .venv/bin/poly export-principles    # DB → markdown
cd backend && .venv/bin/poly import-principles    # markdown → DB (changed positions create revisions)
```

Every position change — from the UI, an import, or an approved Position Brief — writes a
`PrincipleRevision` with the reason, so you can see when and why your thinking changed.

## News providers and feeds

`poly/providers/news/` implements the `NewsProvider` interface:

| Provider | Needs key | Notes |
|---|---|---|
| `rss` | no | Any RSS/Atom feed. **Default.** Also accepts `file://` URLs (used for offline fixtures) |
| `google_news_rss` | no | Google News search as RSS (`query`) |
| `brave`, `tavily`, `newsapi` | yes | Enabled automatically when the key is present |

The curated default list (`default_feeds.py`) mixes wire services, national papers across the
spectrum, government primary sources (Federal Register, White House, Congress.gov, CBO, GAO, BLS,
BEA, Fed, SEC, Census) and think tanks from several perspectives, each with a `Source` row carrying
source type, primary/secondary, ideology (where widely characterised) and reliability notes.

**Adding a feed:** Research → Feeds → *Add feed* (name, URL, category), or `POST /api/feeds`.
Feeds that fail show their last error in the same table; disable or fix them there. Publishers
change feed URLs from time to time — treat the default list as a starting point.

**The daily pipeline** (`services/ingest.py`, `clustering.py`, `analysis.py`): fetch → normalise
(canonical URL, tracking params stripped, title cleaned, topic tags) → dedupe (URL hash, content
hash, title simhash) → cluster into stories (term-frequency cosine + entity overlap within a 5-day
window) → analyse with the local FAST model (summary, why it matters, typed claims with provenance,
arguments on multiple sides, unresolved questions, competing interpretations, content opportunities,
principle links) → embed. If no model is available the heuristic layer still runs and the story is
re-analysed later. The worker runs this daily at `POLY_DAILY_INGEST_HOUR:MINUTE`; *Run ingest now*
runs it on demand.

## AI providers (local first)

Interfaces in `poly/providers/base.py`: `LLMProvider`, `EmbeddingProvider`,
`TranscriptionProvider`, `ImageProvider`, `NewsProvider`. Adapters:

| Adapter | Runtime | Locality |
|---|---|---|
| `OllamaProvider` | Ollama (`/api/chat`, `/api/embed`, `/api/tags`, `/api/show`) | local |
| `OpenAICompatibleProvider` | LM Studio, llama.cpp `llama-server`, vLLM, `mlx_lm.server`, LocalAI … | local |
| `AnthropicProvider`, OpenAI cloud | Claude / GPT | cloud — **disabled unless Allow Cloud AI is on** |
| `HashingEmbeddingProvider` | none | local fallback so search always works |
| `MLXWhisperProvider`, `FasterWhisperProvider`, `WhisperCppProvider` | local Whisper | local |
| `LocalGenerativeImageProvider` | ComfyUI / A1111 / OpenAI-images-compatible local server | local, disabled until configured |

**Model registry & routing.** Detected models are stored in `local_models` with their runtime,
endpoint, size, context window and **task categories**: `FAST`, `REASONING`, `WRITING`,
`EMBEDDING`, `VISION`, `TRANSCRIPTION`, `IMAGE`. Poly classifies each model from its name and
parameter count (≤5B → FAST/WRITING, ≤12B → all three, larger → REASONING/WRITING; embedding and
vision models by name), and you can change assignments, priority, and enabled state in
**Settings → Local AI**. The `Router` picks the best enabled local model for a task; if it fails it
tries the next local model and records the error on the model row. If no model is assigned to a
chat task it borrows from neighbouring categories, so one installed model still runs everything.
It never silently falls back to a cloud provider — the job fails visibly, stays retryable, and you
can choose to allow cloud AI explicitly.

**Privacy & Network** (Settings): *Local AI Only* (default on), *Allow Internet Research*
(default on), *Allow Cloud AI* (default off, needs a confirmation dialog). Every provider call is
checked against this policy (`services/privacy.py`). The top bar shows the current state; anything
cloud-related is orange.

**Add a custom endpoint** (e.g. a llama.cpp server on another port): Settings → Local AI →
*Add model/endpoint*, or set `POLY_OPENAI_COMPAT_URLS` and click *Refresh local models*.

## Video library, transcription, clips

- **Folders:** Videos → *Add folder*. Poly indexes metadata only (ffprobe: duration, resolution,
  fps, codec, dates, a fingerprint). Files are never copied, never modified, never committed.
- **Transcription** is local. On Apple Silicon `setup.sh` installs `mlx-whisper` (default model
  `mlx-community/whisper-large-v3-turbo`, downloaded from Hugging Face on first use, ~1.6 GB);
  elsewhere `faster-whisper`. If you already have `whisper-cli` (whisper.cpp) on your PATH it is
  detected too. Choose the mode/model in Settings → Media. You can also import a transcript made
  by another local tool (`POST /api/videos/{id}/transcript`).
- **Clip discovery** (`services/media.py`): transcript → sentence units → candidate windows
  (18–75 s) scored on hook, self-containment, energy, clarity, surprise, educational value, clear
  argument, controversy-without-distortion and relevance to current stories; the local FAST model
  adds a title, caption, and "why it works". Candidates are shown with timestamps and transcript.
- **Rendering** a clip produces a 9:16 (1080×1920 by default) MP4 in `data/renders/`: center or
  face-tracked crop (OpenCV Haar cascade when `opencv-python-headless` is installed), animated
  word-highlight captions (ASS subtitles; styles `bold_pop`, `clean`, `boxed`; safe-zone margins
  for TikTok/Reels UI), optional intro text, progress bar, watermark text or logo image. Originals
  are untouched. A rendered clip can be added to Content with one click.

FFmpeg must be on your PATH (or set `POLY_FFMPEG_PATH`). Settings → Local AI shows its status.

## Content engine

- **Generate** (Content → Generate, or from a story / brief): long-form packages for
  podcast/YouTube/newsletter/article (titles, hook, 30-second opening, thesis, the 11-section outline
  *Question → Why people care → How the current system works → How we got here → What is working →
  What is broken → Strongest counterargument → My view → What I would change → What could go wrong →
  Conclusion*, research needed, arguments, counterarguments, examples, evidence, transitions,
  conclusion, call to discussion, show notes, sources), short-video scripts, platform posts,
  talking points, book notes, meme/infographic concepts.
- **Social derivatives** from any long-form item: 3–5 posts, thread, quote cards, short-video ideas,
  5 hooks, 5 titles, thumbnail text, 3 meme concepts — materialised as child items so the
  **Content Tree** shows the whole family.
- **Fact Check**: extracts every factual assertion and labels it VERIFIED / SUPPORTED BUT UNCERTAIN
  / OPINION / COUNTERFACTUAL / UNVERIFIED / OUTDATED with source links. An item cannot become
  READY/PUBLISHED while unresolved assertions remain unless you record an explicit override reason.
- **Calendar**: drag-and-drop board IDEA → RESEARCHING → POSITION DEVELOPED → SCRIPTING → RECORDED →
  EDITING → READY → PUBLISHED with platform destinations.
- **Voice** (`services/voice.py`) is applied to every generation prompt: curious, practical,
  direct, evidence-driven, questions both parties, skeptical of concentrated power, comfortable with
  "I don't know yet", systems and incentives, solutions over outrage. No rage bait, no fake
  certainty, no fabricated quotes or statistics.

## Images

Deterministic renderers (Pillow) need no model: text memes, quote cards, bar charts, quick
infographics — `POST /api/images` with `kind` = `text_meme | quote_card | chart | infographic`.
Every image stores its prompt/params and requires **approval** before export; generated or
satirical imagery is labelled.

**Local image generation** is off until you point Poly at a local server:

```bash
POLY_LOCAL_IMAGE_URL=http://localhost:8188   POLY_LOCAL_IMAGE_KIND=comfyui        # ComfyUI (workflow at data/comfy_workflow.json with {{PROMPT}})
POLY_LOCAL_IMAGE_URL=http://localhost:7860   POLY_LOCAL_IMAGE_KIND=a1111          # Automatic1111 / Forge
POLY_LOCAL_IMAGE_URL=http://localhost:8080   POLY_LOCAL_IMAGE_KIND=openai_images  # any local /v1/images/generations server
```

No model is installed automatically. Storage/hardware guidance: SDXL ≈ 7 GB and runs comfortably
on a 32 GB Apple Silicon Mac via ComfyUI or DiffusionKit/MLX; FLUX.1-schnell ≈ 24 GB and is slow
without a large GPU. Pick one when you want generated visuals; Poly's deterministic renderers cover
memes, quote cards and charts without it.

## Analytics

Metrics per content item (views, watch time, retention, likes, comments, shares, subscribers,
completion) via manual entry or CSV import (`content_item_id` or `title`, `platform`,
`recorded_at`, metric columns). The Analytics page plots engagement against **substantive value**
(your 0–5 rating, or the verified-claim ratio) so *high engagement + high substance* is
distinguishable from *high engagement + low substance*. Platform API adapters (YouTube, TikTok,
Instagram, podcast hosts) are the next step and slot into the same table.

## Search

Global search (⌘K) is hybrid: keyword matching over titles/bodies plus cosine similarity over
local embeddings of principles, articles, stories, research notes, transcript segments, clips,
scripts/posts, book notes and position briefs, fused with reciprocal-rank fusion. Embeddings are
re-computed automatically (worker, every 6 h; or `poly reembed`) once a real embedding model
replaces the hashing fallback.

## Tests

```bash
make test        # backend: 29 tests — models, RSS parsing & normalisation, dedupe (URL/content/title simhash),
                 # clustering, story analysis + principle linking, provider fallback (never to cloud),
                 # Ollama wire format against a fake server, Think Mode → brief → approved principle,
                 # content generation + lineage + content tree, fact-check gate, privacy gate, hybrid search,
                 # video indexing, transcript storage, clip candidates (timestamp validity), ASS captions,
                 # real 9:16 FFmpeg render, end-to-end API flow, persistence.
make build       # frontend type-check + production build
make lint
```

Tests use realistic RSS fixtures (`backend/tests/fixtures/`), a deterministic mock LLM
(`POLY_MOCK_LLM=1`) and a synthetic FFmpeg-generated video — no personal media, no network.

## Privacy & integrity commitments (enforced in code)

- No cloud AI unless you turn it on; the UI makes any cloud call obvious.
- News providers receive only the query. Your principles, notes, scripts, transcripts and videos
  never go to a news provider.
- No voter profiling, persuasion scoring, or targeting by sensitive characteristics — Poly
  analyses public policy, public news and aggregate audiences only.
- No auto-posting. "Publish" means you exported it and recorded the link.
- Fact-check gate before READY; fabricated quotes/statistics are prohibited in every prompt.

## GitHub workflow

The repo ignores `.env`, `data/`, all media file types, `node_modules/`, `.venv/`. Before pushing:

```bash
git status                       # nothing under data/ or *.mp4 should appear
grep -rn "sk-" --include=*.py --include=*.ts . | grep -v node_modules   # sanity check for keys
make test && make build
```

Create the GitHub repository and push (GitHub CLI):

```bash
gh auth status || gh auth login
gh repo create Poly --private --source=. --remote=origin --push
```

Without `gh`: create an empty repo named `Poly` on github.com, then
`git remote add origin git@github.com:<you>/Poly.git && git push -u origin main`.

## Repository layout

```
backend/          FastAPI app, services, providers, jobs, Alembic, tests   (see ARCHITECTURE.md)
frontend/         Next.js app (src/app pages, src/components, src/lib/api.ts)
knowledge/        political_operating_system.md — your living principles document
scripts/          setup.sh, dev.sh
data/             (git-ignored) SQLite DB, job queue, renders, images, caches
docker-compose.yml  optional Postgres + pgvector
```
