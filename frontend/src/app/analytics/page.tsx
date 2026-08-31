"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { AnalyticsItem } from "@/lib/types";
import { fmtDate, fmtDuration, fmtNumber, labelFormat } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Panel, Section } from "@/components/ui/section";

const CSV_COLUMNS = ["content_item_id (or title)", "platform", "recorded_at", "views", "watch_time_seconds", "retention_pct", "likes", "comments", "shares", "subscribers_gained", "completion_pct"];

export default function AnalyticsPage() {
  const data = useApi(() => api.analytics(), []);
  const [file, setFile] = React.useState<File | null>(null);
  const [result, setResult] = React.useState<{ imported: number; skipped: number } | null>(null);
  const act = useAction();
  const importCsv = async () => {
    if (!file) return;
    const r = await act.run(() => api.importMetricsCsv(file));
    if (r) {
      setResult(r);
      data.reload();
    }
  };
  const items = data.data?.items ?? [];

  return (
    <div>
      <PageHeader title="Analytics" description="Engagement against substantive value, so the system never optimises for outrage alone." />
      <ErrorNotice error={data.error} className="mb-3" />
      {data.loading ? <ListSkeleton rows={3} /> : null}
      {data.data ? (
        <p className="mb-3 text-xs text-zinc-500">
          {data.data.published_count} published items · {data.data.with_metrics} with metrics
        </p>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          <Section title="Engagement vs substantive value">
            {items.length === 0 ? <EmptyState title="No published items with metrics.">Publish content and record metrics (per item, or via CSV import on the right).</EmptyState> : <Scatter items={items} />}
          </Section>
          <Section title="Published items">
            {items.length ? (
              <Table>
                <THead>
                  <tr>
                    <TH>Item</TH>
                    <TH>Published</TH>
                    <TH className="text-right">Views</TH>
                    <TH className="text-right">Likes</TH>
                    <TH className="text-right">Comments</TH>
                    <TH className="text-right">Shares</TH>
                    <TH className="text-right">Watch time</TH>
                    <TH className="text-right">Retention</TH>
                    <TH className="text-right">Engagement</TH>
                    <TH className="text-right">Substance</TH>
                    <TH>Quadrant</TH>
                  </tr>
                </THead>
                <TBody>
                  {items.map((i) => (
                    <TR key={i.id}>
                      <TD>
                        <Link href={`/library/content/${i.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                          {i.title}
                        </Link>
                        <div className="text-[11px] text-zinc-400">
                          {labelFormat(i.format)}
                          {i.platform ? ` · ${i.platform}` : ""}
                        </div>
                      </TD>
                      <TD className="whitespace-nowrap text-xs text-zinc-500">{fmtDate(i.publish_date)}</TD>
                      <TD className="text-right tabular-nums">{fmtNumber(i.views)}</TD>
                      <TD className="text-right tabular-nums">{fmtNumber(i.likes)}</TD>
                      <TD className="text-right tabular-nums">{fmtNumber(i.comments)}</TD>
                      <TD className="text-right tabular-nums">{fmtNumber(i.shares)}</TD>
                      <TD className="text-right font-mono text-xs">{fmtDuration(i.watch_time_seconds)}</TD>
                      <TD className="text-right tabular-nums">{i.retention_pct != null ? `${i.retention_pct}%` : "—"}</TD>
                      <TD className="text-right tabular-nums">{fmtNumber(i.engagement)}</TD>
                      <TD className="text-right tabular-nums">
                        {i.substantive_value.toFixed(1)}
                        <span className="ml-1 text-[10px] text-zinc-400">
                          {i.verified_claims}/{i.total_claims}
                        </span>
                      </TD>
                      <TD>
                        <QuadrantBadge q={i.quadrant} />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : null}
          </Section>
        </div>
        <aside className="space-y-3">
          <Panel title="Import metrics from CSV">
            <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-xs" />
            <Button variant="default" className="mt-2" onClick={importCsv} disabled={!file} loading={act.busy}>
              Import
            </Button>
            <ErrorNotice error={act.error} className="mt-2" />
            {result ? (
              <Notice kind="success" className="mt-2">
                Imported {result.imported} rows, skipped {result.skipped}.
              </Notice>
            ) : null}
            <p className="mt-3 text-xs font-medium text-zinc-700">Expected columns</p>
            <ul className="mt-1 grid grid-cols-2 gap-x-2 font-mono text-[11px] text-zinc-600">
              {CSV_COLUMNS.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-zinc-500">Rows are matched by content_item_id, falling back to an exact title match. Unmatched rows are skipped.</p>
          </Panel>
          <Panel title="Substantive value">
            <p className="text-xs text-zinc-600">Owner-rated (set substantive_value on a content item) or derived from fact-check density: 2.5 + 2.5 × verified / total claims. Engagement = views + 5×likes + 10×comments + 15×shares.</p>
          </Panel>
          <Panel title="Platform APIs">
            <p className="text-xs text-zinc-600">Automatic import from YouTube, TikTok and X analytics is a future adapter. Manual entry and CSV import are available now.</p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function QuadrantBadge({ q }: { q?: string }) {
  if (!q) return null;
  const v = q.startsWith("high engagement + high") ? "success" : q.startsWith("high engagement + low") ? "warn" : q.includes("high substance") ? "accent" : "neutral";
  return <Badge variant={v}>{q}</Badge>;
}

function Scatter({ items }: { items: AnalyticsItem[] }) {
  const W = 640;
  const H = 360;
  const P = { l: 44, r: 16, t: 16, b: 36 };
  const maxE = Math.max(1, ...items.map((i) => i.engagement));
  const med = [...items.map((i) => i.engagement)].sort((a, b) => a - b)[Math.floor(items.length / 2)] ?? 0;
  const x = (e: number) => P.l + (e / maxE) * (W - P.l - P.r);
  const y = (s: number) => H - P.b - (Math.max(0, Math.min(5, s)) / 5) * (H - P.t - P.b);
  const xm = x(med);
  const ym = y(3);
  const [hover, setHover] = React.useState<AnalyticsItem | null>(null);
  return (
    <div className="rounded-md border border-zinc-200 bg-white p-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Engagement versus substantive value">
        <rect x={xm} y={P.t} width={W - P.r - xm} height={ym - P.t} fill="#e6f6f7" />
        <rect x={xm} y={ym} width={W - P.r - xm} height={H - P.b - ym} fill="#fdeee9" />
        <rect x={P.l} y={P.t} width={xm - P.l} height={ym - P.t} fill="#f4f4f5" />
        <line x1={P.l} y1={H - P.b} x2={W - P.r} y2={H - P.b} stroke="#a1a1aa" />
        <line x1={P.l} y1={P.t} x2={P.l} y2={H - P.b} stroke="#a1a1aa" />
        <line x1={xm} y1={P.t} x2={xm} y2={H - P.b} stroke="#71717a" strokeDasharray="4 3" />
        <line x1={P.l} y1={ym} x2={W - P.r} y2={ym} stroke="#71717a" strokeDasharray="4 3" />
        <text x={W - P.r - 6} y={P.t + 14} textAnchor="end" fontSize={11} fontWeight={600} fill="#0f6f74">
          High engagement + high substantive value
        </text>
        <text x={W - P.r - 6} y={H - P.b - 8} textAnchor="end" fontSize={11} fontWeight={600} fill="#b3401f">
          High engagement + low substantive value
        </text>
        <text x={P.l + 6} y={P.t + 14} fontSize={11} fill="#52525b">
          Low engagement + high substance
        </text>
        <text x={P.l + 6} y={H - P.b - 8} fontSize={11} fill="#52525b">
          Low engagement + low substance
        </text>
        <text x={(P.l + W - P.r) / 2} y={H - 8} textAnchor="middle" fontSize={11} fill="#52525b">
          Engagement (views + 5×likes + 10×comments + 15×shares) · median {fmtNumber(med)}
        </text>
        <text x={12} y={(P.t + H - P.b) / 2} textAnchor="middle" fontSize={11} fill="#52525b" transform={`rotate(-90 12 ${(P.t + H - P.b) / 2})`}>
          Substantive value (0–5)
        </text>
        {[0, 1, 2, 3, 4, 5].map((v) => (
          <text key={v} x={P.l - 6} y={y(v) + 3} textAnchor="end" fontSize={10} fill="#71717a">
            {v}
          </text>
        ))}
        {items.map((i) => (
          <g key={i.id} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <circle cx={x(i.engagement)} cy={y(i.substantive_value)} r={hover?.id === i.id ? 7 : 5} fill={i.substantive_value >= 3 ? "#1EADB4" : "#F46543"} stroke="#fff" strokeWidth={1.5} />
          </g>
        ))}
        {hover ? (
          <g>
            <rect x={Math.min(x(hover.engagement) + 8, W - 220)} y={Math.max(P.t, y(hover.substantive_value) - 34)} width={210} height={30} rx={3} fill="#18181b" />
            <text x={Math.min(x(hover.engagement) + 14, W - 214)} y={Math.max(P.t, y(hover.substantive_value) - 34) + 12} fontSize={10} fill="#fff">
              {hover.title.slice(0, 40)}
            </text>
            <text x={Math.min(x(hover.engagement) + 14, W - 214)} y={Math.max(P.t, y(hover.substantive_value) - 34) + 24} fontSize={10} fill="#d4d4d8">
              engagement {fmtNumber(hover.engagement)} · substance {hover.substantive_value.toFixed(1)}
            </text>
          </g>
        ) : null}
      </svg>
    </div>
  );
}
