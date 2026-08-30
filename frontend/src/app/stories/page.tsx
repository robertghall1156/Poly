"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { humanize, labelFormat, relTime } from "@/lib/utils";
import { Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { Badge } from "@/components/ui/badge";
import { Relevance, StatusBadge } from "@/components/badges";

export default function StoriesPage() {
  const [days, setDays] = React.useState(30);
  const [status, setStatus] = React.useState("");
  const [topic, setTopic] = React.useState("");
  const stories = useApi(() => api.stories({ days, status: status || undefined, limit: 300 }), [days, status]);
  const topics = React.useMemo(() => [...new Set((stories.data ?? []).flatMap((s) => s.topics ?? []))].sort(), [stories.data]);
  const rows = (stories.data ?? []).filter((s) => !topic || s.topics.includes(topic));

  return (
    <div>
      <PageHeader
        title="Stories"
        description="Story clusters over time: deduplicated articles, claims with provenance, and how each story evolved."
        actions={
          <>
            <Select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={3}>Last 3 days</option>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={365}>Last year</option>
            </Select>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any status</option>
              <option value="new">New</option>
              <option value="developing">Developing</option>
              <option value="ignored">Ignored</option>
            </Select>
            <Select value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="">Any topic</option>
              {topics.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </>
        }
      />
      <ErrorNotice error={stories.error} className="mb-3" />
      {stories.loading ? <ListSkeleton /> : null}
      {stories.data && rows.length === 0 ? <EmptyState title="No stories yet.">Run ingest from Home, or add feeds under Research → Feeds.</EmptyState> : null}
      {rows.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <TH>Story</TH>
              <TH>Publications</TH>
              <TH className="text-right">Articles</TH>
              <TH>Topics</TH>
              <TH className="text-right">Rel.</TH>
              <TH>Status</TH>
              <TH>Action</TH>
              <TH>Updated</TH>
            </tr>
          </THead>
          <TBody>
            {rows.map((s) => (
              <TR key={s.id}>
                <TD className="max-w-md">
                  <Link href={`/stories/${s.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                    {s.title}
                  </Link>
                  {s.recommended_format ? <div className="text-[11px] text-zinc-400">Recommended: {labelFormat(s.recommended_format)}</div> : null}
                </TD>
                <TD className="text-xs text-zinc-600">{s.publications.join(", ") || "—"}</TD>
                <TD className="text-right tabular-nums">
                  {s.article_count}
                  {s.duplicate_count ? <span className="text-zinc-400"> +{s.duplicate_count}</span> : null}
                </TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    {s.topics.map((t) => (
                      <Badge key={t} variant="neutral">
                        {t}
                      </Badge>
                    ))}
                  </div>
                </TD>
                <TD className="text-right">
                  <Relevance value={s.relevance_score} />
                </TD>
                <TD>
                  <StatusBadge status={s.status} />
                </TD>
                <TD className="text-xs text-zinc-600">{s.dashboard_action === "none" ? "—" : humanize(s.dashboard_action)}</TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{relTime(s.last_updated)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
