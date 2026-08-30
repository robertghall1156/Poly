"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Clip, TranscriptSegment, VideoDetail } from "@/lib/types";
import { cn, fmtBytes, fmtDateTime, fmtDuration, fmtTimestamp, humanize, labelFormat } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "@/components/ui/notice";
import { KV, PageHeader, Panel, Section } from "@/components/ui/section";
import { StatusBadge } from "@/components/badges";
import { JobStatus } from "@/components/JobStatus";

const CLIP_PLATFORMS = ["youtube_short", "tiktok", "instagram_reel"];

export default function VideoDetailPage() {
  return (
    <React.Suspense fallback={<ListSkeleton rows={5} />}>
      <VideoInner />
    </React.Suspense>
  );
}

function VideoInner() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const video = useApi(() => api.video(id), [id]);
  const [thumbT, setThumbT] = React.useState(Number(params.get("t") ?? 1) || 1);
  const [jobs, setJobs] = React.useState<{ transcribe?: string; discover?: string }>({});
  const [manual, setManual] = React.useState({ start: "0", end: "30", title: "" });
  const act = useAction();
  const v = video.data;

  const transcribe = async () => {
    const j = await act.run(() => api.transcribe(id));
    if (j) setJobs((s) => ({ ...s, transcribe: j.id }));
  };
  const discover = async () => {
    const j = await act.run(() => api.discoverClips(id));
    if (j) setJobs((s) => ({ ...s, discover: j.id }));
  };
  const createManual = async () => {
    const r = await act.run(() => api.createClip(id, { start: Number(manual.start), end: Number(manual.end), title: manual.title }));
    if (r) {
      setManual({ start: "0", end: "30", title: "" });
      video.reload();
    }
  };

  if (video.loading) return <ListSkeleton rows={5} />;
  if (video.error || !v) return <ErrorNotice error={video.error ?? "Not found"} />;

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/videos" className="hover:text-zinc-800">
          Videos
        </Link>{" "}
        / {v.filename}
      </div>
      <PageHeader
        title={v.filename}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={v.transcript_status} />
            <span>
              {fmtDuration(v.duration)} · {v.width}×{v.height} · {v.fps} fps · {v.codec} · {fmtBytes(v.size_bytes)}
            </span>
            {!v.exists || v.missing ? <Badge variant="danger">file missing</Badge> : null}
          </span>
        }
        actions={
          <>
            <Button onClick={transcribe} loading={act.busy} disabled={!v.exists}>
              {v.transcript_status === "done" ? "Re-transcribe" : "Transcribe"}
            </Button>
            <Button variant="default" onClick={discover} loading={act.busy} disabled={v.transcript_status !== "done"} title={v.transcript_status !== "done" ? "Transcribe first" : ""}>
              Find clip opportunities
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {jobs.transcribe ? (
        <div className="mb-3 space-y-2">
          <JobStatus jobId={jobs.transcribe} label="Transcription (local)" onDone={() => video.reload()} />
        </div>
      ) : null}
      {v.transcript_status === "failed" || v.transcript_error ? (
        <Notice kind="error" className="mb-3">
          Transcription failed: {v.transcript_error ?? "unknown error"}. Install a local transcription runtime (see Settings → Local AI for the recommended command) and try again.
        </Notice>
      ) : null}
      {jobs.discover ? <JobStatus jobId={jobs.discover} label="Clip discovery" className="mb-3" onDone={() => video.reload()} /> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <Section title="Clip candidates" description="Sorted by score. Edit ranges, render 9:16 shorts, and push rendered clips into Content.">
            {v.clips.length === 0 ? <EmptyState title="No clips yet.">Run “Find clip opportunities” after transcribing, or create a manual clip below.</EmptyState> : null}
            <div className="space-y-3">
              {v.clips.map((c) => (
                <ClipCard key={c.id} clip={c} video={v} onChange={() => video.reload()} />
              ))}
            </div>
            <div className="mt-3 rounded-md border border-dashed border-zinc-300 bg-white p-3">
              <p className="mb-2 text-xs font-medium text-zinc-600">Manual clip</p>
              <div className="grid gap-2 md:grid-cols-[6rem_6rem_1fr_auto]">
                <Input type="number" step="0.1" min={0} value={manual.start} onChange={(e) => setManual({ ...manual, start: e.target.value })} placeholder="start s" />
                <Input type="number" step="0.1" min={0} value={manual.end} onChange={(e) => setManual({ ...manual, end: e.target.value })} placeholder="end s" />
                <Input value={manual.title} onChange={(e) => setManual({ ...manual, title: e.target.value })} placeholder="Title" />
                <Button variant="default" onClick={createManual} loading={act.busy} disabled={Number(manual.end) <= Number(manual.start)}>
                  Create clip
                </Button>
              </div>
            </div>
          </Section>

          <Section title="Transcript" description={v.segments.length ? `${v.segments.length} segments · ${v.transcript_provider} · ${v.transcript_language}` : undefined}>
            <TranscriptView video={v} onSeek={(t) => setThumbT(Math.max(1, Math.floor(t)))} />
          </Section>
        </div>

        <aside className="space-y-3">
          <Panel>
            {v.exists ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={api.thumbnailUrl(v.id, thumbT)} alt={`Frame at ${fmtTimestamp(thumbT)}`} className="w-full rounded bg-zinc-100" />
            ) : (
              <div className="flex aspect-video items-center justify-center rounded bg-zinc-100 text-xs text-zinc-500">File missing</div>
            )}
            <div className="mt-2 flex items-center gap-2">
              <input type="range" min={0} max={Math.max(1, Math.floor(v.duration))} value={thumbT} onChange={(e) => setThumbT(Number(e.target.value))} className="flex-1" />
              <span className="font-mono text-[11px] text-zinc-500">{fmtTimestamp(thumbT)}</span>
            </div>
          </Panel>
          <Panel title="Metadata">
            <dl>
              <KV label="Path">
                <span className="break-all font-mono text-[11px]">{v.path}</span>
              </KV>
              <KV label="File created">{fmtDateTime(v.file_created_at)}</KV>
              <KV label="Indexed">{fmtDateTime(v.indexed_at)}</KV>
              <KV label="Audio">{v.has_audio ? "yes" : "no"}</KV>
              <KV label="Fingerprint">
                <span className="font-mono text-[11px] text-zinc-500">{v.fingerprint.slice(0, 16)}</span>
              </KV>
            </dl>
          </Panel>
          <Panel title="Summary">
            {v.summary ? <p className="text-[13px] text-zinc-800">{v.summary}</p> : <p className="text-xs text-zinc-400">No summary yet — generated during transcription with a local model.</p>}
            {v.topics.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {v.topics.map((t) => (
                  <Badge key={t}>{t}</Badge>
                ))}
              </div>
            ) : null}
            {v.people.length ? <p className="mt-2 text-xs text-zinc-600">People: {v.people.join(", ")}</p> : null}
            {v.key_moments.length ? (
              <ul className="mt-2 space-y-1 text-xs">
                {v.key_moments.map((m, i) => {
                  const t = Number(m.t ?? m.time ?? m.start ?? 0);
                  return (
                    <li key={i}>
                      <button type="button" className="font-mono text-accent-strong hover:underline" onClick={() => setThumbT(Math.floor(t))}>
                        {fmtTimestamp(t)}
                      </button>{" "}
                      {String(m.label ?? m.description ?? "")}
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </Panel>
          {v.content.length ? (
            <Panel title="Content from this video">
              <ul className="space-y-1 text-[13px]">
                {v.content.map((c) => (
                  <li key={c.id}>
                    <Link href={`/content/${c.id}`} className="text-zinc-900 hover:text-accent-strong">
                      {c.title}
                    </Link>{" "}
                    <span className="text-[11px] text-zinc-400">{labelFormat(c.format)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function TranscriptView({ video, onSeek }: { video: VideoDetail; onSeek: (t: number) => void }) {
  const [q, setQ] = React.useState("");
  const [hits, setHits] = React.useState<TranscriptSegment[] | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  React.useEffect(() => {
    const term = q.trim();
    if (!term) {
      setHits(null);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const r = await api.searchSegments(video.id, term);
        if (!cancelled) {
          setHits(r);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q, video.id]);
  const list = hits ?? video.segments;
  if (video.segments.length === 0) return <EmptyState title="No transcript.">Transcription runs locally with word timestamps.</EmptyState>;
  return (
    <div>
      <Input placeholder="Search transcript" value={q} onChange={(e) => setQ(e.target.value)} className="mb-2 max-w-sm" />
      <ErrorNotice error={err} className="mb-2" />
      {hits ? <p className="mb-1 text-xs text-zinc-500">{hits.length} matching segments</p> : null}
      <div className="max-h-[32rem] overflow-y-auto rounded-md border border-zinc-200 bg-white">
        {list.map((s) => (
          <div key={s.id} className="flex gap-3 border-b border-zinc-100 px-3 py-1.5 last:border-b-0">
            <button type="button" onClick={() => onSeek(s.start)} className="shrink-0 font-mono text-[11px] text-accent-strong hover:underline">
              {fmtTimestamp(s.start)}
            </button>
            <p className="text-[13px] text-zinc-800">{s.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreBars({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown).filter(([k]) => k !== "total");
  if (!entries.length) return null;
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
      {entries.map(([k, val]) => (
        <div key={k} className="flex items-center gap-2 text-[11px]">
          <span className="w-24 truncate text-zinc-500">{humanize(k)}</span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-200">
            <span className="block h-full bg-accent" style={{ width: `${Math.round(Math.max(0, Math.min(1, val)) * 100)}%` }} />
          </span>
          <span className="w-6 text-right font-mono text-zinc-500">{Math.round(val * 100)}</span>
        </div>
      ))}
    </div>
  );
}

function ClipCard({ clip, video, onChange }: { clip: Clip; video: VideoDetail; onChange: () => void }) {
  const [edit, setEdit] = React.useState(false);
  const [f, setF] = React.useState({ start: String(clip.start), end: String(clip.end), title: clip.title, caption: clip.caption, platform: clip.platform });
  const [renderOpen, setRenderOpen] = React.useState(false);
  const [renderJob, setRenderJob] = React.useState<string | null>(null);
  const [contentId, setContentId] = React.useState<string | null>(null);
  const act = useAction();
  const save = async () => {
    const r = await act.run(() => api.patchClip(clip.id, { start: Number(f.start), end: Number(f.end), title: f.title, caption: f.caption, platform: f.platform }));
    if (r) {
      setEdit(false);
      onChange();
    }
  };
  const dismiss = async () => {
    await act.run(() => api.patchClip(clip.id, { status: "dismissed" }));
    onChange();
  };
  const toContent = async () => {
    const r = await act.run(() => api.clipToContent(clip.id));
    if (r) setContentId(r.id);
  };
  const rendered = clip.status === "rendered" && clip.render_path;
  return (
    <div id={`clip-${clip.id}`} className={cn("rounded-md border bg-white", clip.status === "dismissed" ? "border-zinc-200 opacity-60" : "border-zinc-200")}>
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 px-3 py-2">
        <span className="font-mono text-[11px] text-zinc-500">
          {fmtTimestamp(clip.start)} – {fmtTimestamp(clip.end)} · {fmtDuration(clip.end - clip.start)}
        </span>
        <span className="text-[13px] font-semibold text-zinc-900">{clip.title || "Untitled clip"}</span>
        <StatusBadge status={clip.status} />
        <Badge variant="outline">{labelFormat(clip.platform)}</Badge>
        <span className="ml-auto font-mono text-xs text-zinc-600" title="Score">
          {Math.round(clip.score * 100)}
        </span>
      </div>
      <div className="grid gap-3 px-3 py-2 md:grid-cols-2">
        <div className="space-y-1 text-[13px]">
          {edit ? (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <Input type="number" step="0.1" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} />
                <Input type="number" step="0.1" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} />
              </div>
              <Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Title" />
              <Textarea rows={2} value={f.caption} onChange={(e) => setF({ ...f, caption: e.target.value })} placeholder="Caption" />
              <Select value={f.platform} onChange={(e) => setF({ ...f, platform: e.target.value })} className="w-full">
                {[...new Set([...CLIP_PLATFORMS, f.platform])].map((p) => (
                  <option key={p} value={p}>
                    {labelFormat(p)}
                  </option>
                ))}
              </Select>
              <div className="flex gap-2">
                <Button size="sm" variant="default" onClick={save} loading={act.busy}>
                  Save
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEdit(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              {clip.caption ? <p className="text-zinc-800">{clip.caption}</p> : null}
              {clip.why_it_works ? (
                <p className="text-xs text-zinc-600">
                  <span className="font-medium text-zinc-800">Why it works: </span>
                  {clip.why_it_works}
                </p>
              ) : null}
              {clip.transcript_text ? <p className="line-clamp-3 text-xs text-zinc-500">“{clip.transcript_text}”</p> : null}
            </>
          )}
        </div>
        <div>
          <ScoreBars breakdown={clip.score_breakdown ?? {}} />
        </div>
      </div>
      {rendered ? (
        <div className="border-t border-zinc-200 px-3 py-2">
          <video controls preload="metadata" src={api.clipFileUrl(clip.id)} className="max-h-72 rounded bg-black" />
          <p className="mt-1 font-mono text-[11px] text-zinc-400">{clip.render_path}</p>
        </div>
      ) : null}
      {clip.render_error ? <p className="border-t border-zinc-200 px-3 py-2 text-xs text-red-700">Render error: {clip.render_error}</p> : null}
      {renderJob ? (
        <div className="border-t border-zinc-200 px-3 py-2">
          <JobStatus jobId={renderJob} label="Render 9:16" onDone={(j) => j.status === "succeeded" && onChange()} />
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-1.5 border-t border-zinc-200 px-3 py-2">
        <Button size="sm" onClick={() => setEdit(true)} disabled={edit}>
          Edit
        </Button>
        <Button size="sm" variant="default" onClick={() => setRenderOpen(true)} disabled={!video.exists}>
          Render 9:16
        </Button>
        <Button size="sm" onClick={toContent} loading={act.busy}>
          Add to Content
        </Button>
        {clip.status !== "dismissed" ? (
          <Button size="sm" variant="ghost" onClick={dismiss}>
            Dismiss
          </Button>
        ) : null}
        {contentId ? (
          <Link href={`/content/${contentId}`} className="text-xs text-accent-strong hover:underline">
            Content item created — open
          </Link>
        ) : null}
        <ErrorNotice error={act.error} className="w-full" />
      </div>
      <RenderDialog open={renderOpen} onClose={() => setRenderOpen(false)} clip={clip} onQueued={(jid) => setRenderJob(jid)} />
    </div>
  );
}

function RenderDialog({ open, onClose, clip, onQueued }: { open: boolean; onClose: () => void; clip: Clip; onQueued: (jobId: string) => void }) {
  const settings = useApi(() => (open ? api.settings() : Promise.resolve(null)), [open]);
  const [f, setF] = React.useState({ caption_style: "bold_pop", accent_color: "#F46543", intro_text: "", progress_bar: true, watermark_text: "", captions: true, face_tracking: true, pad: 0 });
  const act = useAction();
  React.useEffect(() => {
    if (settings.data) {
      setF((p) => ({ ...p, caption_style: settings.data?.media.caption_style || p.caption_style, accent_color: settings.data?.content.accent_color || p.accent_color, watermark_text: settings.data?.content.watermark_text || "", face_tracking: settings.data?.media.face_tracking ?? true }));
    }
  }, [settings.data]);
  const submit = async () => {
    const j = await act.run(() => api.renderClip(clip.id, { ...f, pad: Number(f.pad) }));
    if (j) {
      onQueued(j.id);
      onClose();
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Render 9:16 — ${clip.title || "clip"}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy}>
            Render with FFmpeg
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Caption style">
            <Select value={f.caption_style} onChange={(e) => setF({ ...f, caption_style: e.target.value })} className="w-full">
              <option value="bold_pop">bold_pop</option>
              <option value="clean">clean</option>
              <option value="boxed">boxed</option>
            </Select>
          </Field>
          <Field label="Accent color">
            <div className="flex gap-2">
              <input type="color" value={f.accent_color} onChange={(e) => setF({ ...f, accent_color: e.target.value })} className="h-8 w-10 rounded border border-zinc-300" />
              <Input value={f.accent_color} onChange={(e) => setF({ ...f, accent_color: e.target.value })} />
            </div>
          </Field>
        </div>
        <Field label="Intro text" hint="(optional)">
          <Input value={f.intro_text} onChange={(e) => setF({ ...f, intro_text: e.target.value })} />
        </Field>
        <Field label="Watermark text">
          <Input value={f.watermark_text} onChange={(e) => setF({ ...f, watermark_text: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Switch checked={f.captions} onChange={(v) => setF({ ...f, captions: v })} label="Animated word captions" />
          <Switch checked={f.progress_bar} onChange={(v) => setF({ ...f, progress_bar: v })} label="Progress bar" />
          <Switch checked={f.face_tracking} onChange={(v) => setF({ ...f, face_tracking: v })} label="Face tracking crop" />
          <Field label="Pad seconds">
            <Input type="number" step="0.5" min={0} value={f.pad} onChange={(e) => setF({ ...f, pad: Number(e.target.value) })} />
          </Field>
        </div>
        <ErrorNotice error={act.error} />
        <p className="text-xs text-zinc-500">Originals are never modified. Output goes to data/renders/.</p>
      </div>
    </Dialog>
  );
}
