import { togglePin, type PinItem } from "@/features/pins/order";
import type { PinRepository } from "@/features/pins/repository";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

const FEATURE = "pins";
const VERSION = 1;

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function load(userId: string): PinItem[] {
  return readVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    [] as PinItem[],
    { version: VERSION },
  );
}

function save(userId: string, items: PinItem[]): void {
  writeVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    items,
    VERSION,
  );
}

export function createLocalPinRepository(userId: string): PinRepository {
  return {
    persistence: "local",
    async list() {
      return load(userId);
    },
    async replace(items) {
      save(userId, items);
      return items;
    },
    async toggle(target) {
      const next = togglePin(load(userId), target);
      save(userId, next);
      return next;
    },
  };
}
