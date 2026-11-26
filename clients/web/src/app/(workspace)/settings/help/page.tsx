import type { Metadata } from "next";

import { HelpPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Help" };

export default function Page() {
  return <HelpPage />;
}
