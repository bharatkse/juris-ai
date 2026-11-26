import { featureBackends } from "@/config/feature-backends";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

export interface ApiKeyMeta {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
}

export interface CreatedApiKey extends ApiKeyMeta {
  secret: string;
}

export interface ApiKeyRepository {
  readonly persistence: "http" | "local";
  list(): Promise<ApiKeyMeta[]>;
  create(name: string): Promise<CreatedApiKey>;
  revoke(id: string): Promise<void>;
}

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function createLocal(userId: string): ApiKeyRepository {
  const key = userStoreKey(userId, "api-keys");
  return {
    persistence: "local",
    async list() {
      return readVersioned(requireStorage(), key, [] as ApiKeyMeta[], {
        version: 1,
      });
    },
    async create(name) {
      const items = await this.list();
      const id = globalThis.crypto.randomUUID();
      const secret = `juris_local_${id.replace(/-/gu, "").slice(0, 24)}`;
      const meta: ApiKeyMeta = {
        id,
        name: name.trim() || "Untitled key",
        prefix: `${secret.slice(0, 14)}…`,
        created_at: new Date().toISOString(),
      };
      writeVersioned(requireStorage(), key, [meta, ...items], 1);
      return { ...meta, secret };
    },
    async revoke(id) {
      const items = await this.list();
      writeVersioned(
        requireStorage(),
        key,
        items.filter((item) => item.id !== id),
        1,
      );
    },
  };
}

const http: ApiKeyRepository = {
  persistence: "http",
  list() {
    return apiFetch<ApiKeyMeta[]>("/api/backend/api-keys");
  },
  create(name) {
    return apiFetch<CreatedApiKey>(
      "/api/backend/api-keys",
      jsonRequest({ name }, { method: "POST" }),
    );
  },
  revoke(id) {
    return apiFetch<void>(`/api/backend/api-keys/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },
};

export function getApiKeyRepository(userId?: string): ApiKeyRepository {
  if (featureBackends.apiKeys === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for API keys.");
    }
    return createLocal(userId);
  }
  return http;
}
