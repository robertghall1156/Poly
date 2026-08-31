"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import type { AllSettings } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { Panel } from "@/components/ui/section";
import { DEFAULT_BRAND, useBrand, type BrandTokens } from "@/components/BrandContext";

const COLOR_FIELDS: { key: keyof BrandTokens; label: string; hint: string }[] = [
  { key: "primary", label: "Primary", hint: "headlines, main buttons" },
  { key: "accent", label: "Accent", hint: "links, highlights, active items" },
  { key: "secondary", label: "Secondary", hint: "supporting text and icons" },
  { key: "background", label: "Background", hint: "page background" },
  { key: "highlight", label: "Highlight", hint: "emphasis in videos and images" },
];

export function BrandTab({ settings, onChanged }: { settings: AllSettings | null; onChanged: () => void }) {
  const { reload } = useBrand();
  const [brand, setBrand] = React.useState<BrandTokens>(DEFAULT_BRAND);
  const [saved, setSaved] = React.useState(false);
  const act = useAction();

  React.useEffect(() => {
    if (settings) setBrand({ ...DEFAULT_BRAND, ...((settings.brand as Partial<BrandTokens> | undefined) ?? {}) });
  }, [settings]);

  const set = (key: keyof BrandTokens, value: string) => {
    setBrand((b) => ({ ...b, [key]: value }));
    setSaved(false);
  };

  const save = async () => {
    const r = await act.run(() => api.patchSettings("brand", brand as unknown as Record<string, unknown>));
    if (r) {
      setSaved(true);
      onChanged();
      void reload();
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-4">
        <Panel title="Colors">
          <div className="space-y-3">
            {COLOR_FIELDS.map((f) => (
              <div key={String(f.key)} className="flex items-center gap-3">
                <input
                  type="color"
                  value={String(brand[f.key] || "#000000")}
                  onChange={(e) => set(f.key, e.target.value)}
                  className="h-8 w-10 shrink-0 cursor-pointer rounded border border-zinc-300"
                  aria-label={f.label}
                />
                <div className="w-24">
                  <p className="text-[13px] font-medium text-zinc-800">{f.label}</p>
                  <p className="text-[11px] text-zinc-400">{f.hint}</p>
                </div>
                <Input value={String(brand[f.key] ?? "")} onChange={(e) => set(f.key, e.target.value)} className="max-w-[9rem] font-mono text-xs" />
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Identity">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Logo text" hint="shown in the sidebar and on videos">
              <Input value={String(brand.logo_text ?? "")} onChange={(e) => set("logo_text", e.target.value)} placeholder="Poly" />
            </Field>
            <Field label="Font" hint="font family name, optional">
              <Input value={String(brand.font ?? "")} onChange={(e) => set("font", e.target.value)} placeholder="System default" />
            </Field>
          </div>
        </Panel>
        <div className="flex items-center gap-2">
          <Button variant="default" onClick={save} loading={act.busy}>
            Save brand
          </Button>
          {saved ? <span className="text-xs text-emerald-700">Saved — applied everywhere.</span> : null}
        </div>
        <ErrorNotice error={act.error} />
        <Notice>Your videos, memes and carousels are rendered with these exact colors, and the app itself uses them too.</Notice>
      </div>

      <aside>
        <Panel title="Live preview">
          <div className="overflow-hidden rounded-md border border-zinc-200" style={{ background: String(brand.background) }}>
            <div className="p-4">
              <p className="text-sm font-semibold" style={{ color: String(brand.primary) }}>
                {String(brand.logo_text || "Poly")}
              </p>
              <p className="mt-1 text-xs" style={{ color: String(brand.secondary) }}>
                One person, one vote — but not one voice?
              </p>
              <div className="mt-3 flex gap-2">
                <span className="rounded px-2 py-1 text-[11px] font-medium text-white" style={{ background: String(brand.primary) }}>
                  Primary
                </span>
                <span className="rounded px-2 py-1 text-[11px] font-medium text-white" style={{ background: String(brand.accent) }}>
                  Accent
                </span>
                <span className="rounded px-2 py-1 text-[11px] font-medium" style={{ background: String(brand.highlight), color: String(brand.primary) }}>
                  Highlight
                </span>
              </div>
              <div className="mt-3 flex gap-1.5">
                {COLOR_FIELDS.map((f) => (
                  <span key={String(f.key)} title={f.label} className="h-6 w-6 rounded-full border border-black/10" style={{ background: String(brand[f.key]) }} />
                ))}
              </div>
            </div>
          </div>
        </Panel>
      </aside>
    </div>
  );
}
