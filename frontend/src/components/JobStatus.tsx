"use client";

import { useJob } from "@/lib/hooks";
import type { Job } from "@/lib/types";
import { cn, humanize } from "@/lib/utils";
import { Button } from "./ui/button";

function messageOf(job: Job): string {
  const r = job.result ?? {};
  if (typeof r.message === "string") return r.message;
  if (job.status === "queued") return "Queued";
  if (job.status === "running") return "Running";
  if (job.status === "succeeded") return "Done";
  if (job.status === "failed") return "Failed";
  return humanize(job.status);
}

export function JobStatus({ jobId, onDone, label, className, compact }: { jobId: string | null; onDone?: (job: Job) => void; label?: string; className?: string; compact?: boolean }) {
  const { job, error, retry } = useJob(jobId, onDone);
  if (!jobId) return null;
  const status = job?.status ?? "queued";
  const progress = Math.max(0, Math.min(1, job?.progress ?? 0));
  const cloud = job?.cloud_override_allowed;
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-xs",
        status === "failed" ? "border-red-200 bg-red-50" : status === "succeeded" ? "border-emerald-200 bg-emerald-50" : cloud ? "border-warn/50 bg-warn-soft" : "border-zinc-200 bg-zinc-50",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span className="font-medium text-zinc-800">{label ?? humanize(job?.kind ?? "job")}</span>
        <span className={cn("rounded px-1 text-[10px] uppercase tracking-wide", status === "failed" ? "bg-red-100 text-red-800" : status === "succeeded" ? "bg-emerald-100 text-emerald-800" : "bg-zinc-200 text-zinc-700")}>{status}</span>
        {cloud ? <span className="rounded bg-warn px-1 text-[10px] uppercase text-white">cloud</span> : null}
        <span className="text-zinc-600">{job ? messageOf(job) : "Enqueued…"}</span>
        <span className="ml-auto font-mono text-[10px] text-zinc-400">{jobId.slice(0, 8)}</span>
        {status === "failed" && job?.retryable ? (
          <Button size="sm" variant="secondary" onClick={retry}>
            Retry
          </Button>
        ) : null}
      </div>
      {!compact && status !== "succeeded" && status !== "failed" ? (
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-zinc-200">
          <div className={cn("h-full transition-all", cloud ? "bg-warn" : "bg-accent")} style={{ width: `${Math.max(4, progress * 100)}%` }} />
        </div>
      ) : null}
      {job?.error ? <p className="mt-1 break-words text-red-700">{job.error}</p> : null}
      {error ? <p className="mt-1 text-red-700">Polling error: {error}</p> : null}
    </div>
  );
}
