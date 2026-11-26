import { apiFetch } from "@/lib/api/client";
import type { HealthStatus } from "@/types/api";

export async function getBackendHealth(
  signal?: AbortSignal,
): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/api/backend/health", { signal });
}
