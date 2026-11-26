import type { Metadata } from "next";

import { IntegrationsPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Integrations" };

export default function Page() {
  return <IntegrationsPage />;
}
