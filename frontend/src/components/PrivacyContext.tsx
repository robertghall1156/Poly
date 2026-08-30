"use client";

import * as React from "react";
import { api } from "@/lib/api";
import type { Privacy } from "@/lib/types";

interface Ctx {
  privacy: Privacy | null;
  reload: () => Promise<void>;
}

const PrivacyCtx = React.createContext<Ctx>({ privacy: null, reload: async () => {} });

export function PrivacyProvider({ children }: { children: React.ReactNode }) {
  const [privacy, setPrivacy] = React.useState<Privacy | null>(null);
  const reload = React.useCallback(async () => {
    try {
      setPrivacy(await api.privacy());
    } catch {
      setPrivacy(null);
    }
  }, []);
  React.useEffect(() => {
    void reload();
  }, [reload]);
  return <PrivacyCtx.Provider value={{ privacy, reload }}>{children}</PrivacyCtx.Provider>;
}

export function usePrivacy() {
  return React.useContext(PrivacyCtx);
}
