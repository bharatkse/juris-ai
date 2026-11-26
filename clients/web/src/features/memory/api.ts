import { apiFetch, jsonRequest } from "@/lib/api/client";
import type { MemoryItem, MemorySettings, Paginated } from "@/types/api";

const MEMORY_ENDPOINT = "/api/backend/memory";

export async function getMemorySettings(
  signal?: AbortSignal,
): Promise<MemorySettings> {
  return apiFetch<MemorySettings>(`${MEMORY_ENDPOINT}/settings`, { signal });
}

export async function updateMemorySettings(
  enabled: boolean,
): Promise<MemorySettings> {
  return apiFetch<MemorySettings>(
    `${MEMORY_ENDPOINT}/settings`,
    jsonRequest({ enabled }, { method: "PUT" }),
  );
}

export async function listMemories(
  offset = 0,
  limit = 20,
  signal?: AbortSignal,
): Promise<Paginated<MemoryItem>> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  return apiFetch<Paginated<MemoryItem>>(
    `${MEMORY_ENDPOINT}/items?${params.toString()}`,
    { signal },
  );
}

export async function getMemory(
  id: string,
  signal?: AbortSignal,
): Promise<MemoryItem> {
  return apiFetch<MemoryItem>(
    `${MEMORY_ENDPOINT}/items/${encodeURIComponent(id)}`,
    { signal },
  );
}

export async function deleteMemory(id: string): Promise<void> {
  return apiFetch<void>(
    `${MEMORY_ENDPOINT}/items/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}
