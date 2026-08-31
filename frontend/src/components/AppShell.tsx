"use client";

import * as React from "react";
import { Sidebar } from "./Sidebar";
import { PrivacyProvider } from "./PrivacyContext";
import { BrandProvider } from "./BrandContext";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <BrandProvider>
      <PrivacyProvider>
        <div className="flex h-screen overflow-hidden">
          <React.Suspense fallback={<aside className="h-screen w-[216px] shrink-0 border-r-2 border-divider bg-paper" />}>
            <Sidebar />
          </React.Suspense>
          <main className="min-w-0 flex-1 overflow-y-auto">
            <div className="w-full max-w-[1080px] px-14 pb-20 pt-11 max-lg:px-6 max-lg:pt-6">{children}</div>
          </main>
        </div>
      </PrivacyProvider>
    </BrandProvider>
  );
}
