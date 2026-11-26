import type { Metadata } from "next";

import { ApiKeysPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "API keys" };

export default function Page() {
  return <ApiKeysPage />;
}
