"use client";

import * as React from "react";
import { api } from "@/lib/api";
import type { AllSettings } from "@/lib/types";

export interface BrandTokens {
  primary: string;
  accent: string;
  secondary: string;
  background: string;
  highlight: string;
  font?: string;
  logo_text?: string;
  [k: string]: unknown;
}

export const DEFAULT_BRAND: BrandTokens = {
  primary: "#102A43",
  accent: "#0F766E",
  secondary: "#52667A",
  background: "#F8F9FA",
  highlight: "#C89B3C",
  font: "",
  logo_text: "",
};

interface Ctx {
  settings: AllSettings | null;
  brand: BrandTokens;
  reload: () => Promise<void>;
}

const BrandCtx = React.createContext<Ctx>({ settings: null, brand: DEFAULT_BRAND, reload: async () => {} });

function applyBrand(b: BrandTokens) {
  const root = document.documentElement;
  root.style.setProperty("--brand-primary", b.primary || DEFAULT_BRAND.primary);
  root.style.setProperty("--brand-accent", b.accent || DEFAULT_BRAND.accent);
  root.style.setProperty("--brand-secondary", b.secondary || DEFAULT_BRAND.secondary);
  root.style.setProperty("--brand-bg", b.background || DEFAULT_BRAND.background);
  root.style.setProperty("--brand-highlight", b.highlight || DEFAULT_BRAND.highlight);
}

export function BrandProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = React.useState<AllSettings | null>(null);
  const [brand, setBrand] = React.useState<BrandTokens>(DEFAULT_BRAND);
  const reload = React.useCallback(async () => {
    try {
      const s = await api.settings();
      setSettings(s);
      const b = { ...DEFAULT_BRAND, ...((s.brand as Partial<BrandTokens> | undefined) ?? {}) };
      setBrand(b);
      applyBrand(b);
    } catch {
      // backend unreachable — keep defaults
    }
  }, []);
  React.useEffect(() => {
    void reload();
  }, [reload]);
  return <BrandCtx.Provider value={{ settings, brand, reload }}>{children}</BrandCtx.Provider>;
}

export function useBrand() {
  return React.useContext(BrandCtx);
}
