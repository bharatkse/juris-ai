import type {
  DocumentRepository,
  LibraryDocument,
} from "@/features/documents/types";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

const FEATURE = "documents";
const VERSION = 1;

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function load(userId: string): LibraryDocument[] {
  return readVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    [] as LibraryDocument[],
    { version: VERSION },
  );
}

function save(userId: string, items: LibraryDocument[]): void {
  writeVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    items,
    VERSION,
  );
}

export function createLocalDocumentRepository(
  userId: string,
): DocumentRepository {
  return {
    persistence: "local",
    async list() {
      return load(userId);
    },
    async add(meta) {
      const doc: LibraryDocument = {
        id: globalThis.crypto.randomUUID(),
        name: meta.name,
        mime: meta.mime,
        size: meta.size,
        created_at: new Date().toISOString(),
      };
      save(userId, [doc, ...load(userId)]);
      return doc;
    },
    async remove(id) {
      save(
        userId,
        load(userId).filter((item) => item.id !== id),
      );
    },
  };
}
