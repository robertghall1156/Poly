"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDateTime, fmtDuration, relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Section } from "@/components/ui/section";
import { StatusBadge } from "@/components/badges";
import { JobStatus } from "@/components/JobStatus";

export default function VideosPage() {
  const folders = useApi(() => api.videoFolders(), []);
  const videos = useApi(() => api.videos(), []);
  const [path, setPath] = React.useState("");
  const [jobs, setJobs] = React.useState<Record<string, string>>({});
  const act = useAction();

  const addFolder = async () => {
    const r = await act.run(() => api.addVideoFolder(path.trim()));
    if (r) {
      setPath("");
      folders.reload();
      setJobs((j) => ({ ...j, [r.folder.id]: r.job.id }));
    }
  };
  const rescan = async (id: string) => {
    const j = await act.run(() => api.scanFolder(id));
    if (j) setJobs((m) => ({ ...m, [id]: j.id }));
  };
  const remove = async (id: string) => {
    if (!confirm("Remove this folder from the index? Files on disk are not touched.")) return;
    await act.run(() => api.removeFolder(id));
    folders.reload();
    videos.reload();
  };

  return (
    <div>
      <PageHeader title="Videos" description="Your local video library: indexed, transcribed and mined for clip opportunities." />
      <Notice className="mb-4">Videos are indexed by metadata only and processed locally. Nothing leaves this machine.</Notice>
      <Section title="Folders">
        <ErrorNotice error={folders.error ?? act.error} className="mb-2" />
        <div className="mb-2 flex gap-2">
          <Input placeholder="/absolute/path/to/videos" value={path} onChange={(e) => setPath(e.target.value)} onKeyDown={(e) => e.key === "Enter" && path.trim() && addFolder()} />
          <Button variant="default" onClick={addFolder} disabled={!path.trim()} loading={act.busy}>
            Add folder
          </Button>
        </div>
        {folders.data && folders.data.length === 0 ? <EmptyState title="No folders configured.">Add an absolute path above. Poly will scan it with ffprobe and record metadata only.</EmptyState> : null}
        {folders.data && folders.data.length > 0 ? (
          <Table>
            <THead>
              <tr>
                <TH>Path</TH>
                <TH>Exists</TH>
                <TH className="text-right">Videos</TH>
                <TH>Last scanned</TH>
                <TH></TH>
              </tr>
            </THead>
            <TBody>
              {folders.data.map((f) => (
                <TR key={f.id}>
                  <TD className="font-mono text-xs text-zinc-800">
                    {f.path}
                    {f.recursive ? <span className="ml-1 text-zinc-400">(recursive)</span> : null}
                    {jobs[f.id] ? <JobStatus jobId={jobs[f.id]} label="Scan" compact className="mt-1" onDone={() => { folders.reload(); videos.reload(); }} /> : null}
                  </TD>
                  <TD>{f.exists ? <Badge variant="success">yes</Badge> : <Badge variant="danger">missing</Badge>}</TD>
                  <TD className="text-right tabular-nums">{f.video_count}</TD>
                  <TD className="text-xs text-zinc-500">{f.last_scanned_at ? relTime(f.last_scanned_at) : "never"}</TD>
                  <TD className="whitespace-nowrap">
                    <Button size="sm" onClick={() => rescan(f.id)}>
                      Rescan
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => remove(f.id)}>
                      Remove
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ) : null}
      </Section>
      <Section title="Library">
        <ErrorNotice error={videos.error} className="mb-2" />
        {videos.loading ? <ListSkeleton /> : null}
        {videos.data && videos.data.length === 0 ? <EmptyState title="No videos indexed.">Add a folder and scan it.</EmptyState> : null}
        {videos.data && videos.data.length > 0 ? (
          <Table>
            <THead>
              <tr>
                <TH>File</TH>
                <TH className="text-right">Duration</TH>
                <TH>Resolution</TH>
                <TH className="text-right">FPS</TH>
                <TH>Created</TH>
                <TH>Transcript</TH>
                <TH className="text-right">Clips</TH>
                <TH></TH>
              </tr>
            </THead>
            <TBody>
              {videos.data.map((v) => (
                <TR key={v.id} className={v.missing ? "opacity-60" : ""}>
                  <TD>
                    <Link href={`/videos/${v.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                      {v.filename}
                    </Link>
                    <div className="truncate font-mono text-[11px] text-zinc-400">{v.path}</div>
                  </TD>
                  <TD className="text-right font-mono text-xs">{fmtDuration(v.duration)}</TD>
                  <TD className="font-mono text-xs">
                    {v.width}×{v.height}
                  </TD>
                  <TD className="text-right font-mono text-xs">{v.fps}</TD>
                  <TD className="whitespace-nowrap text-xs text-zinc-500">{fmtDateTime(v.file_created_at)}</TD>
                  <TD>
                    <StatusBadge status={v.transcript_status} />
                  </TD>
                  <TD className="text-right tabular-nums">{v.clip_count}</TD>
                  <TD>{v.missing ? <Badge variant="danger">missing</Badge> : null}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ) : null}
      </Section>
    </div>
  );
}
