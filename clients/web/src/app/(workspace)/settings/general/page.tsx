import type { Metadata } from "next";

import { GeneralPage } from "@/features/settings/components/general-page";

export const metadata: Metadata = { title: "General" };

export default function Page() {
  return <GeneralPage />;
}
