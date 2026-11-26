import {
  filterAndSortMemories,
  titleFromContent,
  type MemoryDraft,
  type MemoryRecord,
  type MemoryRepository,
} from "@/features/memory/types";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

const FEATURE = "memory";
const VERSION = 1;

interface LocalMemoryState {
  enabled: boolean;
  consent_updated_at: string | null;
  items: MemoryRecord[];
}

const emptyState = (): LocalMemoryState => ({
  enabled: true,
  consent_updated_at: null,
  items: [],
});

function nowIso(): string {
  return new Date().toISOString();
}

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function load(userId: string): LocalMemoryState {
  return readVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    emptyState(),
    { version: VERSION },
  );
}

function save(userId: string, state: LocalMemoryState): void {
  writeVersioned(requireStorage(), userStoreKey(userId, FEATURE), state, VERSION);
}

function notFound(id: string): Error {
  return new Error(`Memory ${id} was not found.`);
}

export function createLocalMemoryRepository(userId: string): MemoryRepository {
  return {
    persistence: "local",

    async getSettings() {
      const state = load(userId);
      return {
        enabled: state.enabled,
        consent_updated_at: state.consent_updated_at,
      };
    },

    async setEnabled(enabled) {
      const state = load(userId);
      const next: LocalMemoryState = {
        enabled,
        consent_updated_at: nowIso(),
        items: enabled ? state.items : [],
      };
      save(userId, next);
      return {
        enabled: next.enabled,
        consent_updated_at: next.consent_updated_at,
      };
    },

    async list(query) {
      const state = load(userId);
      if (!state.enabled) return [];
      return filterAndSortMemories(state.items, query);
    },

    async get(id) {
      const item = load(userId).items.find((entry) => entry.id === id);
      if (!item) throw notFound(id);
      return item;
    },

    async create(draft: MemoryDraft) {
      const state = load(userId);
      const timestamp = nowIso();
      const record: MemoryRecord = {
        id: globalThis.crypto.randomUUID(),
        title: titleFromContent(draft.content, draft.title),
        content: draft.content,
        kind: draft.kind ?? "note",
        status: "active",
        source: "manual",
        source_conversation_id: null,
        created_at: timestamp,
        updated_at: timestamp,
        confidence: 1,
      };
      save(userId, { ...state, items: [record, ...state.items] });
      return record;
    },

    async update(id, draft) {
      const state = load(userId);
      const index = state.items.findIndex((entry) => entry.id === id);
      if (index < 0) throw notFound(id);
      const current = state.items[index];
      const next: MemoryRecord = {
        ...current,
        title: draft.title
          ? titleFromContent(draft.content ?? current.content, draft.title)
          : current.title,
        content: draft.content ?? current.content,
        kind: draft.kind ?? current.kind,
        updated_at: nowIso(),
      };
      const items = [...state.items];
      items[index] = next;
      save(userId, { ...state, items });
      return next;
    },

    async delete(id) {
      const state = load(userId);
      save(userId, {
        ...state,
        items: state.items.filter((entry) => entry.id !== id),
      });
    },

    async clearAll() {
      const state = load(userId);
      save(userId, { ...state, items: [] });
    },
  };
}
