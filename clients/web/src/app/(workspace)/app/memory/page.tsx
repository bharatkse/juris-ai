import { redirect } from "next/navigation";

export default function LegacyMemoryPage() {
  redirect("/settings/memory");
}
