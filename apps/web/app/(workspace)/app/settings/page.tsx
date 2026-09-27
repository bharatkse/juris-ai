import type { Metadata } from "next";

import { SettingsContent } from "@/components/settings/settings-content";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return <SettingsContent />;
}
