import type { Metadata } from "next";

import { AdminPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Admin" };

export default function Page() {
  return <AdminPage />;
}
