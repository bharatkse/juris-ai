import { browserStorage, clearUserStores } from "@/lib/local-store";

export const LOCAL_FEATURES = [
  "memory",
  "projects",
  "pins",
  "documents",
  "preferences",
  "notifications",
  "integrations",
  "api-keys",
  "titles",
] as const;

export function clearLocalUserData(userId: string | undefined): void {
  if (!userId) return;
  const storage = browserStorage();
  if (!storage) return;
  clearUserStores(storage, userId);
}
