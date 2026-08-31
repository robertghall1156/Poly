"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import { humanize, relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";

export function ImagesTab() {
  const images = useApi(() => api.images(), []);
  const act = useAction();
  const toggle = async (id: string, approved: boolean) => {
    const r = await act.run(() => api.approveImage(id, approved));
    if (r) images.setData((prev) => (prev ? prev.map((x) => (x.id === id ? r : x)) : prev));
  };
  return (
    <div>
      <ErrorNotice error={images.error ?? act.error} className="mb-3" />
      {images.loading ? <ListSkeleton /> : null}
      {images.data && images.data.length === 0 ? (
        <EmptyState title="No images yet.">Memes and quote cards you make appear here for approval and download.</EmptyState>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(images.data ?? []).map((im) => (
          <div key={im.id} className="rounded-md border border-zinc-200 bg-white p-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={api.imageFileUrl(im.id)} alt={im.title} className="aspect-square w-full rounded bg-zinc-100 object-cover" loading="lazy" />
            <p className="mt-1.5 truncate text-[13px] font-medium text-zinc-900">{im.title || "Untitled"}</p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
              <Badge variant="outline">{humanize(im.kind)}</Badge>
              {im.approved ? <Badge variant="success">Approved</Badge> : <Badge variant="neutral">Needs approval</Badge>}
              <span className="text-[11px] text-zinc-400">{relTime(im.created_at)}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <a href={api.imageFileUrl(im.id)} download className="inline-flex h-7 items-center rounded-md border border-zinc-300 bg-white px-2.5 text-xs font-medium text-zinc-800 hover:bg-zinc-50">
                Download
              </a>
              <Button size="sm" variant={im.approved ? "ghost" : "accent"} onClick={() => toggle(im.id, !im.approved)}>
                {im.approved ? "Unapprove" : "Approve"}
              </Button>
              {im.content_item_id ? (
                <Link href={`/library/content/${im.content_item_id}`} className="ml-auto text-xs text-accent-strong hover:underline">
                  Draft
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
