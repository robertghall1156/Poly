"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Job } from "@/lib/types";
import { fmtDateTime, humanize } from "@/lib/utils";
import { Button } from "../ui/button";
import { Select } from "../ui/input";
import { Table, TBody, TD, TH, THead, TR } from "../ui/table";
import { ListSkeleton } from "../ui/skeleton";
import { EmptyState, ErrorNotice } from "../ui/notice";
import { StatusBadge } from "../badges";

export function JobsTab() {
  const [status, setStatus] = React.useState("");
  const jobs = useApi(() => api.jobs({ status: status || undefined, limit: 100 }), [status]);
  const [err, setErr] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState<string | null>(null);

  React.useEffect(() => {
    const hasActive = (jobs.data ?? []).some((j) => j.status === "queued" || j.status === "running");
    if (!hasActive) return;
    const t = setInterval(() => jobs.reload(), 2000);
    return () => clearInterval(t);
  }, [jobs.data, jobs]);

  const retry = async (j: Job) => {
    try {
      await api.retryJob(j.id);
      jobs.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["queued", "running", "succeeded", "failed"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Button size="sm" onClick={() => jobs.reload()}>
          Refresh
        </Button>
        <span className="text-xs text-zinc-500">Active jobs refresh automatically.</span>
      </div>
      <ErrorNotice error={jobs.error ?? err} className="mb-3" />
      {jobs.loading ? <ListSkeleton /> : null}
      {jobs.data && jobs.data.length === 0 ? <EmptyState title="No jobs recorded." /> : null}
      {jobs.data && jobs.data.length ? (
        <Table>
          <THead>
            <tr>
              <TH>Kind</TH>
              <TH>Status</TH>
              <TH>Progress</TH>
              <TH>Created</TH>
              <TH>Finished</TH>
              <TH>Result / error</TH>
              <TH></TH>
            </tr>
          </THead>
          <TBody>
            {jobs.data.map((j) => (
              <TR key={j.id}>
                <TD>
                  <div className="font-medium text-zinc-900">{humanize(j.kind)}</div>
                  <div className="font-mono text-[10px] text-zinc-400">
                    {j.id.slice(0, 8)} · attempts {j.attempts}
                    {j.cloud_override_allowed ? <span className="ml-1 text-[#b3401f]">cloud override</span> : null}
                  </div>
                </TD>
                <TD>
                  <StatusBadge status={j.status} />
                </TD>
                <TD>
                  <div className="h-1.5 w-20 overflow-hidden rounded-full bg-zinc-200">
                    <div className="h-full bg-accent" style={{ width: `${Math.round(j.progress * 100)}%` }} />
                  </div>
                </TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{fmtDateTime(j.created_at)}</TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{fmtDateTime(j.finished_at)}</TD>
                <TD className="max-w-md text-xs">
                  {j.error ? <div className="text-red-700">{j.error}</div> : null}
                  {Object.keys(j.result ?? {}).length ? (
                    <button type="button" className="text-accent-strong hover:underline" onClick={() => setExpanded(expanded === j.id ? null : j.id)}>
                      {expanded === j.id ? "hide result" : "show result"}
                    </button>
                  ) : null}
                  {expanded === j.id ? <pre className="mt-1 max-h-40 overflow-auto rounded bg-zinc-50 p-2 font-mono text-[10px]">{JSON.stringify({ payload: j.payload, result: j.result }, null, 2)}</pre> : null}
                </TD>
                <TD>
                  {j.status === "failed" && j.retryable ? (
                    <Button size="sm" onClick={() => retry(j)}>
                      Retry
                    </Button>
                  ) : null}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
