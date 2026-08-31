"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Tabs } from "@/components/ui/tabs";
import { ListSkeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/ui/section";
import { ContentTab } from "@/components/library/ContentTab";
import { VideosTab } from "@/components/library/VideosTab";
import { ImagesTab } from "@/components/library/ImagesTab";
import { BookTab } from "@/components/library/BookTab";

const TABS = [
  { id: "content", label: "Content" },
  { id: "videos", label: "Videos" },
  { id: "images", label: "Images" },
  { id: "book", label: "Book" },
];

export default function LibraryPage() {
  return (
    <React.Suspense fallback={<ListSkeleton />}>
      <LibraryInner />
    </React.Suspense>
  );
}

function LibraryInner() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? (params.get("tab") as string) : "content";
  return (
    <div>
      <PageHeader title="Library" description="Everything you've made or collected: drafts, videos, images and your book." />
      <Tabs tabs={TABS} value={tab} onChange={(id) => router.replace(`/library?tab=${id}`)} className="mb-4" />
      {tab === "content" ? <ContentTab /> : tab === "videos" ? <VideosTab /> : tab === "images" ? <ImagesTab /> : <BookTab />}
    </div>
  );
}
