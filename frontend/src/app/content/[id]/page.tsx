"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { ContentItem, ContentTreeNode, FactCheckClaim, ImageRecord } from "@/lib/types";
import { cn, fmtDateTime, fmtNumber, humanize, labelFormat, relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Panel } from "@/components/ui/section";
import { ClaimBadge, FACT_CHECK_STATUSES, FactCheckDot, FormatBadge, StatusBadge } from "@/components/badges";
import { JobStatus } from "@/components/JobStatus";
import { PackageView } from "@/components/PackageView";
import { GenerateContentDialog } from "@/components/GenerateContentDialog";
import { SaveToBookDialog } from "@/components/SaveToBookDialog";
import { usePrivacy } from "@/components/PrivacyContext";

export default function ContentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { privacy } = usePrivacy();
  const item = useApi(() => api.contentItem(id), [id]);
  const tree = useApi(() => api.contentTree(id), [id]);
  const formats = useApi(() => api.contentFormats(), []);
  const [tab, setTab] = React.useState("script");
  const [script, setScript] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [platform, setPlatform] = React.useState("");
  const [publishDate, setPublishDate] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [dirty, setDirty] = React.useState(false);
  const [jobs, setJobs] = React.useState<{ fact?: string; social?: string }>({});
  const [gen, setGen] = React.useState(false);
  const [book, setBook] = React.useState(false);
  const [gate, setGate] = React.useState<{ status: string; message: string } | null>(null);
  const [override, setOverride] = React.useState("");
  const act = useAction();
  const statusAct = useAction();

  React.useEffect(() => {
    if (item.data) {
      setScript(item.data.script);
      setTitle(item.data.title);
      setPlatform(item.data.platform);
      setPublishDate(item.data.publish_date ? item.data.publish_date.slice(0, 10) : "");
      setUrl(item.data.url);
      setDirty(false);
    }
  }, [item.data]);

  const c = item.data;
  const cloud = privacy?.cloud_ai_permitted;

  const save = async () => {
    const r = await act.run(() => api.patchContent(id, { title, script, platform, url, publish_date: publishDate || undefined }));
    if (r) {
      item.setData(r);
      tree.reload();
    }
  };
  const setStatus = async (status: string, override_reason = "") => {
    statusAct.setError(null);
    try {
      const r = await api.setContentStatus(id, status, override_reason);
      item.setData(r);
      setGate(null);
      setOverride("");
      tree.reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setGate({ status, message: e.detail });
      else statusAct.setError(e instanceof Error ? e.message : String(e));
    }
  };
  const runFactCheck = async () => {
    const j = await act.run(() => api.factCheck(id));
    if (j) setJobs((s) => ({ ...s, fact: j.id }));
  };
  const runSocial = async () => {
    const j = await act.run(() => api.socialBundle(id));
    if (j) setJobs((s) => ({ ...s, social: j.id }));
  };
  const remove = async () => {
    if (!confirm("Delete this content item? Children are kept and detached.")) return;
    const ok = await act.run(() => api.deleteContent(id));
    if (ok !== undefined) router.push("/content");
  };

  if (item.loading) return <ListSkeleton rows={6} />;
  if (item.error || !c) return <ErrorNotice error={item.error ?? "Not found"} />;
  const unresolved = c.fact_check_claims.filter((f) => !f.resolved).length;

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/content" className="hover:text-zinc-800">
          Content
        </Link>
        {c.lineage.parents.map((p) => (
          <span key={p.id}>
            {" / "}
            <Link href={`/content/${p.id}`} className="hover:text-zinc-800">
              {p.title}
            </Link>
          </span>
        ))}
      </div>
      <PageHeader
        title={c.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <FormatBadge format={c.format} />
            <StatusBadge status={c.status} />
            <span className="inline-flex items-center gap-1">
              <FactCheckDot status={c.fact_check_status} /> {c.fact_check_status.replace(/_/g, " ")}
            </span>
            {unresolved ? <Badge variant="danger">{unresolved} unresolved claims</Badge> : null}
            <span>· updated {relTime(c.updated_at)}</span>
            {typeof c.generation_meta?.model === "string" ? (
              <span className={cn("font-mono text-[11px]", c.generation_meta.locality === "cloud" ? "text-[#b3401f]" : "text-zinc-400")}>
                {String(c.generation_meta.provider ?? "")}:{String(c.generation_meta.model)} {c.generation_meta.locality === "cloud" ? "(cloud)" : ""}
              </span>
            ) : null}
          </span>
        }
        actions={
          <>
            <Button onClick={() => setBook(true)}>Save to Book</Button>
            <Button onClick={() => setGen(true)}>Derive content</Button>
            <Button variant={cloud ? "warn" : "secondary"} onClick={runSocial} loading={act.busy}>
              Generate social derivatives
            </Button>
            <Button variant="default" onClick={save} loading={act.busy} disabled={!dirty}>
              Save
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {jobs.social ? (
        <JobStatus
          jobId={jobs.social}
          label="Social derivatives"
          className="mb-3"
          onDone={(j) => {
            if (j.status === "succeeded") {
              item.reload();
              tree.reload();
            }
          }}
        />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0">
          <Tabs
            className="mb-3"
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "script", label: "Script" },
              { id: "package", label: "Package" },
              { id: "factcheck", label: "Fact check", count: c.fact_check_claims.length },
              { id: "tree", label: "Content tree" },
              { id: "metrics", label: "Metrics", count: c.metrics.length },
              { id: "images", label: "Images" },
            ]}
          />
          {tab === "script" ? (
            <div className="space-y-3">
              <div className="grid gap-2 md:grid-cols-4">
                <Field label="Title" className="md:col-span-2">
                  <Input
                    value={title}
                    onChange={(e) => {
                      setTitle(e.target.value);
                      setDirty(true);
                    }}
                  />
                </Field>
                <Field label="Platform">
                  <Input
                    value={platform}
                    onChange={(e) => {
                      setPlatform(e.target.value);
                      setDirty(true);
                    }}
                  />
                </Field>
                <Field label="Publish date">
                  <Input
                    type="date"
                    value={publishDate}
                    onChange={(e) => {
                      setPublishDate(e.target.value);
                      setDirty(true);
                    }}
                  />
                </Field>
                <Field label="Published URL" className="md:col-span-4">
                  <Input
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      setDirty(true);
                    }}
                    placeholder="https://"
                  />
                </Field>
              </div>
              <Textarea
                rows={28}
                className="font-mono text-[12.5px] leading-relaxed"
                value={script}
                onChange={(e) => {
                  setScript(e.target.value);
                  setDirty(true);
                }}
                placeholder="Script or body text. Editing a fact-checked script resets its fact-check status."
              />
              <div className="flex items-center gap-2">
                <Button variant="default" onClick={save} loading={act.busy} disabled={!dirty}>
                  Save script
                </Button>
                <span className="text-xs text-zinc-400">{script.length.toLocaleString()} characters · {script.split(/\s+/).filter(Boolean).length.toLocaleString()} words</span>
              </div>
            </div>
          ) : null}
          {tab === "package" ? (
            <Panel>
              <PackageView pkg={c.package ?? {}} />
            </Panel>
          ) : null}
          {tab === "factcheck" ? (
            <FactCheckPanel
              item={c}
              jobId={jobs.fact ?? null}
              onRun={runFactCheck}
              busy={act.busy}
              cloud={!!cloud}
              onJobDone={() => item.reload()}
              onResolved={(r) => item.setData(r)}
            />
          ) : null}
          {tab === "tree" ? (
            <Panel title="Content tree" actions={<span className="text-xs text-zinc-400">Lineage from the root item down to every derivative.</span>}>
              <ErrorNotice error={tree.error} />
              {tree.data ? <TreeNode node={tree.data} current={id} depth={0} /> : <ListSkeleton rows={2} />}
            </Panel>
          ) : null}
          {tab === "metrics" ? <MetricsPanel item={c} onAdded={() => item.reload()} /> : null}
          {tab === "images" ? <ImagesPanel item={c} /> : null}
        </div>

        <aside className="space-y-3">
          <Panel title="Status">
            <Select value={c.status} onChange={(e) => setStatus(e.target.value)} className="w-full">
              {(formats.data?.statuses ?? [c.status]).map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
            <ErrorNotice error={statusAct.error} className="mt-2" />
            {gate ? (
              <div className="mt-2 rounded-md border border-warn/50 bg-warn-soft p-2 text-xs text-[#9a3a1c]">
                <p className="font-medium">Fact-check gate</p>
                <p className="mt-0.5">{gate.message}</p>
                <Input className="mt-2 bg-white" placeholder="Override reason (recorded on the item)" value={override} onChange={(e) => setOverride(e.target.value)} />
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="warn" disabled={!override.trim()} onClick={() => setStatus(gate.status, override.trim())}>
                    Override with reason
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setGate(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : null}
            {c.fact_check_override_reason ? <p className="mt-2 text-xs text-[#9a3a1c]">Override recorded: {c.fact_check_override_reason}</p> : null}
            {c.approved_at ? <p className="mt-2 text-xs text-zinc-500">Approved {fmtDateTime(c.approved_at)}</p> : null}
          </Panel>
          <Panel title="Lineage">
            <dl className="space-y-1.5 text-[13px]">
              <div>
                <dt className="text-[11px] uppercase text-zinc-500">Story</dt>
                <dd>
                  {c.lineage.story ? (
                    <Link href={`/stories/${c.lineage.story.id}`} className="text-zinc-900 hover:text-accent-strong">
                      {c.lineage.story.title}
                    </Link>
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase text-zinc-500">Position brief</dt>
                <dd>
                  {c.lineage.brief ? (
                    <Link href={`/think/briefs/${c.lineage.brief.id}`} className="text-zinc-900 hover:text-accent-strong">
                      {c.lineage.brief.issue}
                    </Link>
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase text-zinc-500">Principles</dt>
                <dd>
                  {c.lineage.principles.length === 0 ? <span className="text-zinc-400">—</span> : null}
                  <ul>
                    {c.lineage.principles.map((p) => (
                      <li key={p.id}>
                        <Link href={`/principles/${p.id}`} className="text-zinc-900 hover:text-accent-strong">
                          {p.title}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
              {c.lineage.source_video_id ? (
                <div>
                  <dt className="text-[11px] uppercase text-zinc-500">Video / clip</dt>
                  <dd>
                    <Link href={`/videos/${c.lineage.source_video_id}${c.lineage.clip_id ? `#clip-${c.lineage.clip_id}` : ""}`} className="text-zinc-900 hover:text-accent-strong">
                      Open source video
                    </Link>
                  </dd>
                </div>
              ) : null}
              {c.lineage.parents.length ? (
                <div>
                  <dt className="text-[11px] uppercase text-zinc-500">Parent</dt>
                  <dd>
                    <Link href={`/content/${c.lineage.parents[0].id}`} className="text-zinc-900 hover:text-accent-strong">
                      {c.lineage.parents[0].title}
                    </Link>
                  </dd>
                </div>
              ) : null}
              <div>
                <dt className="text-[11px] uppercase text-zinc-500">Children ({c.children.length})</dt>
                <dd>
                  <ul>
                    {c.children.map((k) => (
                      <li key={k.id} className="flex items-center gap-1.5">
                        <Link href={`/content/${k.id}`} className="min-w-0 flex-1 truncate text-zinc-900 hover:text-accent-strong">
                          {k.title}
                        </Link>
                        <span className="text-[11px] text-zinc-400">{labelFormat(k.format)}</span>
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            </dl>
          </Panel>
          <Panel title="Danger zone">
            <Button variant="danger" size="sm" onClick={remove}>
              Delete item
            </Button>
          </Panel>
        </aside>
      </div>
      <GenerateContentDialog open={gen} onClose={() => setGen(false)} defaults={{ parent_id: c.id, story_id: c.story_id, brief_id: c.position_brief_id, principle_ids: c.principle_ids, format: "youtube_short" }} onCreated={() => { item.reload(); tree.reload(); }} />
      <SaveToBookDialog open={book} onClose={() => setBook(false)} defaults={{ title: c.title, body: (c.package?.thesis as string) || c.script.slice(0, 500), content_item_id: c.id, story_id: c.story_id }} />
    </div>
  );
}

function TreeNode({ node, current, depth }: { node: ContentTreeNode; current: string; depth: number }) {
  return (
    <div>
      <div className={cn("flex items-center gap-2 rounded px-1.5 py-1", node.id === current && "bg-accent-soft")} style={{ marginLeft: depth * 18 }}>
        {depth > 0 ? <span className="text-zinc-300">└</span> : null}
        <Link href={`/content/${node.id}`} className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-900 hover:text-accent-strong">
          {node.title}
        </Link>
        <FormatBadge format={node.format} />
        <StatusBadge status={node.status} />
        {node.platform ? <span className="text-[11px] text-zinc-400">{node.platform}</span> : null}
      </div>
      {node.children.map((k) => (
        <TreeNode key={k.id} node={k} current={current} depth={depth + 1} />
      ))}
    </div>
  );
}

function FactCheckPanel({ item, jobId, onRun, busy, cloud, onJobDone, onResolved }: { item: ContentItem; jobId: string | null; onRun: () => void; busy: boolean; cloud: boolean; onJobDone: () => void; onResolved: (r: ContentItem) => void }) {
  const [editing, setEditing] = React.useState<FactCheckClaim | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-2">
        <p className="text-xs text-zinc-600">Every factual assertion in the script is extracted and labelled. A script cannot become READY or PUBLISHED with unresolved assertions unless you record an explicit override.</p>
        <Button variant={cloud ? "warn" : "default"} className="ml-auto" onClick={onRun} loading={busy}>
          {cloud ? "Run fact check (cloud AI may be used)" : "Run fact check"}
        </Button>
      </div>
      {jobId ? <JobStatus jobId={jobId} label="Fact check" onDone={(j) => j.status === "succeeded" && onJobDone()} /> : null}
      {item.fact_check_claims.length === 0 ? <EmptyState title="No claims extracted yet." /> : null}
      {item.fact_check_claims.length ? (
        <Table>
          <THead>
            <tr>
              <TH>Assertion</TH>
              <TH>Status</TH>
              <TH>Sources</TH>
              <TH>Notes</TH>
              <TH></TH>
            </tr>
          </THead>
          <TBody>
            {item.fact_check_claims.map((f) => (
              <TR key={f.id} className={!f.resolved ? "bg-red-50/40" : ""}>
                <TD className="max-w-md text-zinc-900">{f.text}</TD>
                <TD>
                  <ClaimBadge status={f.status} />
                  {!f.resolved ? <div className="text-[10px] uppercase text-red-700">unresolved</div> : null}
                </TD>
                <TD className="max-w-[12rem] text-xs">
                  {f.sources.length === 0 ? <span className="text-zinc-400">—</span> : null}
                  {f.sources.map((s, i) => (
                    <a key={i} href={s} target="_blank" rel="noreferrer" className="block truncate text-accent-strong hover:underline">
                      {s}
                    </a>
                  ))}
                </TD>
                <TD className="max-w-xs text-xs text-zinc-600">{f.notes || "—"}</TD>
                <TD>
                  <Button size="sm" onClick={() => setEditing(f)}>
                    Resolve
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
      <ResolveDialog claim={editing} contentId={item.id} onClose={() => setEditing(null)} onResolved={onResolved} />
    </div>
  );
}

function ResolveDialog({ claim, contentId, onClose, onResolved }: { claim: FactCheckClaim | null; contentId: string; onClose: () => void; onResolved: (r: ContentItem) => void }) {
  const [status, setStatus] = React.useState("VERIFIED");
  const [sources, setSources] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const act = useAction();
  React.useEffect(() => {
    if (claim) {
      setStatus(claim.status);
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
      title="Resolve claim"
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
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full">
            {FACT_CHECK_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
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

function MetricsPanel({ item, onAdded }: { item: ContentItem; onAdded: () => void }) {
  const [f, setF] = React.useState({ platform: item.platform, recorded_at: "", views: 0, watch_time_seconds: 0, retention_pct: "", likes: 0, comments: 0, shares: 0, subscribers_gained: 0, completion_pct: "" });
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() =>
      api.addMetric(item.id, {
        platform: f.platform,
        recorded_at: f.recorded_at || undefined,
        views: Number(f.views),
        watch_time_seconds: Number(f.watch_time_seconds),
        retention_pct: f.retention_pct === "" ? null : Number(f.retention_pct),
        likes: Number(f.likes),
        comments: Number(f.comments),
        shares: Number(f.shares),
        subscribers_gained: Number(f.subscribers_gained),
        completion_pct: f.completion_pct === "" ? null : Number(f.completion_pct),
      }),
    );
    if (r) onAdded();
  };
  const num = (k: keyof typeof f, label: string) => (
    <Field label={label} key={k}>
      <Input type="number" value={f[k] as number | string} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </Field>
  );
  return (
    <div className="space-y-3">
      {item.metrics.length === 0 ? <EmptyState title="No metrics recorded.">Add a snapshot below or import a CSV under Analytics.</EmptyState> : null}
      {item.metrics.length ? (
        <Table>
          <THead>
            <tr>
              <TH>Recorded</TH>
              <TH>Platform</TH>
              <TH className="text-right">Views</TH>
              <TH className="text-right">Likes</TH>
              <TH className="text-right">Comments</TH>
              <TH className="text-right">Shares</TH>
              <TH className="text-right">Watch time (s)</TH>
              <TH className="text-right">Retention</TH>
              <TH className="text-right">Subs</TH>
              <TH>Source</TH>
            </tr>
          </THead>
          <TBody>
            {[...item.metrics]
              .sort((a, b) => b.recorded_at.localeCompare(a.recorded_at))
              .map((m) => (
                <TR key={m.id}>
                  <TD className="whitespace-nowrap text-xs">{fmtDateTime(m.recorded_at)}</TD>
                  <TD className="text-xs">{m.platform || "—"}</TD>
                  <TD className="text-right tabular-nums">{fmtNumber(m.views)}</TD>
                  <TD className="text-right tabular-nums">{fmtNumber(m.likes)}</TD>
                  <TD className="text-right tabular-nums">{fmtNumber(m.comments)}</TD>
                  <TD className="text-right tabular-nums">{fmtNumber(m.shares)}</TD>
                  <TD className="text-right tabular-nums">{fmtNumber(Math.round(m.watch_time_seconds))}</TD>
                  <TD className="text-right tabular-nums">{m.retention_pct != null ? `${m.retention_pct}%` : "—"}</TD>
                  <TD className="text-right tabular-nums">{fmtNumber(m.subscribers_gained)}</TD>
                  <TD className="text-xs text-zinc-500">{m.source}</TD>
                </TR>
              ))}
          </TBody>
        </Table>
      ) : null}
      <Panel title="Add metric snapshot">
        <div className="grid gap-2 md:grid-cols-5">
          <Field label="Platform">
            <Input value={f.platform} onChange={(e) => setF({ ...f, platform: e.target.value })} />
          </Field>
          <Field label="Recorded at">
            <Input type="datetime-local" value={f.recorded_at} onChange={(e) => setF({ ...f, recorded_at: e.target.value })} />
          </Field>
          {num("views", "Views")}
          {num("likes", "Likes")}
          {num("comments", "Comments")}
          {num("shares", "Shares")}
          {num("watch_time_seconds", "Watch time (s)")}
          {num("retention_pct", "Retention %")}
          {num("completion_pct", "Completion %")}
          {num("subscribers_gained", "Subscribers gained")}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Button variant="default" onClick={submit} loading={act.busy}>
            Add snapshot
          </Button>
          <ErrorNotice error={act.error} />
        </div>
      </Panel>
    </div>
  );
}

function ImagesPanel({ item }: { item: ContentItem }) {
  const images = useApi(() => api.images(), []);
  const mine = (images.data ?? []).filter((i) => i.content_item_id === item.id);
  const [kind, setKind] = React.useState<"quote_card" | "text_meme">("quote_card");
  const [quote, setQuote] = React.useState((item.package?.social?.quote_cards?.[0] as string) ?? "");
  const [attribution, setAttribution] = React.useState("");
  const [top, setTop] = React.useState("");
  const [bottom, setBottom] = React.useState("");
  const act = useAction();
  const create = async () => {
    const params = kind === "quote_card" ? { quote, attribution } : { top, bottom };
    const r = await act.run(() => api.createImage({ kind, params, content_item_id: item.id, title: item.title }));
    if (r) images.reload();
  };
  const approve = async (im: ImageRecord, approved: boolean) => {
    await act.run(() => api.approveImage(im.id, approved));
    images.reload();
  };
  return (
    <div className="space-y-3">
      <Panel title="Create quote card or meme">
        <div className="mb-2 flex gap-2">
          <Button size="sm" variant={kind === "quote_card" ? "default" : "secondary"} onClick={() => setKind("quote_card")}>
            Quote card
          </Button>
          <Button size="sm" variant={kind === "text_meme" ? "default" : "secondary"} onClick={() => setKind("text_meme")}>
            Text meme
          </Button>
        </div>
        {kind === "quote_card" ? (
          <div className="grid gap-2 md:grid-cols-[2fr_1fr]">
            <Textarea rows={2} placeholder="Quote" value={quote} onChange={(e) => setQuote(e.target.value)} />
            <Input placeholder="Attribution" value={attribution} onChange={(e) => setAttribution(e.target.value)} />
          </div>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            <Input placeholder="Top text" value={top} onChange={(e) => setTop(e.target.value)} />
            <Input placeholder="Bottom text" value={bottom} onChange={(e) => setBottom(e.target.value)} />
          </div>
        )}
        <div className="mt-2 flex items-center gap-2">
          <Button variant="default" onClick={create} loading={act.busy} disabled={kind === "quote_card" ? !quote.trim() : !top.trim()}>
            Render locally
          </Button>
          <span className="text-xs text-zinc-500">Deterministic renderer; generated or satirical imagery is labelled and needs approval before export.</span>
        </div>
        <ErrorNotice error={act.error} className="mt-2" />
      </Panel>
      <ErrorNotice error={images.error} />
      {mine.length === 0 ? <p className="text-xs text-zinc-400">No images attached to this item.</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {mine.map((im) => (
          <div key={im.id} className="rounded-md border border-zinc-200 bg-white p-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={api.imageFileUrl(im.id)} alt={im.title} className="aspect-square w-full rounded object-cover" />
            <div className="mt-1.5 flex items-center gap-1.5 text-xs">
              <Badge variant="outline">{humanize(im.kind)}</Badge>
              <Badge variant={im.label === "satire" ? "warn" : "neutral"}>{im.label}</Badge>
              {im.approved ? <Badge variant="success">approved</Badge> : null}
              <Button size="sm" variant="ghost" className="ml-auto" onClick={() => approve(im, !im.approved)}>
                {im.approved ? "Unapprove" : "Approve"}
              </Button>
            </div>
          </div>
        ))}
      </div>
      {mine.length ? <Notice>Approval is required before any export. Poly never posts automatically.</Notice> : null}
    </div>
  );
}
