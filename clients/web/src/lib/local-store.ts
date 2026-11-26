const PREFIX = "juris";

export const LOCAL_STORE_CURRENT_VERSION = 1;

export interface VersionedEnvelope<T> {
  version: number;
  data: T;
}

export function userStoreKey(userId: string, feature: string): string {
  return `${PREFIX}:${userId}:${feature}`;
}

export function isUserStoreKey(userId: string, key: string): boolean {
  return key.startsWith(`${PREFIX}:${userId}:`);
}

export type MigrateFn<T> = (raw: unknown, version: number) => T;

function parseEnvelope(raw: string): VersionedEnvelope<unknown> | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !("version" in parsed) ||
      !("data" in parsed) ||
      typeof (parsed as VersionedEnvelope<unknown>).version !== "number"
    ) {
      return null;
    }
    return parsed as VersionedEnvelope<unknown>;
  } catch {
    return null;
  }
}

export function readVersioned<T>(
  storage: Storage,
  key: string,
  fallback: T,
  options?: {
    version?: number;
    migrate?: MigrateFn<T>;
  },
): T {
  const currentVersion = options?.version ?? LOCAL_STORE_CURRENT_VERSION;
  try {
    const raw = storage.getItem(key);
    if (!raw) return fallback;
    const envelope = parseEnvelope(raw);
    if (!envelope) return fallback;
    if (envelope.version === currentVersion) {
      return envelope.data as T;
    }
    if (options?.migrate) {
      const migrated = options.migrate(envelope.data, envelope.version);
      writeVersioned(storage, key, migrated, currentVersion);
      return migrated;
    }
    return fallback;
  } catch {
    return fallback;
  }
}

export function writeVersioned<T>(
  storage: Storage,
  key: string,
  data: T,
  version = LOCAL_STORE_CURRENT_VERSION,
): void {
  try {
    const envelope: VersionedEnvelope<T> = { version, data };
    storage.setItem(key, JSON.stringify(envelope));
  } catch {
    // Quota or private-mode failures must not break the UI.
  }
}

export function clearUserStores(storage: Storage, userId: string): void {
  const doomed: string[] = [];
  try {
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key && isUserStoreKey(userId, key)) {
        doomed.push(key);
      }
    }
    for (const key of doomed) {
      storage.removeItem(key);
    }
  } catch {
    /* ignore */
  }
}

export function browserStorage(): Storage | null {
  try {
    if (typeof globalThis.localStorage === "undefined") return null;
    return globalThis.localStorage;
  } catch {
    return null;
  }
}
