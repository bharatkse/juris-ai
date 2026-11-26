import type { Metadata } from "next";

import { PrivacyPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Data & privacy" };

export default function Page() {
  return <PrivacyPage />;
}
