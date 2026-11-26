import { featureBackends } from "@/config/feature-backends";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

export type TitleMap = Record<string, string>;

export interface TitleRepository {
  readonly persistence: "http" | "local";
  list(): Promise<TitleMap>;
  set(conversationId: string, title: string): Promise<TitleMap>;
}

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function createLocalTitleRepository(userId: string): TitleRepository {
  const key = userStoreKey(userId, "titles");
  return {
    persistence: "local",
    async list() {
      return readVersioned(requireStorage(), key, {} as TitleMap, {
        version: 1,
      });
    },
    async set(conversationId, title) {
      const current = await this.list();
      const next = { ...current, [conversationId]: title };
      writeVersioned(requireStorage(), key, next, 1);
      return next;
    },
  };
}

const httpTitleRepository: TitleRepository = {
  persistence: "http",
  list() {
    return apiFetch<TitleMap>("/api/backend/conversation-titles");
  },
  set(conversationId, title) {
    return apiFetch<TitleMap>(
      `/api/backend/conversations/${encodeURIComponent(conversationId)}`,
      jsonRequest({ title }, { method: "PATCH" }),
    );
  },
};

export function getTitleRepository(userId?: string): TitleRepository {
  if (featureBackends.titles === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for conversation titles.");
    }
    return createLocalTitleRepository(userId);
  }
  return httpTitleRepository;
}
