"use client";

import * as React from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { PrivacyProvider } from "./PrivacyContext";
import { BrandProvider } from "./BrandContext";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <BrandProvider>
      <PrivacyProvider>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            <main className="flex-1 overflow-y-auto">
              <div className="mx-auto w-full max-w-6xl px-6 py-5">{children}</div>
            </main>
          </div>
        </div>
      </PrivacyProvider>
    </BrandProvider>
  );
}
