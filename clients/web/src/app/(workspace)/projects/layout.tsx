import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "Projects",
  robots: { index: false, follow: false },
};

export default function ProjectsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
