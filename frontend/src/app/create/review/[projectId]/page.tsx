"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2, Circle, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { ContentItem, FactCheckClaim } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { FACT_CHECK_LABEL, FACT_CHECK_STATUSES } from "@/components/badges";
import { JobStatus } from "@/components/JobStatus";

export default function ReviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const project = useApi(() => api.studioProject(projectId), [projectId]);
  const quality = useApi(() => api.studioQuality(projectId), [projectId]);
  const cid = project.data?.content_item_id ?? null;
  const item = useApi(() => (cid ? api.contentItem(cid) : Promise.resolve(null)), [cid]);
  const [title, setTitle] = React.useState("");
  const [caption, setCaption] = React.useState("");
  const [factJob, setFactJob] = React.useState<string | null>(null);
  const [gate, setGate] = React.useState<string | null>(null);
  const [note, setNote] = React.useState("");
  const [approved, setApproved] = React.useState(false);
  const [copied, setCopied] = React.useState<string | null>(null);
  const [slide, setSlide] = React.useState(0);
  const act = useAction();

  const p = project.data;
  React.useEffect(() => {
    if (p) {
      setTitle(p.title);
      setCaption(p.caption);
    }
  }, [p]);

  const saveTitle = async () => {
    if (!p || !cid || title.trim() === p.title) return;
    await act.run(() => api.patchContent(cid, { title: title.trim() }));
  };
  const saveCaption = async () => {
    if (!p || caption === p.caption) return;
    await act.run(() => api.patchStudioProject(projectId, { caption }));
  };

  const runFactCheck = async () => {
    if (!cid) return;
    const j = await act.run(() => api.factCheck(cid));
    if (j) setFactJob(j.id);
  };

  const approve = async (override_reason = "") => {
    if (!cid) return;
    act.setError(null);
    try {
      await api.setContentStatus(cid, "READY", override_reason);
      setApproved(true);
      setGate(null);
      setNote("");
      void item.reload();
      void project.reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setGate(e.detail);
      else act.setError(e instanceof Error ? e.message : String(e));
    }
  };

  const copy = async (what: "caption" | "script") => {
    try {
      const text = what === "caption" ? caption : (await api.studioScript(projectId)).markdown;
      await navigator.clipboard?.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 1500);
    } catch (e) {
      act.setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (project.loading) return <ListSkeleton rows={5} />;
  if (project.error || !p) return <ErrorNotice error={project.error ?? "Not found"} />;

  const isCarousel = p.kind === "carousel";
  const rendered = p.render_status === "done";
  const claims = (item.data?.fact_check_claims ?? []).filter((f) => !f.resolved);
  const isReady = item.data?.status === "READY" || item.data?.status === "PUBLISHED" || approved;

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href={`/create/studio/${projectId}`} className="hover:text-zinc-800">
          Editor
        </Link>{" "}
        / review
      </div>
      <h1 className="mb-5 text-[36px]">Is this good to go?</h1>
      <ErrorNotice error={act.error} className="mb-3" />
      {isReady ? <Notice kind="success" className="mb-3">Approved and marked Ready. Export it below whenever you like.</Notice> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        {/* Preview + text */}
        <div className="min-w-0">
          <div className="mb-4">
            {rendered && !isCarousel ? (
              <video controls preload="metadata" src={api.projectFileUrl(p.id)} className="mx-auto max-h-[480px] rounded-md bg-black" />
            ) : rendered && isCarousel ? (
              <div className="mx-auto max-w-[340px]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={api.slideFileUrl(p.id, slide)} alt={`Slide ${slide + 1}`} className="w-full rounded-md border border-zinc-200 bg-zinc-100" />
                <div className="mt-2 flex items-center justify-center gap-3">
                  <Button size="sm" onClick={() => setSlide((i) => Math.max(0, i - 1))} disabled={slide === 0}>
                    Previous
                  </Button>
                  <span className="font-mono text-xs text-zinc-500">
                    {slide + 1} / {p.scenes.length}
                  </span>
                  <Button size="sm" onClick={() => setSlide((i) => Math.min(p.scenes.length - 1, i + 1))} disabled={slide >= p.scenes.length - 1}>
                    Next
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-[300px]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={api.scenePreviewUrl(p.id, 0, 0.5, p.updated_at ?? 1)} alt="First scene" className="w-full rounded-md border border-zinc-200 bg-zinc-100" />
                <p className="mt-1 text-center text-xs text-zinc-500">Not rendered yet — this is the first scene. Render from the editor to preview the whole thing.</p>
              </div>
            )}
          </div>
          <div className="space-y-3 rounded-md border border-zinc-200 bg-white p-3">
            <Field label="Title">
              <Input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={saveTitle} />
            </Field>
            <Field label="Caption">
              <Textarea rows={3} value={caption} onChange={(e) => setCaption(e.target.value)} onBlur={saveCaption} />
            </Field>
            {p.hashtags.length ? <p className="text-xs text-zinc-500">{p.hashtags.map((h) => `#${h}`).join(" ")}</p> : null}
            <div>
              <p className="mb-1 text-xs font-medium text-zinc-600">Sources</p>
              {p.sources.length === 0 ? <p className="text-xs text-zinc-400">No sources attached.</p> : null}
              <ul className="space-y-0.5 text-[13px]">
                {p.sources.map((s, i) => (
                  <li key={i}>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer" className="text-accent-strong hover:underline">
                        {s.label || s.url}
                      </a>
                    ) : (
                      s.label
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Quality + actions */}
        <aside className="space-y-4">
          <div className="rounded-md border border-zinc-200 bg-white">
            <div className="flex items-center justify-between border-b border-zinc-200 px-3 py-2">
              <h3 className="text-[13px] font-semibold text-zinc-800">Quality checklist</h3>
              <Button size="sm" onClick={runFactCheck} loading={act.busy}>
                Run fact check
              </Button>
            </div>
            <div className="px-3 py-2">
              {factJob ? (
                <JobStatus
                  jobId={factJob}
                  label="Checking the facts"
                  className="mb-2"
                  onDone={(j) => {
                    if (j.status === "succeeded") {
                      void quality.reload();
                      void item.reload();
                    }
                  }}
                />
              ) : null}
              <ErrorNotice error={quality.error} className="mb-2" />
              {quality.loading ? <ListSkeleton rows={2} /> : null}
              <ul className="space-y-1.5">
                {(quality.data?.checks ?? []).map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px]">
                    {c.status === "pass" ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" />
                    ) : c.status === "fail" ? (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
                    ) : (
                      <Circle className="mt-0.5 h-4 w-4 shrink-0 text-highlight" />
                    )}
                    <span>
                      <span className={cn("font-medium", c.status === "fail" ? "text-danger" : c.status === "warn" ? "text-highlight-strong" : "text-zinc-800")}>{c.check}</span>{" "}
                      <span className="text-zinc-600">{c.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {claims.length ? <UnresolvedClaims claims={claims} contentId={cid!} onResolved={(r) => { item.setData(r); void quality.reload(); }} /> : null}

          <div className="rounded-md border border-zinc-200 bg-white p-3">
            <div className="grid grid-cols-3 gap-2">
              <Button variant="secondary" onClick={() => router.push(`/create/studio/${projectId}`)}>
                Edit
              </Button>
              <Button variant="default" onClick={() => approve()} disabled={isReady} data-testid="approve">
                Approve
              </Button>
              <a
                href={rendered ? api.projectFileUrl(p.id) : undefined}
                download
                className={cn(
                  "inline-flex h-8 items-center justify-center rounded-md border px-3 text-[13px] font-medium",
                  rendered ? "border-accent bg-accent text-white hover:opacity-90" : "pointer-events-none border-zinc-200 bg-zinc-100 text-zinc-400",
                )}
                title={rendered ? "" : "Render first to export"}
              >
                Export
              </a>
            </div>
            {gate ? (
              <div className="mt-3 rounded-md border border-warn/50 bg-warn-soft p-2 text-xs text-highlight-strong">
                <p className="font-medium">Not approved yet</p>
                <p className="mt-0.5">{gate}</p>
                <Input className="mt-2 bg-white" placeholder="Add a note explaining why it's fine" value={note} onChange={(e) => setNote(e.target.value)} data-testid="approve-note" />
                <Button size="sm" variant="warn" className="mt-2" disabled={!note.trim()} onClick={() => approve(note.trim())} data-testid="approve-with-note">
                  Approve with a note
                </Button>
              </div>
            ) : null}
            <div className="mt-2 flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => copy("caption")}>
                {copied === "caption" ? "Copied" : "Copy caption"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => copy("script")}>
                {copied === "script" ? "Copied" : "Copy script"}
              </Button>
            </div>
            <p className="mt-2 text-[11px] text-zinc-400">Nothing is ever posted automatically.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function UnresolvedClaims({ claims, contentId, onResolved }: { claims: FactCheckClaim[]; contentId: string; onResolved: (r: ContentItem) => void }) {
  const [editing, setEditing] = React.useState<FactCheckClaim | null>(null);
  return (
    <div className="rounded-md border border-danger/40 bg-white">
      <div className="border-b border-danger/40 px-3 py-2 text-[13px] font-semibold text-danger">
        {claims.length} claim{claims.length === 1 ? "" : "s"} still unverified
      </div>
      <ul>
        {claims.map((f) => (
          <li key={f.id} className="flex items-start gap-2 border-b border-zinc-100 px-3 py-2 text-[13px] last:border-b-0">
            <span className="min-w-0 flex-1 text-zinc-800">{f.text}</span>
            <Button size="sm" onClick={() => setEditing(f)}>
              Resolve
            </Button>
          </li>
        ))}
      </ul>
      <ResolveClaimDialog claim={editing} contentId={contentId} onClose={() => setEditing(null)} onResolved={onResolved} />
    </div>
  );
}

function ResolveClaimDialog({ claim, contentId, onClose, onResolved }: { claim: FactCheckClaim | null; contentId: string; onClose: () => void; onResolved: (r: ContentItem) => void }) {
  const [status, setStatus] = React.useState("VERIFIED");
  const [sources, setSources] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const act = useAction();
  React.useEffect(() => {
    if (claim) {
      setStatus(claim.status === "UNVERIFIED" ? "VERIFIED" : claim.status);
      setSources(claim.sources.join("\n"));
      setNotes(claim.notes);
    }
  }, [claim]);
  if (!claim) return null;
  const submit = async () => {
    const r = await act.run(() => api.resolveClaim(contentId, claim.id, { status, sources: sources.split("\n").map((s) => s.trim()).filter(Boolean), notes }));
    if (r) {
      onResolved(r);
      onClose();
    }
  };
  return (
    <Dialog
      open={!!claim}
      onClose={onClose}
      title="Resolve this claim"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="rounded bg-zinc-50 p-2 text-[13px] text-zinc-800">{claim.text}</p>
        <Field label="What did you find?">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full">
            {FACT_CHECK_STATUSES.map((s) => (
              <option key={s} value={s}>
                {FACT_CHECK_LABEL[s] ?? s.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Sources" hint="one URL per line">
          <Textarea rows={3} value={sources} onChange={(e) => setSources(e.target.value)} />
        </Field>
        <Field label="Notes">
          <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        <ErrorNotice error={act.error} />
      </div>
    </Dialog>
  );
}
