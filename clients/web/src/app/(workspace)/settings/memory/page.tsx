import type { Metadata } from "next";

import { MemoryWorkspace } from "@/features/memory/components/memory-workspace";

export const metadata: Metadata = { title: "Memory" };

export default function Page() {
  return <MemoryWorkspace />;
}
