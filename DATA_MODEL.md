# Poly — Data Model

All tables are defined in `backend/poly/models.py` (SQLAlchemy 2.0) and migrated with Alembic.
The same schema runs on SQLite (default) and PostgreSQL 16 + pgvector. JSON columns use SQLAlchemy's
portable `JSON` type; vectors use `pgvector.Vector` on Postgres and a packed-float blob on SQLite.

IDs are UUID strings. All timestamps are UTC.

## Knowledge system

| Table | Key fields |
|---|---|
| `principles` | id, title, category, current_position, rationale, status (`provisional` / `established` / `retired`), confidence (0–1), sort_order, created_at, updated_at |
| `principle_revisions` | id, principle_id, old_position, new_position, reason_for_change, created_at |
| `supporting_evidence` | id, principle_id, source, source_type, summary, url, publication_date, reliability, notes, article_id? |
| `counterarguments` | id, principle_id, argument, source, strength (`weak`/`moderate`/`strong`), response, unresolved_questions (json list) |
| `research_notes` | id, title, body, tags (json), story_id?, principle_id?, content_item_id?, created_at, updated_at |

## News intelligence

| Table | Key fields |
|---|---|
| `sources` | id, name, domain, source_type (`wire`/`newspaper`/`broadcast`/`magazine`/`government`/`think_tank`/`academic`/`blog`/`other`), is_primary, ideology (nullable; only when known and relevant), reliability_notes |
| `feeds` | id, name, url, provider (`rss`/`google_news_rss`/`brave`/`tavily`/`newsapi`), query?, enabled, category, source_id?, last_fetched_at, last_error, fetch_count |
| `articles` | id, url, canonical_url, url_hash, title, title_simhash, author, publication, source_id?, feed_id?, story_id?, published_at, fetched_at, summary, content, content_hash, language, topics (json), duplicate_of_id?, raw (json) |
| `stories` | id, title, slug, summary, status (`new`/`developing`/`continuing`/`resolved`/`ignored`), first_seen, last_updated, topics (json), relevance_score, why_it_matters, arguments (json: `{side, argument}` list), primary_sources (json), unresolved_questions (json), competing_interpretations (json), content_potential (json: `{format, angle, score}`), recommended_format, dashboard_action (`none`/`ignored`/`research`/`develop_position`/`create_content`/`save_for_book`), analysis_version, analyzed_at |
| `story_events` | id, story_id, article_id?, occurred_at, description — the story timeline |
| `claims` | id, story_id, article_id?, text, claim_type (`FACT`/`ANALYSIS`/`OPINION`/`COUNTERFACTUAL`/`PREDICTION`), supporting_passage, source_url, is_primary_source, primary_source_url, verification_status, notes |
| `story_principle_links` | id, story_id, principle_id, relation (`supports`/`challenges`/`relates`), strength (0–1), note |

## Thinking

| Table | Key fields |
|---|---|
| `think_sessions` | id, title, story_id?, principle_id?, question, status (`active`/`completed`/`approved`/`abandoned`), messages (json list of `{role, content, kind, created_at}`), principle_ids_considered (json), created_at, updated_at |
| `position_briefs` | id, think_session_id?, story_id?, issue, position, rationale, governing_principle_id?, strongest_for, strongest_against, response, factual_assumptions (json), unresolved_questions (json), policy_mechanisms (json), confidence, status (`draft`/`approved`), approved_principle_id?, created_at, approved_at |

## Content

| Table | Key fields |
|---|---|
| `content_items` | id, title, format, status (`IDEA`/`RESEARCHING`/`POSITION_DEVELOPED`/`SCRIPTING`/`RECORDED`/`EDITING`/`READY`/`PUBLISHED`), story_id?, principle_ids (json), position_brief_id?, script (text), package (json — structured generator output), source_video_id?, clip_id?, parent_id?, platform, publish_date?, url?, fact_check_status (`not_run`/`pending`/`fact_checked`/`overridden`), fact_check_override_reason?, substantive_value (0–5 owner rating), approved_at?, created_at, updated_at |
| `fact_check_claims` | id, content_item_id, text, status (`VERIFIED`/`SUPPORTED_BUT_UNCERTAIN`/`OPINION`/`COUNTERFACTUAL`/`UNVERIFIED`/`OUTDATED`), sources (json), notes, resolved |
| `content_metrics` | id, content_item_id, platform, recorded_at, views, watch_time_seconds, retention_pct, likes, comments, shares, subscribers_gained, completion_pct, source (`manual`/`csv`/`api`) |
| `images` | id, kind (`text_meme`/`quote_card`/`chart`/`infographic`/`generated`/`uploaded`/`cartoon_concept`), title, prompt, provider, params (json), path, width, height, is_generated, label (`generated`/`satire`/`photo`/`chart`), approved, content_item_id?, created_at |

## Book

| Table | Key fields |
|---|---|
| `book_projects` | id, title, working_titles (json), premise, status, created_at |
| `book_chapters` | id, book_id, title, summary, order, body, status |
| `book_notes` | id, book_id?, chapter_id?, kind (`concept`/`theme`/`chapter_idea`/`personal_story`/`research`/`excerpt`/`note`), title, body, story_id?, principle_id?, content_item_id?, video_id?, article_id?, created_at |

## Media

| Table | Key fields |
|---|---|
| `video_folders` | id, path, enabled, recursive, last_scanned_at, file_count |
| `videos` | id, folder_id, path, filename, size_bytes, duration, width, height, fps, codec, file_created_at, file_modified_at, indexed_at, transcript_status (`none`/`queued`/`running`/`done`/`failed`), transcript_provider, transcript_language, summary, topics (json), people (json), key_moments (json), fingerprint |
| `transcript_segments` | id, video_id, idx, start, end, text, words (json `[{w,s,e}]`) |
| `clips` | id, video_id, start, end, title, caption, why_it_works, score, score_breakdown (json), platform, status (`suggested`/`selected`/`rendering`/`rendered`/`failed`/`dismissed`), render_path, render_settings (json), transcript_text, created_at |

## System

| Table | Key fields |
|---|---|
| `settings` | key (pk), value (json), updated_at |
| `local_models` | id, name, runtime (`ollama`/`openai_compat`/`mlx_whisper`/`faster_whisper`/`whisper_cpp`/`local_image`), endpoint, context_window, tasks (json list of task categories), enabled, priority, fallback_model_id?, size_bytes, capabilities (json), last_ok_at, last_latency_ms, last_error, detected |
| `embeddings` | id, entity_type, entity_id, chunk_index, text, model, vector (pgvector or blob), created_at — unique (entity_type, entity_id, chunk_index) |
| `jobs` | id, kind, status (`queued`/`running`/`succeeded`/`failed`), payload (json), result (json), error, attempts, retryable, cloud_override_allowed, created_at, started_at, finished_at |

## Relationships worth knowing

- `articles.story_id` groups deduplicated articles into a story; `articles.duplicate_of_id` marks exact duplicates that are kept for provenance but hidden.
- `content_items.parent_id` builds the Content Tree (one long-form parent → many derivatives).
- `content_items.principle_ids`, `stories ↔ principles` (via `story_principle_links`) and `book_notes.*_id` columns are what make lineage searchable end-to-end.
- `embeddings` is polymorphic over (`principle`, `article`, `story`, `research_note`, `transcript_segment`, `clip`, `content_item`, `book_note`, `position_brief`).
