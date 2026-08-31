import type {
  AllSettings,
  AnalyticsOverview,
  Article,
  Board,
  BookChapter,
  BookDetail,
  BookListItem,
  BookNote,
  BookProject,
  Claim,
  Clip,
  ContentItem,
  ContentListItem,
  ContentMetric,
  ContentTreeNode,
  Counterargument,
  Dashboard,
  Evidence,
  Feed,
  ImageRecord,
  IngestStatus,
  Job,
  LocalAI,
  LocalModel,
  MemeConcept,
  MemeRenderResult,
  ModelTestResult,
  PositionBrief,
  Principle,
  PrincipleDetail,
  PrincipleListItem,
  Privacy,
  ResearchNote,
  SearchResponse,
  Source,
  Story,
  StoryDetail,
  StudioFormats,
  StudioProject,
  StudioScene,
  StudioSourceIn,
  QualityCheck,
  ThinkSessionDetail,
  ThinkSessionListItem,
  TranscriptSegment,
  Video,
  VideoDetail,
  VideoFolder,
  VideoListItem,
  LocalAIStatus,
  ImageCandidate,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_POLY_API ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) {
    if (e.message === "Failed to fetch") return `Cannot reach the Poly backend at ${API_BASE}. Is it running?`;
    return e.message;
  }
  return String(e);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}/api${path}`;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init?.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(url, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) } });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    if (data && typeof data === "object" && "detail" in data) {
      const d = (data as { detail: unknown }).detail;
      detail = typeof d === "string" ? d : JSON.stringify(d);
    } else if (typeof data === "string" && data) {
      detail = data;
    }
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = (path: string) => request<void>(path, { method: "DELETE" });

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  // system
  dashboard: () => get<Dashboard>("/dashboard"),
  settings: () => get<AllSettings>("/settings"),
  patchSettings: (key: string, value: Record<string, unknown>) => patch<Record<string, unknown>>("/settings", { key, value }),
  privacy: () => get<Privacy>("/settings/privacy"),
  patchPrivacy: (body: Partial<Privacy> & { confirm_cloud?: boolean }) => patch<Privacy>("/settings/privacy", body),
  localAI: () => get<LocalAI>("/local-ai"),
  localAIStatus: () => get<LocalAIStatus>("/local-ai/status"),
  refreshLocalAI: () => post<Record<string, unknown>>("/local-ai/refresh"),
  testModel: (id: string) => post<ModelTestResult>(`/local-ai/models/${id}/test`),
  patchModel: (id: string, body: Partial<Pick<LocalModel, "tasks" | "enabled" | "priority" | "fallback_model_id" | "context_window">>) => patch<LocalModel>(`/local-ai/models/${id}`, body),
  addModel: (body: { name: string; runtime: string; endpoint: string; tasks: string[]; priority: number; context_window?: number | null; locality: string }) => post<LocalModel>("/local-ai/models", body),
  deleteModel: (id: string) => del(`/local-ai/models/${id}`),
  jobs: (params?: { status?: string; limit?: number }) => get<Job[]>(`/jobs${qs(params ?? {})}`),
  job: (id: string) => get<Job>(`/jobs/${id}`),
  retryJob: (id: string) => post<Job>(`/jobs/${id}/retry`),
  search: (q: string, types?: string) => get<SearchResponse>(`/search${qs({ q, types })}`),
  images: () => get<ImageRecord[]>("/images"),
  createImage: (body: { kind: string; params: Record<string, unknown>; content_item_id?: string | null; title?: string }) => post<ImageRecord>("/images", body),
  approveImage: (id: string, approved: boolean) => post<ImageRecord>(`/images/${id}/approve`, { approved }),
  deleteImage: (id: string) => del(`/images/${id}`),
  imageFileUrl: (id: string) => `${API_BASE}/api/images/${id}/file`,

  // stories
  stories: (params?: { status?: string; topic?: string; days?: number; min_relevance?: number; action?: string; limit?: number }) => get<Story[]>(`/stories${qs(params ?? {})}`),
  story: (id: string) => get<StoryDetail>(`/stories/${id}`),
  storyAction: (id: string, action: string) => post<Story>(`/stories/${id}/action`, { action }),
  analyzeStory: (id: string) => post<Job>(`/stories/${id}/analyze`),
  patchClaim: (id: string, body: Partial<Pick<Claim, "verification_status" | "notes" | "claim_type" | "primary_source_url">>) => patch<Claim>(`/claims/${id}`, body),
  article: (id: string) => get<Article>(`/articles/${id}`),
  feeds: () => get<Feed[]>("/feeds"),
  addFeed: (body: { name: string; url: string; provider?: string; query?: string | null; category?: string; enabled?: boolean }) => post<Feed>("/feeds", body),
  patchFeed: (id: string, body: Partial<Pick<Feed, "name" | "url" | "category" | "enabled" | "query">>) => patch<Feed>(`/feeds/${id}`, body),
  deleteFeed: (id: string) => del(`/feeds/${id}`),
  fetchFeed: (id: string) => post<Job>(`/feeds/${id}/fetch`),
  runIngest: () => post<Job>("/ingest/run"),
  ingestStatus: () => get<IngestStatus>("/ingest/status"),
  sources: () => get<Source[]>("/sources"),
  patchSource: (id: string, body: Partial<Pick<Source, "source_type" | "is_primary" | "ideology" | "reliability_notes">>) => patch<Source>(`/sources/${id}`, body),
  research: (params?: { story_id?: string; principle_id?: string }) => get<ResearchNote[]>(`/research${qs(params ?? {})}`),
  createResearch: (body: { title: string; body?: string; kind?: string; tags?: string[]; story_id?: string | null; principle_id?: string | null; content_item_id?: string | null }) => post<ResearchNote>("/research", body),
  updateResearch: (id: string, body: { title: string; body: string; kind: string; tags: string[]; story_id: string | null; principle_id: string | null; content_item_id: string | null }) => patch<ResearchNote>(`/research/${id}`, body),
  deleteResearch: (id: string) => del(`/research/${id}`),

  // principles
  principles: (params?: { category?: string; status?: string }) => get<PrincipleListItem[]>(`/principles${qs(params ?? {})}`),
  principleCategories: () => get<string[]>("/principles/categories"),
  principle: (id: string) => get<PrincipleDetail>(`/principles/${id}`),
  createPrinciple: (body: { title: string; category: string; current_position: string; rationale?: string; status?: string; confidence?: number; sort_order?: number }) => post<Principle>("/principles", body),
  patchPrinciple: (id: string, body: Partial<Pick<Principle, "title" | "category" | "current_position" | "rationale" | "status" | "confidence" | "sort_order">> & { reason_for_change?: string }) => patch<Principle>(`/principles/${id}`, body),
  retirePrinciple: (id: string) => del(`/principles/${id}`),
  addEvidence: (pid: string, body: Partial<Omit<Evidence, "id" | "principle_id" | "created_at">>) => post<Evidence>(`/principles/${pid}/evidence`, body),
  deleteEvidence: (pid: string, eid: string) => del(`/principles/${pid}/evidence/${eid}`),
  addCounter: (pid: string, body: { argument: string; source?: string; strength?: string; response?: string; unresolved_questions?: string[] }) => post<Counterargument>(`/principles/${pid}/counterarguments`, body),
  updateCounter: (pid: string, cid: string, body: { argument: string; source: string; strength: string; response: string; unresolved_questions: string[] }) => patch<Counterargument>(`/principles/${pid}/counterarguments/${cid}`, body),
  deleteCounter: (pid: string, cid: string) => del(`/principles/${pid}/counterarguments/${cid}`),
  importPrinciples: () => post<Record<string, number>>("/principles/import"),
  exportPrinciplesMarkdown: () => get<{ markdown: string }>("/principles/export/markdown"),
  exportPrinciplesFile: () => post<{ path: string }>("/principles/export"),

  // think
  thinkSessions: (status?: string) => get<ThinkSessionListItem[]>(`/think/sessions${qs({ status })}`),
  thinkSession: (id: string) => get<ThinkSessionDetail>(`/think/sessions/${id}`),
  startThink: (body: { title: string; story_id?: string | null; principle_id?: string | null; question?: string; ask_first_question?: boolean }) => post<ThinkSessionDetail>("/think/sessions", body),
  answerThink: (id: string, text: string) => post<ThinkSessionDetail>(`/think/sessions/${id}/answer`, { text }),
  briefFromThink: (id: string) => post<PositionBrief>(`/think/sessions/${id}/brief`),
  abandonThink: (id: string) => post<ThinkSessionDetail>(`/think/sessions/${id}/abandon`),
  briefs: (status?: string) => get<PositionBrief[]>(`/think/briefs${qs({ status })}`),
  brief: (id: string) => get<PositionBrief>(`/think/briefs/${id}`),
  patchBrief: (id: string, body: Partial<Omit<PositionBrief, "id" | "created_at" | "approved_at" | "status" | "markdown">>) => patch<PositionBrief>(`/think/briefs/${id}`, body),
  approveBrief: (id: string, body: { mode: string; principle_id?: string | null; title?: string | null; category?: string | null; reason?: string }) => post<{ brief: PositionBrief; principle: Principle }>(`/think/briefs/${id}/approve`, body),

  // content
  contentFormats: () => get<{ formats: string[]; statuses: string[] }>("/content/formats"),
  content: (params?: { status?: string; format?: string; story_id?: string; roots_only?: boolean; limit?: number }) => get<ContentListItem[]>(`/content${qs(params ?? {})}`),
  contentItem: (id: string) => get<ContentItem>(`/content/${id}`),
  createContent: (body: { title: string; format: string; status?: string; story_id?: string | null; principle_ids?: string[]; position_brief_id?: string | null; script?: string; parent_id?: string | null; platform?: string; publish_date?: string | null; url?: string }) => post<ContentItem>("/content", body),
  patchContent: (id: string, body: Partial<{ title: string; script: string; package: Record<string, unknown>; platform: string; publish_date: string; url: string; principle_ids: string[]; substantive_value: number; story_id: string }>) => patch<ContentItem>(`/content/${id}`, body),
  setContentStatus: (id: string, status: string, override_reason = "") => post<ContentItem>(`/content/${id}/status`, { status, override_reason }),
  deleteContent: (id: string) => del(`/content/${id}`),
  generateContent: (body: { format: string; story_id?: string | null; brief_id?: string | null; principle_ids?: string[]; parent_id?: string | null; title?: string | null; extra_instructions?: string; background?: boolean }) => post<{ job?: Job; item?: ContentItem }>("/content/generate", { background: true, ...body }),
  socialBundle: (id: string) => post<Job>(`/content/${id}/social`),
  contentTree: (id: string) => get<ContentTreeNode>(`/content/${id}/tree`),
  factCheck: (id: string) => post<Job>(`/content/${id}/fact-check`),
  resolveClaim: (cid: string, fid: string, body: { status: string; sources?: string[]; notes?: string }) => post<ContentItem>(`/content/${cid}/claims/${fid}`, body),
  board: () => get<Board>("/content/calendar/board"),
  addMetric: (id: string, body: Partial<Omit<ContentMetric, "id" | "content_item_id" | "source">>) => post<ContentMetric>(`/content/${id}/metrics`, body),
  importMetricsCsv: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ imported: number; skipped: number }>("/content/metrics/import-csv", { method: "POST", body: fd });
  },
  analytics: () => get<AnalyticsOverview>("/content/analytics/overview"),

  // videos
  videoFolders: () => get<VideoFolder[]>("/videos/folders"),
  addVideoFolder: (path: string, recursive = true) => post<{ folder: VideoFolder; job: Job }>("/videos/folders", { path, recursive }),
  scanFolder: (id: string) => post<Job>(`/videos/folders/${id}/scan`),
  removeFolder: (id: string) => del(`/videos/folders/${id}`),
  videos: (folder_id?: string) => get<VideoListItem[]>(`/videos${qs({ folder_id })}`),
  video: (id: string) => get<VideoDetail>(`/videos/${id}`),
  recentClips: (limit = 12) => get<(Clip & { video_filename: string })[]>(`/videos/clips/recent${qs({ limit })}`),
  transcribe: (id: string) => post<Job>(`/videos/${id}/transcribe`),
  discoverClips: (id: string) => post<Job>(`/videos/${id}/clips/discover`),
  createClip: (vid: string, body: { start: number; end: number; title?: string; caption?: string; platform?: string }) => post<Clip>(`/videos/${vid}/clips`, body),
  patchClip: (id: string, body: Partial<Pick<Clip, "start" | "end" | "title" | "caption" | "platform" | "status">>) => patch<Clip>(`/videos/clips/${id}`, body),
  renderClip: (id: string, body: { caption_style?: string; accent_color?: string; intro_text?: string; progress_bar?: boolean; watermark_text?: string; captions?: boolean; face_tracking?: boolean; size?: string; pad?: number }) => post<Job>(`/videos/clips/${id}/render`, body),
  clipFileUrl: (id: string) => `${API_BASE}/api/videos/clips/${id}/file`,
  clipToContent: (id: string) => post<ContentItem>(`/videos/clips/${id}/to-content`),
  thumbnailUrl: (id: string, t = 1) => `${API_BASE}/api/videos/${id}/thumbnail?t=${t}`,
  searchSegments: (vid: string, q: string) => get<TranscriptSegment[]>(`/videos/${vid}/segments/search${qs({ q })}`),

  // studio (faceless videos, carousels, memes)
  studioFormats: () => get<StudioFormats>("/studio/formats"),
  createFaceless: (body: { source: StudioSourceIn; kind?: string; format?: string | null; target_seconds?: number | null; platform?: string | null; voice_mode?: string | null; title?: string | null; extra_instructions?: string; background?: boolean }) =>
    post<{ project: StudioProject; job?: Job }>("/studio/faceless", { background: true, ...body }),
  studioProjects: (kind?: string) => get<StudioProject[]>(`/studio/projects${qs({ kind })}`),
  studioProject: (id: string) => get<StudioProject>(`/studio/projects/${id}`),
  studioByContent: (cid: string) => get<StudioProject>(`/studio/by-content/${cid}`),
  patchStudioProject: (id: string, body: Partial<{ scenes: StudioScene[]; caption: string; hashtags: string[]; voice_mode: string; tts_voice: string; music_path: string; platform: string; target_seconds: number; brand_overrides: Record<string, unknown>; sources: { label?: string; url?: string }[] }>) =>
    patch<StudioProject>(`/studio/projects/${id}`, body),
  undoScenes: (id: string) => post<StudioProject>(`/studio/projects/${id}/undo-scenes`),
  studioVariation: (id: string, variation: string) => post<Job>(`/studio/projects/${id}/variation`, { variation }),
  regenerateScene: (id: string, idx: number, instruction = "") => post<StudioProject>(`/studio/projects/${id}/scenes/${idx}/regenerate`, { instruction }),
  scenePreviewUrl: (id: string, idx: number, scale = 0.35, v: string | number = 0) => `${API_BASE}/api/studio/projects/${id}/scenes/${idx}/preview?scale=${scale}&v=${v}`,
  renderProject: (id: string) => post<Job>(`/studio/projects/${id}/render`),
  addPictures: (id: string) => post<Job>(`/studio/projects/${id}/imagery`, {}),
  searchImages: (q: string, limit = 12) => get<{ results: ImageCandidate[] }>(`/studio/images/search${qs({ q, limit })}`),
  attachSceneImage: (id: string, idx: number, candidate: ImageCandidate, treatment = "band") =>
    post<StudioProject>(`/studio/projects/${id}/scenes/${idx}/image`, { scene_index: idx, candidate, treatment }),
  projectFileUrl: (id: string) => `${API_BASE}/api/studio/projects/${id}/file`,
  slideFileUrl: (id: string, idx: number) => `${API_BASE}/api/studio/projects/${id}/slides/${idx}/file`,
  studioQuality: (id: string) => get<{ checks: QualityCheck[]; passed: boolean }>(`/studio/projects/${id}/quality`),
  studioScript: (id: string) => get<{ markdown: string }>(`/studio/projects/${id}/script`),
  memeConcepts: (body: { source?: StudioSourceIn | null; idea?: string; humor?: string }) => post<{ concepts: MemeConcept[] }>("/studio/memes/concepts", body),
  memeRender: (body: { template: string; top_text?: string; bottom_text?: string; title?: string; caption?: string; base_image?: string | null; content_item_id?: string | null; save_as_draft?: boolean; story_id?: string | null; principle_ids?: string[] }) =>
    post<MemeRenderResult>("/studio/memes/render", body),

  // book
  books: () => get<BookListItem[]>("/book"),
  book: (id: string) => get<BookDetail>(`/book/${id}`),
  patchBook: (id: string, body: Partial<Pick<BookProject, "title" | "working_titles" | "premise" | "status">>) => patch<BookProject>(`/book/${id}`, body),
  addChapter: (bid: string, body: { title: string; summary?: string; order?: number; body?: string; status?: string }) => post<BookChapter>(`/book/${bid}/chapters`, body),
  patchChapter: (id: string, body: { title: string; summary: string; order: number; body: string; status: string }) => patch<BookChapter>(`/book/chapters/${id}`, body),
  deleteChapter: (id: string) => del(`/book/chapters/${id}`),
  addBookNote: (body: { title: string; body?: string; kind?: string; book_id?: string | null; chapter_id?: string | null; story_id?: string | null; principle_id?: string | null; content_item_id?: string | null; video_id?: string | null; article_id?: string | null }) => post<BookNote>("/book/notes", body),
  patchBookNote: (id: string, body: { title: string; body?: string; kind?: string; chapter_id?: string | null }) => patch<BookNote>(`/book/notes/${id}`, body),
  deleteBookNote: (id: string) => del(`/book/notes/${id}`),
};

export type Api = typeof api;
export type { Video };
