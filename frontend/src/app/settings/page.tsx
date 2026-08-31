"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Tabs } from "@/components/ui/tabs";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { LocalAITab } from "@/components/settings/LocalAITab";
import { PrivacyTab } from "@/components/settings/PrivacyTab";
import { ContentTab, GithubTab, KeysTab, MediaTab, NewsTab } from "@/components/settings/SimpleTabs";
import { JobsTab } from "@/components/settings/JobsTab";
import { BrandTab } from "@/components/settings/BrandTab";

const TABS = [
  { id: "brand", label: "Brand" },
  { id: "local-ai", label: "Local AI" },
  { id: "privacy", label: "Privacy & Network" },
  { id: "news", label: "News" },
  { id: "media", label: "Media" },
  { id: "content", label: "Content" },
  { id: "github", label: "GitHub" },
  { id: "keys", label: "AI keys" },
  { id: "jobs", label: "Jobs" },
];

export default function SettingsPage() {
  return (
    <React.Suspense fallback={<ListSkeleton />}>
      <SettingsInner />
    </React.Suspense>
  );
}

function SettingsInner() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? (params.get("tab") as string) : "local-ai";
  const settings = useApi(() => api.settings(), []);
  const s = settings.data;
  return (
    <div>
      <PageHeader title="Settings" description="Local AI, privacy, news, media, content defaults and jobs. Everything is stored in the local database." />
      <Tabs tabs={TABS} value={tab} onChange={(id) => router.replace(`/settings?tab=${id}`)} className="mb-4" />
      <ErrorNotice error={settings.error} className="mb-3" />
      {settings.loading && !s ? <ListSkeleton /> : null}
      {tab === "brand" ? <BrandTab settings={s} onChanged={() => settings.reload()} /> : null}
      {tab === "local-ai" ? <LocalAITab settings={s} /> : null}
      {tab === "privacy" ? <PrivacyTab settings={s} onChanged={() => settings.reload()} /> : null}
      {s && tab === "news" ? <NewsTab settings={s} onChanged={() => settings.reload()} /> : null}
      {s && tab === "media" ? <MediaTab settings={s} onChanged={() => settings.reload()} /> : null}
      {s && tab === "content" ? <ContentTab settings={s} onChanged={() => settings.reload()} /> : null}
      {s && tab === "github" ? <GithubTab settings={s} onChanged={() => settings.reload()} /> : null}
      {s && tab === "keys" ? <KeysTab settings={s} /> : null}
      {tab === "jobs" ? <JobsTab /> : null}
    </div>
  );
}
