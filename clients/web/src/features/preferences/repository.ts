import { featureBackends } from "@/config/feature-backends";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

export interface UserPreferences {
  timezone: string;
  language: string;
  avatarDataUrl: string | null;
  notifications: {
    product: boolean;
    approvals: boolean;
  };
}

export const defaultPreferences = (): UserPreferences => ({
  timezone: "Asia/Kolkata",
  language: "en",
  avatarDataUrl: null,
  notifications: { product: true, approvals: true },
});

export interface PreferencesRepository {
  readonly persistence: "http" | "local";
  get(): Promise<UserPreferences>;
  save(next: UserPreferences): Promise<UserPreferences>;
}

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function createLocalPreferencesRepository(
  userId: string,
): PreferencesRepository {
  const key = userStoreKey(userId, "preferences");
  return {
    persistence: "local",
    async get() {
      return readVersioned(requireStorage(), key, defaultPreferences(), {
        version: 1,
      });
    },
    async save(next) {
      writeVersioned(requireStorage(), key, next, 1);
      return next;
    },
  };
}

const httpPreferencesRepository: PreferencesRepository = {
  persistence: "http",
  get() {
    return apiFetch<UserPreferences>("/api/backend/preferences");
  },
  save(next) {
    return apiFetch<UserPreferences>(
      "/api/backend/preferences",
      jsonRequest(next, { method: "PUT" }),
    );
  },
};

export function getPreferencesRepository(
  userId?: string,
): PreferencesRepository {
  if (featureBackends.preferences === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for preferences.");
    }
    return createLocalPreferencesRepository(userId);
  }
  return httpPreferencesRepository;
}
