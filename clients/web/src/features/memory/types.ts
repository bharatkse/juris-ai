import type { MemoryItem, MemorySettings } from "@/types/api";

export interface MemoryRecord {
  id: string;
  title: string;
  content: string;
  kind: string;
  status: string;
  source: string | null;
  source_conversation_id: string | null;
  created_at: string;
  updated_at: string;
  confidence: number;
}

export interface MemoryDraft {
  title: string;
  content: string;
  kind?: string;
}

export type MemorySort = "updated" | "created";

export interface MemoryListQuery {
  search?: string;
  sort?: MemorySort;
  kind?: string;
}

export interface MemoryRepository {
  readonly persistence: "http" | "local";
  getSettings(signal?: AbortSignal): Promise<MemorySettings>;
  setEnabled(enabled: boolean): Promise<MemorySettings>;
  list(query?: MemoryListQuery, signal?: AbortSignal): Promise<MemoryRecord[]>;
  get(id: string, signal?: AbortSignal): Promise<MemoryRecord>;
  create(draft: MemoryDraft): Promise<MemoryRecord>;
  update(id: string, draft: Partial<MemoryDraft>): Promise<MemoryRecord>;
  delete(id: string): Promise<void>;
  clearAll(): Promise<void>;
}

export function titleFromContent(content: string, explicit?: string): string {
  const trimmed = explicit?.trim();
  if (trimmed) return trimmed;
  const firstLine = content.trim().split(/\n/u)[0] ?? "";
  return firstLine.slice(0, 80) || "Untitled memory";
}

export function memoryItemToRecord(item: MemoryItem): MemoryRecord {
  return {
    id: item.id,
    title: titleFromContent(item.content),
    content: item.content,
    kind: item.kind,
    status: item.status,
    source: item.source_conversation_id ?? null,
    source_conversation_id: item.source_conversation_id ?? null,
    created_at: item.created_at,
    updated_at: item.last_used_at || item.created_at,
    confidence: item.confidence,
  };
}

export function filterAndSortMemories(
  items: readonly MemoryRecord[],
  query: MemoryListQuery = {},
): MemoryRecord[] {
  const search = query.search?.trim().toLocaleLowerCase() ?? "";
  const kind = query.kind?.trim();
  let next = [...items];
  if (kind) {
    next = next.filter((item) => item.kind === kind);
  }
  if (search) {
    next = next.filter(
      (item) =>
        item.title.toLocaleLowerCase().includes(search) ||
        item.content.toLocaleLowerCase().includes(search),
    );
  }
  const sort = query.sort ?? "updated";
  next.sort((left, right) => {
    const field = sort === "created" ? "created_at" : "updated_at";
    return new Date(right[field]).getTime() - new Date(left[field]).getTime();
  });
  return next;
}
