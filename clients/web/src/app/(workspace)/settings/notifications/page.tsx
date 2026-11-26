import type { Metadata } from "next";

import { NotificationsPage } from "@/features/settings/components/placeholder-pages";

export const metadata: Metadata = { title: "Notifications" };

export default function Page() {
  return <NotificationsPage />;
}
