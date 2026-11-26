import type { Metadata } from "next";

import { UsagePage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Usage" };

export default function Page() {
  return <UsagePage />;
}
