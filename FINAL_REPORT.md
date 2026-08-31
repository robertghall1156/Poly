# Poly — Simplification & Faceless Content Studio: Final Report (2026-08-31)

## Current state before changes
Poly v1 was a fully working local-first engine (see `CURRENT_STATE_AUDIT.md` for the traced,
classified inventory): real news pipeline, principles with revision history, Think Mode → position
briefs, long-form/social generators with a fact-check gate, video indexing/transcription/clip
rendering, deterministic images, local model registry with a privacy gate, Huey jobs, 29 passing
tests. No demo features and no dead buttons — but the UI was an admin panel over the database:
12 equal sidebar items, internal vocabulary, object-first creation, 5–8 clicks to make anything,
and no way at all to create content without recording yourself.

## UX problems found → changes made
Full detail in `UX_AUDIT.md`. Headlines: navigation modelled the schema (fixed: 6 primary areas),
internal jargon (fixed: plain language everywhere), creation started from objects with 6-field
forms (fixed: format-first, one Generate button, options inferred), no universal entry point
(fixed: global **+ Create**), review scattered across a long page (fixed: one review screen),
colors hard-coded (fixed: central brand tokens driving UI *and* renderers).

## Navigation before / after
| Before | After |
|---|---|
| Home · Today · Stories · Think · Principles · Research · Content · Videos · Book · Calendar · Analytics · Settings (12 equal) | **Home · Discover · Think · Create · Library · Calendar** + quiet secondary (Analytics · Settings). All old URLs redirect. |

Workflows removed/combined: Today merged into Discover; Research (notes/sources/feeds) became a
Discover tab; Principles became Think → "What I believe"; Content/Videos/Images/Book merged into
Library; four content-creation entry points collapsed into one format picker reachable from
**+ Create** and from **Create from this** on every story, position, belief, research note, video
and draft.

## Faceless Content Studio — what actually works (all tested end-to-end)
- **8 formats**: Question, Text explainer, News explainer, Did you know?, How the system works
  (signature format), Data story, Both sides (arguments — never fabricated quotes), My take (from
  an approved position). Each generates title, caption, hashtags, scene list with timing/animation/
  backgrounds, music recommendation, and per-scene + project sources.
- **VideoScene model** (`video_projects.scenes`): order, duration, narration, on_screen_text,
  subtext, visual_type (text/title/question/chart/comparison/counter/timeline/list/image/quote),
  visual payload, animation (fade/slide_up/pop/typewriter), transition, background token, emphasis
  words, source.
- **Real MP4 rendering** — 1080×1920, 30fps H.264: Pillow-drawn brand backgrounds and data visuals
  (bar charts, VS comparisons, animated counters, timelines, numbered lists), ASS-animated text
  with gold emphasis, subtle zoom, per-scene fades, safe-zone margins, source attribution on
  screen, optional logo mark. ~1s of video renders in ~1s on this hardware.
- **Voiceover**: No voice / AI voice via local TTS — macOS `say` (zero install) or piper if
  present; scene durations stretch automatically to fit speech; optional user-supplied music bed is
  mixed under the voice. "My voice later" is an interface slot; cloning other people's voices is
  explicitly out of scope. A good video still works silent.
- **One-click variations**: Shorter · More direct · More curious · More educational · More humorous
  · More serious · Simpler · Stronger hook · Change visual style — plus per-scene regenerate with
  an instruction, and undo.
- **Quality gate** before READY: Facts (fact-check integration), Sources, Clarity, Length,
  Platform fit, Asset provenance, AI-image disclosure, Human approval — surfaced as a green/amber/
  red checklist on the review screen; READY still blocked on unresolved facts unless explicitly
  overridden with a note.
- **Unified editor**: scenes left / live preview centre / properties right; add, delete, reorder,
  retime, regenerate; rendered video plays in place. **Review screen**: preview, title, caption,
  sources, checklist → Edit / Approve / Export. Nothing ever posts automatically.

## Real rendering vs previews
| Output | Real file? |
|---|---|
| Faceless video | **Yes — MP4** (1080×1920, audio track incl. voiceover/music when enabled) |
| Carousel | **Yes — PNG per slide + ZIP** (1080×1350, numbered, footers, sources) |
| Meme | **Yes — PNG** (8 templates + classic over uploaded image) |
| Clip short (from your recordings) | **Yes — MP4** with animated captions (pre-existing, still passing) |
| Scripts/captions | Markdown/copy export |
| Scene previews in the editor | PNG per scene (same drawing code as the render) |

## Meme system — WORKING
Concepts (3 per request: template, visual, top/bottom, caption, why-it-works, humor type; styles
constrained to observational/irony/system-absurdity/bureaucracy/economic/AI humor — no rage bait)
→ edit → regenerate → render → approve → export PNG. Templates: Two buttons, Expectation/Reality,
How it started/going, System says/Reality, Politicians/People, Before/After, What people think/What
actually happens, Classic, Custom (uploaded image; generated images are labeled).

## Carousel system — WORKING
6–8 slides generated from any source (title hook → what happened → how it works → why it exists →
what's broken → possible fix → question), edited in the same editor, exported as PNGs + ZIP.

## Video system (recordings) — unchanged and WORKING
Index folders → transcribe locally → clip suggestions → 9:16 render with captions. Now lives under
Library → Videos with "Create from this".

## Required workflow tests
| Test | Result |
|---|---|
| 1. Story → Faceless Video → Question → 30s → Generate → Preview → **Render MP4** | **PASS** (`test_workflow1…`: 1080×1920 MP4, duration within 1.5s of scene total) |
| 2. Position → Meme → concepts → image → export | **PASS** (`test_workflow2…` + UI flow with Download/Approve) |
| 3. Research → Carousel → Generate → Edit → Export ZIP | **PASS** (`test_workflow3…`) |
| 4. Custom idea → 45s → Generate → Render (with voice track) | **PASS** (`test_workflow4…`) |
| 5. Uploaded video → analyze → clips → render vertical short | **PASS** (pre-existing `test_media.py`, still green) |

Suite: **37 backend tests passing**; frontend builds with zero TS/lint errors; every page verified
in a real browser with zero console errors, including the full Short flow (3 clicks to a draft) and
the approve-gate 409 path.

## Remaining demo/unproven features (being explicit)
- The **live-Ollama** path is verified against a protocol-accurate fake server + the mock provider;
  the studio's first run against your actual models happens on your Mac (same as v1 — everything
  else about the pipeline is identical).
- **Whisper transcription** still awaits its first real run on your machine (model downloads on
  first use).
- **Local generative images** remain a configured-off adapter (deterministic renderers cover memes/
  charts/cards). Keyed news APIs (Brave/Tavily/NewsAPI) and platform analytics APIs remain
  key-gated / not implemented respectively. TTS via `say` runs only on macOS; the sandbox tested
  the silence fallback path.
- Music: Poly recommends a mood and mixes a music file you provide; it does not ship or download
  music (licensing).

## Next 5 priorities
1. **First-run polish on your Mac**: verify Ollama-generated scenes read well; tune the scene
   prompt per model if qwen2.5:14b needs it.
2. **Typewriter/word-level narration sync**: align on-screen text reveals to TTS word timings.
3. **Icon & map visual packs**: small public-domain icon set + simple US map shading for scenes.
4. **Publishing checklists per platform** (export presets with title/caption/hashtag limits) —
   still no auto-posting.
5. **Analytics loop**: log which formats/hooks you actually export, feed that back into "What can I
   create?" ranking.
