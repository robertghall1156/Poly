"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Clapperboard, FileText, Images, Laugh, MessageSquareText, Mic, MonitorPlay, Tv } from "lucide-react";
import { api, API_BASE } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Job, MemeConcept, MemeRenderResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { JobStatus } from "@/components/JobStatus";
import { SourcePicker, sourceReady, toStudioSource, type SourceSelection, type SourceType } from "@/components/create/SourcePicker";

type Flow = "short" | "faceless" | "meme" | "carousel" | "post" | "youtube" | "podcast" | "article";

const TILES: { id: Flow; label: string; hint: string; icon: typeof FileText }[] = [
  { id: "short", label: "Short", hint: "15–60s vertical video, ~3 clicks to a draft", icon: MonitorPlay },
  { id: "faceless", label: "Faceless Video", hint: "Animated text video — no camera needed", icon: Clapperboard },
  { id: "meme", label: "Meme", hint: "Three concepts, pick one, done", icon: Laugh },
  { id: "carousel", label: "Carousel", hint: "Swipeable slides for Instagram or LinkedIn", icon: Images },
  { id: "post", label: "Post", hint: "A sharp written post", icon: MessageSquareText },
  { id: "youtube", label: "YouTube", hint: "Full script, hook and outline", icon: Tv },
  { id: "podcast", label: "Podcast", hint: "Episode outline and talking points", icon: Mic },
  { id: "article", label: "Article", hint: "Long-form written piece", icon: FileText },
];

const DEFAULT_STYLE: Record<SourceType, string> = {
  story: "news_explainer",
  position: "my_take",
  belief: "question",
  research: "text_explainer",
  video: "news_explainer",
  custom: "question",
};

function sourceFromParams(params: URLSearchParams): SourceSelection {
  const src = params.get("source");
  const id = params.get("id") ?? "";
  const types: SourceType[] = ["story", "position", "belief", "research", "video"];
  if (src && id && (types as string[]).includes(src)) return { type: src as SourceType, id, idea: "" };
  return { type: "custom", id: "", idea: "" };
}

export default function CreatePage() {
  return (
    <React.Suspense fallback={<ListSkeleton />}>
      <CreateInner />
    </React.Suspense>
  );
}

function CreateInner() {
  const params = useSearchParams();
  const router = useRouter();
  const flow = (params.get("format") as Flow | null) ?? null;
  const validFlow = flow && TILES.some((t) => t.id === flow) ? flow : null;
  const [source, setSource] = React.useState<SourceSelection>(() => sourceFromParams(params));
  React.useEffect(() => {
    setSource(sourceFromParams(params));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("source"), params.get("id")]);

  const pickFlow = (id: Flow) => {
    const qs = new URLSearchParams(params.toString());
    qs.set("format", id);
    router.replace(`/create?${qs.toString()}`);
  };

  return (
    <div>
      <PageHeader title="Create" description="Pick a format. Poly writes the first draft — you shape it from there. Nothing is ever posted automatically." />
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {TILES.map((t) => {
          const Icon = t.icon;
          const active = validFlow === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => pickFlow(t.id)}
              className={cn(
                "flex flex-col items-start gap-2 rounded-lg border p-3.5 text-left transition-colors",
                active ? "border-accent bg-accent-soft" : "border-zinc-200 bg-white hover:border-accent/60 hover:bg-accent-soft/50",
              )}
              data-testid={`tile-${t.id}`}
            >
              <Icon className={cn("h-5 w-5", active ? "text-accent-strong" : "text-secondary")} />
              <span className="text-[13.5px] font-semibold text-zinc-900">{t.label}</span>
              <span className="text-[11.5px] leading-snug text-zinc-500">{t.hint}</span>
            </button>
          );
        })}
      </div>

      {!validFlow ? <Notice>Choose a format above to start. You can begin from a story, a position, a belief, research, or a custom idea.</Notice> : null}
      {validFlow === "short" || validFlow === "faceless" ? <FacelessFlow key={validFlow} kind="faceless_video" short={validFlow === "short"} source={source} onSource={setSource} /> : null}
      {validFlow === "carousel" ? <FacelessFlow key="carousel" kind="carousel" source={source} onSource={setSource} /> : null}
      {validFlow === "meme" ? <MemeFlow source={source} onSource={setSource} /> : null}
      {validFlow === "post" || validFlow === "youtube" || validFlow === "podcast" || validFlow === "article" ? (
        <SimpleFlow key={validFlow} flow={validFlow} source={source} onSource={setSource} />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Faceless video / Short / Carousel
// ---------------------------------------------------------------------------
function FacelessFlow({ kind, short, source, onSource }: { kind: "faceless_video" | "carousel"; short?: boolean; source: SourceSelection; onSource: (s: SourceSelection) => void }) {
  const router = useRouter();
  const formats = useApi(() => api.studioFormats(), []);
  const [style, setStyle] = React.useState<string>(DEFAULT_STYLE[source.type]);
  const [styleTouched, setStyleTouched] = React.useState(false);
  const [seconds, setSeconds] = React.useState(30);
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [projectId, setProjectId] = React.useState<string | null>(null);
  const act = useAction();

  React.useEffect(() => {
    if (!styleTouched) setStyle(DEFAULT_STYLE[source.type]);
  }, [source.type, styleTouched]);

  const generate = async () => {
    const res = await act.run(() =>
      api.createFaceless({ source: toStudioSource(source), kind, format: style, target_seconds: seconds, platform: short ? "youtube_short" : undefined, background: true }),
    );
    if (res) {
      setProjectId(res.project.id);
      if (res.job) setJobId(res.job.id);
      else router.push(`/create/studio/${res.project.id}`);
    }
  };

  const onJobDone = (job: Job) => {
    if (job.status === "succeeded" && projectId) router.push(`/create/studio/${projectId}`);
  };

  const kindLabel = kind === "carousel" ? "carousel" : short ? "Short" : "faceless video";
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4">
      <ol className="space-y-4">
        <li>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">1 · Start from</p>
          <SourcePicker value={source} onChange={onSource} />
        </li>
        <li>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">2 · Style</p>
          <div className="flex flex-wrap gap-1.5">
            {(formats.data?.formats ?? []).filter((f) => f.id !== "custom").map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => {
                  setStyle(f.id);
                  setStyleTouched(true);
                }}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  style === f.id ? "border-accent bg-accent-soft text-accent-strong" : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </li>
        {kind === "faceless_video" ? (
          <li>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">3 · Length</p>
            <div className="flex gap-1.5">
              {(formats.data?.lengths ?? [15, 30, 45, 60]).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setSeconds(l)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                    seconds === l ? "border-accent bg-accent-soft text-accent-strong" : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50",
                  )}
                >
                  {l}s
                </button>
              ))}
            </div>
          </li>
        ) : null}
      </ol>
      <div className="mt-4 flex items-center gap-3">
        <Button variant="default" size="lg" onClick={generate} loading={act.busy} disabled={!sourceReady(source) || !!jobId} data-testid="generate">
          Generate
        </Button>
        <span className="text-xs text-zinc-500">Poly drafts the whole {kindLabel} — every scene stays editable.</span>
      </div>
      <ErrorNotice error={act.error} className="mt-3" />
      {jobId ? <JobStatus jobId={jobId} label={`Drafting your ${kindLabel}`} className="mt-3" onDone={onJobDone} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Meme
// ---------------------------------------------------------------------------
function MemeFlow({ source, onSource }: { source: SourceSelection; onSource: (s: SourceSelection) => void }) {
  const [concepts, setConcepts] = React.useState<MemeConcept[] | null>(null);
  const act = useAction();

  const generate = async () => {
    const res = await act.run(() => api.memeConcepts({ source: source.type === "custom" ? null : toStudioSource(source), idea: source.type === "custom" ? source.idea : "" }));
    if (res) setConcepts(res.concepts);
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">Start from</p>
      <SourcePicker value={source} onChange={onSource} />
      <div className="mt-4 flex items-center gap-3">
        <Button variant="default" size="lg" onClick={generate} loading={act.busy} disabled={!sourceReady(source)} data-testid="generate">
          {concepts ? "Regenerate" : "Generate concepts"}
        </Button>
        <span className="text-xs text-zinc-500">You get three concepts — edit any of them, then make the one you like.</span>
      </div>
      <ErrorNotice error={act.error} className="mt-3" />
      {act.busy && !concepts ? <ListSkeleton rows={1} /> : null}
      {concepts ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {concepts.map((c, i) => (
            <MemeConceptCard key={i} concept={c} source={source} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MemeConceptCard({ concept, source }: { concept: MemeConcept; source: SourceSelection }) {
  const formats = useApi(() => api.studioFormats(), []);
  const [template, setTemplate] = React.useState(concept.template);
  const [top, setTop] = React.useState(concept.top_text);
  const [bottom, setBottom] = React.useState(concept.bottom_text);
  const [caption, setCaption] = React.useState(concept.caption);
  const [result, setResult] = React.useState<MemeRenderResult | null>(null);
  const [approved, setApproved] = React.useState(false);
  const act = useAction();

  React.useEffect(() => {
    setTemplate(concept.template);
    setTop(concept.top_text);
    setBottom(concept.bottom_text);
    setCaption(concept.caption);
    setResult(null);
    setApproved(false);
  }, [concept]);

  const make = async () => {
    const r = await act.run(() =>
      api.memeRender({
        template,
        top_text: top,
        bottom_text: bottom,
        caption,
        title: concept.concept || top,
        story_id: source.type === "story" ? source.id : null,
        principle_ids: source.type === "belief" && source.id ? [source.id] : [],
      }),
    );
    if (r) setResult(r);
  };
  const approve = async () => {
    if (!result) return;
    const r = await act.run(() => api.approveImage(result.id, true));
    if (r) setApproved(true);
  };

  return (
    <div className="flex flex-col rounded-md border border-zinc-200 p-3">
      {concept.concept ? <p className="text-[13px] font-medium text-zinc-900">{concept.concept}</p> : null}
      {concept.why_it_works ? <p className="mt-0.5 text-xs text-zinc-500">{concept.why_it_works}</p> : null}
      <div className="mt-2 space-y-2">
        <Field label="Layout">
          <Select value={template} onChange={(e) => setTemplate(e.target.value)} className="w-full">
            {[...new Set([...(formats.data?.meme_templates ?? []), template])].filter((t) => t !== "custom").map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Top text">
          <Input value={top} onChange={(e) => setTop(e.target.value)} />
        </Field>
        <Field label="Bottom text">
          <Input value={bottom} onChange={(e) => setBottom(e.target.value)} />
        </Field>
        <Field label="Caption">
          <Textarea rows={2} value={caption} onChange={(e) => setCaption(e.target.value)} />
        </Field>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Button variant="default" size="sm" onClick={make} loading={act.busy}>
          {result ? "Make it again" : "Make it"}
        </Button>
      </div>
      <ErrorNotice error={act.error} className="mt-2" />
      {result ? (
        <div className="mt-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${API_BASE}${result.file_url}`} alt={top || "Meme"} className="w-full rounded border border-zinc-200" />
          <div className="mt-2 flex items-center gap-2">
            <a
              href={`${API_BASE}${result.file_url}`}
              download
              className="inline-flex h-7 items-center rounded-md border border-zinc-300 bg-white px-2.5 text-xs font-medium text-zinc-800 hover:bg-zinc-50"
            >
              Download
            </a>
            <Button size="sm" variant="accent" onClick={approve} disabled={approved} loading={act.busy}>
              {approved ? "Approved" : "Approve"}
            </Button>
          </div>
          {approved ? <p className="mt-1 text-xs text-emerald-700">Approved — saved as a draft in your Library.</p> : null}
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Post / YouTube / Podcast / Article
// ---------------------------------------------------------------------------
const SIMPLE_DEFAULT_FORMAT: Record<string, string> = { post: "x_post", youtube: "youtube", podcast: "podcast", article: "article" };
const POST_FORMATS = ["x_post", "x_thread", "facebook_post", "instagram_post", "linkedin_post"];

function SimpleFlow({ flow, source, onSource }: { flow: "post" | "youtube" | "podcast" | "article"; source: SourceSelection; onSource: (s: SourceSelection) => void }) {
  const router = useRouter();
  const [format, setFormat] = React.useState(SIMPLE_DEFAULT_FORMAT[flow]);
  const [title, setTitle] = React.useState("");
  const [extra, setExtra] = React.useState("");
  const [jobId, setJobId] = React.useState<string | null>(null);
  const act = useAction();

  const generate = async () => {
    let instructions = extra;
    if (source.type === "custom") instructions = `Base this on the following idea: ${source.idea}\n\n${extra}`.trim();
    if (source.type === "research" && source.id) {
      try {
        const notes = await api.research();
        const note = notes.find((n) => n.id === source.id);
        if (note) instructions = `Base this on this research note titled "${note.title}":\n${note.body}\n\n${extra}`.trim();
      } catch {
        // fall through with whatever instructions we have
      }
    }
    const res = await act.run(() =>
      api.generateContent({
        format,
        story_id: source.type === "story" ? source.id : null,
        brief_id: source.type === "position" ? source.id : null,
        principle_ids: source.type === "belief" && source.id ? [source.id] : [],
        title: title || null,
        extra_instructions: instructions,
        background: true,
      }),
    );
    if (res?.job) setJobId(res.job.id);
    else if (res?.item) router.push(`/library/content/${res.item.id}`);
  };

  const onJobDone = (job: Job) => {
    const id = (job.result?.content_item_id ?? job.result?.item_id ?? job.result?.id) as string | undefined;
    if (job.status === "succeeded" && id) router.push(`/library/content/${id}`);
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">Start from</p>
      <SourcePicker value={source} onChange={onSource} />
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-zinc-600 hover:text-zinc-900">More options</summary>
        <div className="mt-2 grid gap-3 md:grid-cols-2">
          {flow === "post" ? (
            <Field label="Post type">
              <Select value={format} onChange={(e) => setFormat(e.target.value)} className="w-full">
                {POST_FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f.replace(/_/g, " ")}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}
          <Field label="Title" hint="(optional)">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Leave blank and Poly proposes one" />
          </Field>
          <Field label="Anything else?" className="md:col-span-2">
            <Textarea rows={2} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Angle, tone, audience, things to avoid…" />
          </Field>
        </div>
      </details>
      <div className="mt-4 flex items-center gap-3">
        <Button variant="default" size="lg" onClick={generate} loading={act.busy} disabled={!sourceReady(source) || !!jobId} data-testid="generate">
          Generate
        </Button>
        <span className="text-xs text-zinc-500">The draft opens in your Library when it&apos;s ready.</span>
      </div>
      <ErrorNotice error={act.error} className="mt-3" />
      {jobId ? <JobStatus jobId={jobId} label="Writing your draft" className="mt-3" onDone={onJobDone} /> : null}
    </div>
  );
}
