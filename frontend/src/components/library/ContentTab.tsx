"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { labelFormat, relTime } from "@/lib/utils";
import { Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { FactCheckDot, FormatBadge, StatusBadge } from "@/components/badges";
import { labelStatus } from "@/lib/utils";

export function ContentTab() {
  const [status, setStatus] = React.useState("");
  const [format, setFormat] = React.useState("");
  const items = useApi(() => api.content({ status: status || undefined, format: format || undefined }), [status, format]);
  const formats = useApi(() => api.contentFormats(), []);
  const router = useRouter();

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {(formats.data?.statuses ?? []).map((s) => (
            <option key={s} value={s}>
              {labelStatus(s)}
            </option>
          ))}
        </Select>
        <Select value={format} onChange={(e) => setFormat(e.target.value)}>
          <option value="">Any format</option>
          {(formats.data?.formats ?? []).map((f) => (
            <option key={f} value={f}>
              {labelFormat(f)}
            </option>
          ))}
        </Select>
      </div>
      <ErrorNotice error={items.error} className="mb-3" />
      {items.loading ? <ListSkeleton /> : null}
      {items.data && items.data.length === 0 ? (
        <EmptyState title="No drafts yet.">Press &ldquo;+ Create&rdquo; in the top bar to make your first one.</EmptyState>
      ) : null}
      {items.data && items.data.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <TH>Draft</TH>
              <TH>Format</TH>
              <TH>Status</TH>
              <TH>Facts</TH>
              <TH>Updated</TH>
            </tr>
          </THead>
          <TBody>
            {items.data.map((c) => (
              <TR key={c.id} className="cursor-pointer hover:bg-accent-soft/40" onClick={() => router.push(`/library/content/${c.id}`)}>
                <TD className="max-w-md">
                  <span className="font-medium text-zinc-900">{c.title}</span>
                  {c.script_preview ? <div className="line-clamp-1 text-xs text-zinc-400">{c.script_preview}</div> : null}
                </TD>
                <TD>
                  <FormatBadge format={c.format} />
                </TD>
                <TD>
                  <StatusBadge status={c.status} />
                </TD>
                <TD className="whitespace-nowrap text-xs text-zinc-600">
                  <FactCheckDot status={c.fact_check_status} className="mr-1.5" />
                  {labelStatus(c.fact_check_status)}
                  {c.unresolved_claims ? <span className="ml-1 font-medium text-danger">({c.unresolved_claims})</span> : null}
                </TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{relTime(c.updated_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
