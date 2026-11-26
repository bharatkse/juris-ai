import type { Metadata } from "next";

import { PermissionsPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Permissions" };

export default function Page() {
  return <PermissionsPage />;
}
