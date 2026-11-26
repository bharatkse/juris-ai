import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SettingsNav } from "@/components/layout/settings-nav";
import { WorkspaceHotkeys } from "@/components/layout/workspace-hotkeys";

export const metadata: Metadata = {
  title: "Settings",
  robots: { index: false, follow: false },
};

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background md:flex-row">
      <WorkspaceHotkeys />
      <SettingsNav />
      <main id="main-content" className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-8">{children}</div>
      </main>
    </div>
  );
}
