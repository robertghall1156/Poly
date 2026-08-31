// Interfaces matching the FastAPI backend responses (see backend/poly/api/*.py and models.py).

export type JSONValue = string | number | boolean | null | JSONValue[] | { [k: string]: JSONValue };

// ---- jobs ----
export type JobStatusValue = "queued" | "running" | "succeeded" | "failed" | string;
export interface Job {
  id: string;
  kind: string;
  status: JobStatusValue;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  error: string | null;
  attempts: number;
  retryable: boolean;
  cloud_override_allowed: boolean;
  progress: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

// ---- privacy / settings ----
export interface Privacy {
  local_ai_only: boolean;
  allow_internet_research: boolean;
  allow_cloud_ai: boolean;
  cloud_ai_permitted: boolean;
}

export interface Runtime {
  runtime: string;
  endpoint: string;
  running: boolean;
  version: string;
  model_count: number;
  error: string;
}

export interface FfmpegStatus {
  ffmpeg: string | null;
  ffprobe: string | null;
  ok: boolean;
}

export interface TranscriptionRecommendation {
  runtime: string;
  command: string;
  why: string;
  default_model: string;
}

export interface NewsSettings {
  topic_preferences: string[];
  max_articles_per_feed: number;
  relevance_threshold: number;
  lookback_days: number;
}
export interface MediaSettings {
  transcription_mode: string;
  transcription_model: string;
  default_video_size: string;
  caption_style: string;
  face_tracking: boolean;
}
export interface ContentSettings {
  default_platforms: string[];
  brand_name: string;
  watermark_text: string;
  watermark_path: string;
  primary_color: string;
  accent_color: string;
}
export interface GithubSettings {
  repo: string;
  owner: string;
  default_branch: string;
}
export interface EnvInfo {
  database: string;
  database_url_masked: string;
  pgvector: boolean;
  data_dir: string;
  ffmpeg: FfmpegStatus;
  ollama_url: string;
  openai_compat_urls: string[];
  anthropic_key_present: boolean;
  openai_key_present: boolean;
  brave_key_present: boolean;
  tavily_key_present: boolean;
  newsapi_key_present: boolean;
  daily_ingest: string;
  platform: string;
  apple_silicon: boolean;
  transcription_recommendation: TranscriptionRecommendation;
}
export interface LastIngest {
  at?: string;
  feeds?: number;
  feeds_ok?: number;
  feeds_failed?: number;
  seen?: number;
  inserted?: number;
  duplicates?: number;
  old?: number;
  analyzed?: number;
  error_count?: number;
}
export interface AllSettings {
  news: NewsSettings;
  media: MediaSettings;
  content: ContentSettings;
  github: GithubSettings;
  ai: { task_overrides: Record<string, string> };
  detected_runtimes: Runtime[];
  last_detection: string | null;
  last_ingest: LastIngest;
  privacy: Privacy;
  env: EnvInfo;
  [k: string]: unknown;
}

export interface LocalModel {
  id: string;
  name: string;
  runtime: string;
  endpoint: string;
  context_window: number | null;
  tasks: string[];
  enabled: boolean;
  priority: number;
  fallback_model_id: string | null;
  size_bytes: number | null;
  capabilities: Record<string, unknown>;
  last_ok_at: string | null;
  last_latency_ms: number | null;
  last_error: string | null;
  detected: boolean;
  locality: string;
}
export interface ImageProviderStatus {
  configured: boolean;
  kind: string;
  endpoint: string;
  available: boolean;
  deterministic: boolean;
}
export interface LocalAI {
  runtimes: Runtime[];
  models: LocalModel[];
  assignments: Record<string, string | null>;
  task_categories: string[];
  ffmpeg: FfmpegStatus;
  image_provider: ImageProviderStatus;
  last_detection: string | null;
}
export interface ModelTestResult {
  ok: boolean;
  detail?: string;
  latency_ms?: number;
  [k: string]: unknown;
}

// ---- search ----
export interface SearchHit {
  entity_type: string;
  entity_id: string;
  title: string;
  snippet: string;
  score: number;
  keyword_rank: number | null;
  vector_rank: number | null;
  meta: Record<string, unknown> | null;
}
export interface SearchResponse {
  query: string;
  hits: SearchHit[];
}

// ---- principles ----
export interface Principle {
  id: string;
  title: string;
  category: string;
  current_position: string;
  rationale: string;
  status: "provisional" | "established" | "retired" | string;
  confidence: number;
  sort_order: number;
  created_at: string;
  updated_at: string;
}
export interface PrincipleListItem extends Principle {
  evidence_count: number;
  counterargument_count: number;
  revision_count: number;
  story_count: number;
}
export interface PrincipleRevision {
  id: string;
  principle_id: string;
  old_position: string;
  new_position: string;
  old_status: string | null;
  new_status: string | null;
  reason_for_change: string;
  created_at: string;
}
export interface Evidence {
  id: string;
  principle_id: string;
  source: string;
  source_type: string;
  summary: string;
  url: string;
  publication_date: string | null;
  reliability: string;
  notes: string;
  article_id: string | null;
  created_at: string;
}
export interface Counterargument {
  id: string;
  principle_id: string;
  argument: string;
  source: string;
  strength: string;
  response: string;
  unresolved_questions: string[];
  created_at: string;
}
export interface PrincipleDetail extends Principle {
  revisions: PrincipleRevision[];
  evidence: Evidence[];
  counterarguments: Counterargument[];
  stories: { story_id: string; title: string; relation: string; strength: number; last_updated: string }[];
  content: ContentRef[];
  briefs: { id: string; issue: string; status: string; created_at: string }[];
}

// ---- stories ----
export interface StoryArgument {
  side: string;
  argument: string;
  [k: string]: unknown;
}
export interface PrimarySource {
  title?: string;
  url?: string;
  publication?: string;
  [k: string]: unknown;
}
export interface ContentPotential {
  format?: string;
  angle?: string;
  score?: number;
  [k: string]: unknown;
}
export interface StoryPrincipleRef {
  id: string;
  title: string;
  relation: string;
  strength: number;
  note?: string;
}
export interface StoryRowData {
  id: string;
  title: string;
  summary: string;
  why_it_matters: string;
  relevance_score: number;
  topics: string[];
  status: string;
  last_updated: string;
  article_count: number;
  principles: StoryPrincipleRef[];
  arguments: StoryArgument[];
  primary_sources: PrimarySource[];
  content_potential: ContentPotential[];
  recommended_format: string;
  dashboard_action: string;
  analysis_source: string;
}
export interface Story extends StoryRowData {
  slug: string;
  first_seen: string;
  unresolved_questions: string[];
  competing_interpretations: string[];
  analysis_version: number;
  analyzed_at: string | null;
  keywords: string[];
  duplicate_count: number;
  publications: string[];
  claim_count: number;
}
export interface Source {
  id: string;
  name: string;
  domain: string;
  source_type: string;
  is_primary: boolean;
  ideology: string | null;
  reliability_notes: string;
}
export interface Article {
  id: string;
  url: string;
  canonical_url: string;
  title: string;
  author: string | null;
  publication: string;
  source_id: string | null;
  feed_id: string | null;
  story_id: string | null;
  published_at: string | null;
  fetched_at: string;
  summary: string;
  language: string;
  topics: string[];
  duplicate_of_id: string | null;
  source: Source | null;
}
export interface Claim {
  id: string;
  story_id: string;
  article_id: string | null;
  text: string;
  claim_type: string;
  supporting_passage: string;
  source_url: string;
  publication: string;
  is_primary_source: boolean;
  primary_source_url: string;
  verification_status: string;
  notes: string;
  created_at: string;
}
export interface StoryEvent {
  id: string;
  story_id: string;
  article_id: string | null;
  occurred_at: string;
  kind: string;
  description: string;
}
export interface ResearchNote {
  id: string;
  title: string;
  body: string;
  kind: string;
  tags: string[];
  story_id: string | null;
  principle_id: string | null;
  content_item_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface BookNote {
  id: string;
  book_id: string | null;
  chapter_id: string | null;
  kind: string;
  title: string;
  body: string;
  story_id: string | null;
  principle_id: string | null;
  content_item_id: string | null;
  video_id: string | null;
  article_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface ContentRef {
  id: string;
  title: string;
  format: string;
  status?: string;
}
export interface StoryDetail extends Story {
  articles: Article[];
  claims: Claim[];
  events: StoryEvent[];
  think_sessions: { id: string; title: string; status: string; created_at: string }[];
  content: ContentRef[];
  notes: ResearchNote[];
  book_notes: BookNote[];
}

export interface Feed {
  id: string;
  name: string;
  url: string;
  provider: string;
  query: string | null;
  enabled: boolean;
  category: string;
  source_id: string | null;
  last_fetched_at: string | null;
  last_error: string | null;
  fetch_count: number;
  source: Source | null;
  article_count: number;
}
export interface IngestStatus {
  last_ingest: LastIngest;
  providers: { name: string; requires_key: boolean; available: boolean }[];
  story_count: number;
  article_count: number;
}

// ---- think ----
export interface ThinkMessage {
  role: "assistant" | "user" | string;
  content: string;
  kind?: string;
  note?: string;
  created_at?: string;
}
export interface ThinkSession {
  id: string;
  title: string;
  story_id: string | null;
  principle_id: string | null;
  question: string;
  status: "active" | "completed" | "abandoned" | string;
  messages: ThinkMessage[];
  principle_ids_considered: string[];
  model_used: string;
  created_at: string;
  updated_at: string;
}
export interface ThinkSessionListItem extends ThinkSession {
  exchanges: number;
  brief_ids: string[];
}
export interface ThinkSessionDetail extends ThinkSession {
  briefs: PositionBrief[];
  principles_considered: { id: string; title: string; category: string }[];
}
export interface PositionBrief {
  id: string;
  think_session_id: string | null;
  story_id: string | null;
  issue: string;
  position: string;
  rationale: string;
  governing_principle_id: string | null;
  governing_principle_text: string;
  strongest_for: string;
  strongest_against: string;
  response: string;
  factual_assumptions: string[];
  unresolved_questions: string[];
  policy_mechanisms: string[];
  confidence: number;
  status: string;
  approved_principle_id: string | null;
  created_at: string;
  approved_at: string | null;
  markdown?: string;
}

// ---- content ----
export interface OutlineSection {
  section: string;
  notes?: string;
  [k: string]: unknown;
}
export interface SocialPackage {
  posts?: string[];
  thread?: string[];
  quote_cards?: string[];
  short_video_ideas?: string[];
  hooks?: string[];
  titles?: string[];
  thumbnail_text?: string[];
  meme_concepts?: string[];
  [k: string]: unknown;
}
export interface ContentPackage {
  working_title?: string;
  alternative_titles?: string[];
  hook?: string;
  opening_30s?: string;
  thesis?: string;
  outline?: OutlineSection[];
  research_needed?: string[];
  arguments?: string[];
  counterarguments?: string[];
  examples?: string[];
  evidence?: string[];
  transitions?: string[];
  conclusion?: string;
  call_to_discussion?: string;
  show_notes?: string;
  sources?: string[];
  social?: SocialPackage;
  [k: string]: unknown;
}
export interface FactCheckClaim {
  id: string;
  content_item_id: string;
  text: string;
  status: string;
  sources: string[];
  notes: string;
  resolved: boolean;
  created_at: string;
}
export interface ContentMetric {
  id: string;
  content_item_id: string;
  platform: string;
  recorded_at: string;
  views: number;
  watch_time_seconds: number;
  retention_pct: number | null;
  likes: number;
  comments: number;
  shares: number;
  subscribers_gained: number;
  completion_pct: number | null;
  source: string;
}
export interface ContentItemBase {
  id: string;
  title: string;
  format: string;
  status: string;
  story_id: string | null;
  principle_ids: string[];
  position_brief_id: string | null;
  script: string;
  source_video_id: string | null;
  clip_id: string | null;
  parent_id: string | null;
  platform: string;
  publish_date: string | null;
  url: string;
  fact_check_status: string;
  fact_check_override_reason: string;
  substantive_value: number | null;
  approved_at: string | null;
  generation_meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
export interface ContentListItem extends ContentItemBase {
  script_preview: string;
  child_count: number;
  unresolved_claims: number;
}
export interface Lineage {
  parents: ContentRef[];
  story: { id: string; title: string } | null;
  brief: { id: string; issue: string } | null;
  principles: { id: string; title: string }[];
  source_video_id: string | null;
  clip_id: string | null;
  children: ContentRef[];
}
export interface ContentItem extends ContentItemBase {
  package: ContentPackage;
  children: ContentRef[];
  fact_check_claims: FactCheckClaim[];
  metrics: ContentMetric[];
  lineage: Lineage;
}
export interface ContentTreeNode {
  id: string;
  title: string;
  format: string;
  status: string;
  platform: string;
  children: ContentTreeNode[];
}
export interface BoardCard {
  id: string;
  title: string;
  format: string;
  platform: string;
  publish_date: string | null;
  parent_id: string | null;
  fact_check_status: string;
  url: string;
}
export type Board = Record<string, BoardCard[]>;
export interface AnalyticsItem {
  id: string;
  title: string;
  format: string;
  platform: string;
  publish_date: string | null;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  watch_time_seconds: number;
  retention_pct: number | null;
  completion_pct: number | null;
  engagement: number;
  substantive_value: number;
  verified_claims: number;
  total_claims: number;
  quadrant?: string;
}
export interface AnalyticsOverview {
  items: AnalyticsItem[];
  published_count: number;
  with_metrics: number;
}

// ---- images ----
export interface ImageRecord {
  id: string;
  kind: string;
  title: string;
  prompt: string;
  provider: string;
  params: Record<string, unknown>;
  path: string;
  width: number;
  height: number;
  is_generated: boolean;
  label: string;
  approved: boolean;
  content_item_id: string | null;
  created_at: string;
}

// ---- videos ----
export interface VideoFolder {
  id: string;
  path: string;
  enabled: boolean;
  recursive: boolean;
  last_scanned_at: string | null;
  file_count: number;
  created_at: string;
  video_count: number;
  exists: boolean;
}
export interface Video {
  id: string;
  folder_id: string;
  path: string;
  filename: string;
  size_bytes: number;
  duration: number;
  width: number;
  height: number;
  fps: number;
  codec: string;
  has_audio: boolean;
  file_created_at: string | null;
  file_modified_at: string | null;
  indexed_at: string;
  transcript_status: string;
  transcript_provider: string;
  transcript_language: string;
  transcript_error: string | null;
  summary: string;
  topics: string[];
  people: string[];
  key_moments: { t?: number; time?: number; start?: number; label?: string; description?: string; [k: string]: unknown }[];
  fingerprint: string;
  missing: boolean;
}
export interface VideoListItem extends Video {
  clip_count: number;
  segment_count: number;
}
export interface TranscriptWord {
  w: string;
  s: number;
  e: number;
}
export interface TranscriptSegment {
  id: string;
  video_id: string;
  idx: number;
  start: number;
  end: number;
  text: string;
  words: TranscriptWord[];
}
export interface Clip {
  id: string;
  video_id: string;
  start: number;
  end: number;
  title: string;
  caption: string;
  why_it_works: string;
  score: number;
  score_breakdown: Record<string, number>;
  platform: string;
  status: string;
  render_path: string;
  render_settings: Record<string, unknown>;
  render_error: string | null;
  transcript_text: string;
  story_id: string | null;
  created_at: string;
}
export interface VideoDetail extends Video {
  segments: TranscriptSegment[];
  clips: Clip[];
  exists: boolean;
  content: ContentRef[];
}

// ---- book ----
export interface BookProject {
  id: string;
  title: string;
  working_titles: string[];
  premise: string;
  status: string;
  created_at: string;
  updated_at: string;
}
export interface BookListItem extends BookProject {
  chapter_count: number;
  note_count: number;
}
export interface BookChapter {
  id: string;
  book_id: string;
  title: string;
  summary: string;
  order: number;
  body: string;
  status: string;
  created_at: string;
  updated_at: string;
  note_count?: number;
}
export interface BookNoteLinks {
  story?: { id: string; title: string };
  principle?: { id: string; title: string };
  content?: { id: string; title: string; format: string };
  video?: { id: string; filename: string };
}
export interface BookNoteWithLinks extends BookNote {
  links: BookNoteLinks;
}
export interface BookDetail extends BookProject {
  chapters: BookChapter[];
  notes: BookNoteWithLinks[];
}

// ---- dashboard ----
export interface Dashboard {
  generated_at: string;
  counts: { stories_3d: number; principles: number; videos: number; content: number };
  last_ingest: LastIngest;
  today: StoryRowData[];
  think_about: StoryRowData[];
  create: StoryRowData[];
  continue: {
    think_sessions: { id: string; title: string; updated_at: string; exchanges: number }[];
    briefs: { id: string; issue: string; confidence: number }[];
    content: ContentRef[];
  };
  recent_clips: {
    id: string;
    title: string;
    video_id: string;
    video: string;
    start: number;
    end: number;
    score: number;
    status: string;
    platform: string;
  }[];
  privacy: Privacy;
}

// ---- studio (faceless videos, carousels, memes) ----
export interface SceneVisual {
  labels?: string[];
  values?: number[];
  unit?: string;
  title?: string;
  source?: string;
  from?: number;
  to?: number;
  prefix?: string;
  suffix?: string;
  label?: string;
  left?: { label?: string; value?: string };
  right?: { label?: string; value?: string };
  points?: { label?: string; text?: string }[];
  items?: string[];
  [k: string]: unknown;
}
export interface StudioScene {
  order?: number;
  duration: number;
  narration: string;
  on_screen_text: string;
  subtext: string;
  visual_type: string;
  visual: SceneVisual;
  animation: string;
  transition?: string;
  background: string;
  emphasis: string[];
  source: string;
  [k: string]: unknown;
}
export interface StudioSource {
  label?: string;
  url?: string;
  [k: string]: unknown;
}
export interface StudioProject {
  id: string;
  content_item_id: string;
  kind: "faceless_video" | "carousel" | string;
  format: string;
  target_seconds: number;
  platform: string;
  voice_mode: "none" | "tts" | string;
  tts_voice: string;
  music_path: string;
  music_recommendation: string;
  scenes: StudioScene[];
  previous_scenes: StudioScene[];
  sources: StudioSource[];
  caption: string;
  hashtags: string[];
  brand_overrides: Record<string, unknown>;
  render_status: "none" | "queued" | "rendering" | "done" | "failed" | string;
  render_path: string;
  render_error: string | null;
  generation_meta: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  // enriched by the API
  title: string;
  status: string;
  fact_check_status: string;
  content_item: { id: string; title: string; status: string; format: string; approved_at: string | null };
  total_seconds: number;
  formats: Record<string, string>;
}
export interface StudioFormatDef {
  id: string;
  label: string;
  default_seconds: number;
}
export interface TtsStatus {
  available: boolean;
  engine?: string;
  detail?: string;
  [k: string]: unknown;
}
export interface StudioFormats {
  formats: StudioFormatDef[];
  lengths: number[];
  variations: string[];
  meme_templates: string[];
  tts: TtsStatus;
}
export interface QualityCheck {
  check: string;
  status: "pass" | "warn" | "fail" | string;
  detail: string;
}
export interface StudioSourceIn {
  story_id?: string | null;
  brief_id?: string | null;
  principle_id?: string | null;
  research_note_id?: string | null;
  video_id?: string | null;
  idea?: string;
}
export interface MemeConcept {
  template: string;
  concept?: string;
  visual?: string;
  top_text: string;
  bottom_text: string;
  caption: string;
  why_it_works?: string;
  humor_type?: string;
  [k: string]: unknown;
}
export interface MemeRenderResult extends ImageRecord {
  content_item_id: string | null;
  file_url: string;
}

export interface LocalAIStatus {
  runtimes: { runtime: string; endpoint: string; running: boolean }[];
  any_runtime_running: boolean;
  chat_ready: boolean;
  assignments: Record<string, string | null>;
  hint: string;
  transcription_ready: boolean;
}
