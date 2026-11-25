import type { Metadata } from "next";

import { MemorySettingsPanel } from "@/features/memory/components/memory-settings";

export const metadata: Metadata = {
  title: "Memory",
};

export default function MemoryPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-10 sm:px-8 sm:py-12">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">
          Account
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em]">
          Memory
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Control long-term facts the assistant stores about you.
        </p>
      </div>
      <MemorySettingsPanel />
    </div>
  );
}
