import { featureBackends } from "@/config/feature-backends";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

export interface Connector {
  id: string;
  name: string;
  kind: "mcp" | "other";
  enabled: boolean;
}

export interface IntegrationRepository {
  readonly persistence: "http" | "local";
  list(): Promise<Connector[]>;
  setEnabled(id: string, enabled: boolean): Promise<Connector[]>;
}

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function createLocal(userId: string): IntegrationRepository {
  const key = userStoreKey(userId, "integrations");
  return {
    persistence: "local",
    async list() {
      return readVersioned(requireStorage(), key, [] as Connector[], {
        version: 1,
      });
    },
    async setEnabled(id, enabled) {
      const items = await this.list();
      const next = items.map((item) =>
        item.id === id ? { ...item, enabled } : item,
      );
      writeVersioned(requireStorage(), key, next, 1);
      return next;
    },
  };
}

const http: IntegrationRepository = {
  persistence: "http",
  list() {
    return apiFetch<Connector[]>("/api/backend/integrations");
  },
  setEnabled(id, enabled) {
    return apiFetch<Connector[]>(
      `/api/backend/integrations/${encodeURIComponent(id)}`,
      jsonRequest({ enabled }, { method: "PATCH" }),
    );
  },
};

export function getIntegrationRepository(
  userId?: string,
): IntegrationRepository {
  if (featureBackends.integrations === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for integrations.");
    }
    return createLocal(userId);
  }
  return http;
}
