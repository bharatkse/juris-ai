import type { Metadata } from "next";

import { MemoryWorkspace } from "@/features/memory/components/memory-workspace";

export const metadata: Metadata = { title: "Memory" };

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MemoryWorkspace selectedId={id} />;
}
