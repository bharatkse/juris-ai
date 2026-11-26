import {
  deleteMemory,
  getMemory,
  getMemorySettings,
  listMemories,
  updateMemorySettings,
} from "@/features/memory/api";
import {
  filterAndSortMemories,
  memoryItemToRecord,
  type MemoryDraft,
  type MemoryRecord,
  type MemoryRepository,
} from "@/features/memory/types";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import type { MemoryItem, MemorySettings } from "@/types/api";

const ITEMS = "/api/backend/memory/items";

async function loadAll(signal?: AbortSignal): Promise<MemoryRecord[]> {
  const records: MemoryRecord[] = [];
  let offset = 0;
  const limit = 50;
  for (;;) {
    const page = await listMemories(offset, limit, signal);
    records.push(...page.items.map(memoryItemToRecord));
    if (!page.pagination.has_more) break;
    offset += page.pagination.limit;
  }
  return records;
}

export const httpMemoryRepository: MemoryRepository = {
  persistence: "http",

  getSettings(signal) {
    return getMemorySettings(signal);
  },

  setEnabled(enabled) {
    return updateMemorySettings(enabled);
  },

  async list(query, signal) {
    return filterAndSortMemories(await loadAll(signal), query);
  },

  async get(id, signal) {
    const item = await getMemory(id, signal);
    return memoryItemToRecord(item);
  },

  async create(draft: MemoryDraft): Promise<MemoryRecord> {
    const content = draft.title.trim()
      ? `${draft.title.trim()}\n\n${draft.content}`
      : draft.content;
    const item = await apiFetch<MemoryItem>(
      ITEMS,
      jsonRequest(
        { content, kind: draft.kind ?? "note" },
        { method: "POST" },
      ),
    );
    return memoryItemToRecord(item);
  },

  async update(id, draft): Promise<MemoryRecord> {
    const current = await getMemory(id);
    const title = draft.title ?? titleFromFirstLine(current.content);
    const body = draft.content ?? stripTitle(current.content);
    const content = title ? `${title}\n\n${body}` : body;
    const item = await apiFetch<MemoryItem>(
      `${ITEMS}/${encodeURIComponent(id)}`,
      jsonRequest(
        { content, kind: draft.kind ?? current.kind },
        { method: "PATCH" },
      ),
    );
    return memoryItemToRecord(item);
  },

  delete(id) {
    return deleteMemory(id);
  },

  async clearAll() {
    await apiFetch<MemorySettings>(
      "/api/backend/memory/settings",
      jsonRequest({ enabled: false }, { method: "PUT" }),
    );
    await apiFetch<MemorySettings>(
      "/api/backend/memory/settings",
      jsonRequest({ enabled: true }, { method: "PUT" }),
    );
  },
};

function titleFromFirstLine(content: string): string {
  return content.trim().split(/\n/u)[0] ?? "";
}

function stripTitle(content: string): string {
  const lines = content.split(/\n/u);
  if (lines.length <= 1) return content;
  return lines.slice(1).join("\n").replace(/^\n/u, "");
}
