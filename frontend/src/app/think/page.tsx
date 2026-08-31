"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { Confidence, StatusBadge } from "@/components/badges";
import { NewThinkDialog } from "@/components/CreateLauncher";
import { BeliefsTab } from "@/components/think/BeliefsTab";

const TABS = [
  { id: "ideas", label: "My ideas" },
  { id: "positions", label: "My positions" },
  { id: "beliefs", label: "What I believe" },
];

export default function ThinkPage() {
  return (
    <React.Suspense fallback={<ListSkeleton />}>
      <ThinkInner />
    </React.Suspense>
  );
}

function ThinkInner() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? (params.get("tab") as string) : "ideas";
  return (
    <div>
      <PageHeader title="Think" description="Work out what you actually believe before you publish anything." />
      <Tabs tabs={TABS} value={tab} onChange={(id) => router.replace(`/think?tab=${id}`)} className="mb-4" />
      {tab === "ideas" ? <IdeasTab presetStory={params.get("story")} /> : tab === "positions" ? <PositionsTab /> : <BeliefsTab />}
    </div>
  );
}

function IdeasTab({ presetStory }: { presetStory: string | null }) {
  const sessions = useApi(() => api.thinkSessions(), []);
  const story = useApi(() => (presetStory ? api.story(presetStory) : Promise.resolve(null)), [presetStory]);
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    if (presetStory && story.data) setOpen(true);
  }, [presetStory, story.data]);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-[13px] text-zinc-500">One question at a time, including the strongest case against you.</p>
        <Button variant="default" onClick={() => setOpen(true)}>
          New idea
        </Button>
      </div>
      <ErrorNotice error={sessions.error} className="mb-2" />
      {sessions.loading ? <ListSkeleton rows={3} /> : null}
      {sessions.data && sessions.data.length === 0 ? (
        <EmptyState title="No ideas in progress.">Press &ldquo;New idea&rdquo; above, or &ldquo;Think this through&rdquo; on any story.</EmptyState>
      ) : null}
      {sessions.data && sessions.data.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <TH>Idea</TH>
              <TH>Status</TH>
              <TH className="text-right">Exchanges</TH>
              <TH>Positions</TH>
              <TH>Updated</TH>
            </tr>
          </THead>
          <TBody>
            {sessions.data.map((s) => (
              <TR key={s.id}>
                <TD>
                  <Link href={`/think/${s.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                    {s.title}
                  </Link>
                </TD>
                <TD>
                  <StatusBadge status={s.status} />
                </TD>
                <TD className="text-right tabular-nums">{s.exchanges}</TD>
                <TD className="text-xs">
                  {s.brief_ids.map((b) => (
                    <Link key={b} href={`/think/positions/${b}`} className="mr-1 text-accent-strong hover:underline">
                      position
                    </Link>
                  ))}
                  {s.brief_ids.length === 0 ? "—" : null}
                </TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{relTime(s.updated_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
      <NewThinkDialog open={open} onClose={() => setOpen(false)} defaults={presetStory && story.data ? { title: story.data.title, story_id: presetStory } : undefined} />
    </div>
  );
}

function PositionsTab() {
  const briefs = useApi(() => api.briefs(), []);
  return (
    <div>
      <p className="mb-3 text-[13px] text-zinc-500">Positions you&apos;ve drafted. Approving one makes it part of what you believe.</p>
      <ErrorNotice error={briefs.error} className="mb-2" />
      {briefs.loading ? <ListSkeleton rows={3} /> : null}
      {briefs.data && briefs.data.length === 0 ? <EmptyState title="No positions yet.">Finish thinking through an idea, then draft your position from it.</EmptyState> : null}
      {briefs.data && briefs.data.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <TH>Issue</TH>
              <TH>My position</TH>
              <TH>Status</TH>
              <TH>Confidence</TH>
              <TH>Created</TH>
            </tr>
          </THead>
          <TBody>
            {briefs.data.map((b) => (
              <TR key={b.id}>
                <TD>
                  <Link href={`/think/positions/${b.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                    {b.issue}
                  </Link>
                </TD>
                <TD className="max-w-md text-xs text-zinc-600">{b.position}</TD>
                <TD>
                  <StatusBadge status={b.status} />
                </TD>
                <TD>
                  <Confidence value={b.confidence} />
                </TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{relTime(b.created_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
