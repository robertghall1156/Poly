"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import { relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader, Panel, Section } from "@/components/ui/section";
import { Confidence, StatusBadge } from "@/components/badges";
import { usePrivacy } from "@/components/PrivacyContext";

function NewSessionForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { privacy } = usePrivacy();
  const presetStory = params.get("story") ?? "";
  const stories = useApi(() => api.stories({ days: 60, limit: 200 }), []);
  const principles = useApi(() => api.principles(), []);
  const [title, setTitle] = React.useState("");
  const [question, setQuestion] = React.useState("");
  const [storyId, setStoryId] = React.useState(presetStory);
  const [principleId, setPrincipleId] = React.useState("");
  const act = useAction();

  React.useEffect(() => {
    if (presetStory && stories.data && !title) {
      const s = stories.data.find((x) => x.id === presetStory);
      if (s) setTitle(s.title);
    }
  }, [presetStory, stories.data, title]);

  const submit = async () => {
    const s = await act.run(() => api.startThink({ title: title.trim(), story_id: storyId || null, principle_id: principleId || null, question, ask_first_question: true }));
    if (s) router.push(`/think/${s.id}`);
  };

  return (
    <Panel title="New session">
      <div className="space-y-3">
        <Field label="Title">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What are you trying to work out?" />
        </Field>
        <Field label="Question" hint="(optional)">
          <Textarea rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Frame the policy question in your own words" />
        </Field>
        <Field label="Story" hint="(optional)">
          <Select value={storyId} onChange={(e) => setStoryId(e.target.value)} className="w-full">
            <option value="">None</option>
            {(stories.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Principle" hint="(optional)">
          <Select value={principleId} onChange={(e) => setPrincipleId(e.target.value)} className="w-full">
            <option value="">None</option>
            {(principles.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </Select>
        </Field>
        <ErrorNotice error={act.error} />
        <Button variant={privacy?.cloud_ai_permitted ? "warn" : "default"} onClick={submit} loading={act.busy} disabled={!title.trim()}>
          {privacy?.cloud_ai_permitted ? "Start (cloud AI may be used)" : "Start session"}
        </Button>
        <p className="text-xs text-zinc-500">The interviewer asks one substantive question at a time, compares your answers with existing principles, and surfaces the strongest opposing case before you commit to a position.</p>
      </div>
    </Panel>
  );
}

export default function ThinkPage() {
  const sessions = useApi(() => api.thinkSessions(), []);
  const stories = useApi(() => api.stories({ days: 365, limit: 500 }), []);
  const briefs = useApi(() => api.briefs(), []);
  const storyTitle = (id: string | null) => (id ? stories.data?.find((s) => s.id === id)?.title ?? id.slice(0, 8) : "—");

  return (
    <div>
      <PageHeader title="Think Mode" description="Interview yourself against a story or policy question, then produce a Position Brief and approve it into the operating system." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <Section title="Sessions">
            <ErrorNotice error={sessions.error} className="mb-2" />
            {sessions.loading ? <ListSkeleton rows={3} /> : null}
            {sessions.data && sessions.data.length === 0 ? <EmptyState title="No think sessions yet.">Start one on the right, or use “Develop Position” on a story.</EmptyState> : null}
            {sessions.data && sessions.data.length > 0 ? (
              <Table>
                <THead>
                  <tr>
                    <TH>Title</TH>
                    <TH>Status</TH>
                    <TH className="text-right">Exchanges</TH>
                    <TH>Story</TH>
                    <TH>Briefs</TH>
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
                      <TD className="max-w-[16rem] truncate text-xs text-zinc-600">
                        {s.story_id ? (
                          <Link href={`/stories/${s.story_id}`} className="hover:text-accent-strong">
                            {storyTitle(s.story_id)}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </TD>
                      <TD className="text-xs">
                        {s.brief_ids.map((b) => (
                          <Link key={b} href={`/think/briefs/${b}`} className="mr-1 text-accent-strong hover:underline">
                            brief
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
          </Section>
          <Section title="Position briefs">
            {briefs.data && briefs.data.length === 0 ? <EmptyState title="No briefs yet." /> : null}
            {briefs.data && briefs.data.length > 0 ? (
              <Table>
                <THead>
                  <tr>
                    <TH>Issue</TH>
                    <TH>Position</TH>
                    <TH>Status</TH>
                    <TH>Confidence</TH>
                    <TH>Created</TH>
                  </tr>
                </THead>
                <TBody>
                  {briefs.data.map((b) => (
                    <TR key={b.id}>
                      <TD>
                        <Link href={`/think/briefs/${b.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
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
          </Section>
        </div>
        <React.Suspense fallback={null}>
          <NewSessionForm />
        </React.Suspense>
      </div>
    </div>
  );
}
