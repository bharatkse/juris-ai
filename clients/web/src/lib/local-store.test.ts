import { afterEach, describe, expect, it } from "vitest";

import {
  clearUserStores,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

class MemoryStorage implements Storage {
  private map = new Map<string, string>();

  get length(): number {
    return this.map.size;
  }

  clear(): void {
    this.map.clear();
  }

  getItem(key: string): string | null {
    return this.map.get(key) ?? null;
  }

  key(index: number): string | null {
    return [...this.map.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.map.delete(key);
  }

  setItem(key: string, value: string): void {
    this.map.set(key, value);
  }
}

describe("local-store versioning", () => {
  const storage = new MemoryStorage();

  afterEach(() => storage.clear());

  it("round-trips current version data", () => {
    const key = userStoreKey("user_1", "pins");
    writeVersioned(storage, key, [{ type: "conversation", id: "c1" }], 1);
    expect(readVersioned(storage, key, [])).toEqual([
      { type: "conversation", id: "c1" },
    ]);
  });

  it("migrates older envelopes", () => {
    const key = userStoreKey("user_1", "pins");
    storage.setItem(key, JSON.stringify({ version: 0, data: ["c1"] }));
    const migrated = readVersioned(storage, key, [] as Array<{ id: string }>, {
      version: 1,
      migrate: (raw) =>
        (raw as string[]).map((id) => ({ type: "conversation" as const, id })),
    });
    expect(migrated).toEqual([{ type: "conversation", id: "c1" }]);
  });

  it("clears only one user's keys", () => {
    writeVersioned(storage, userStoreKey("a", "pins"), [1], 1);
    writeVersioned(storage, userStoreKey("b", "pins"), [2], 1);
    clearUserStores(storage, "a");
    expect(readVersioned(storage, userStoreKey("a", "pins"), "missing")).toBe(
      "missing",
    );
    expect(readVersioned(storage, userStoreKey("b", "pins"), 0)).toEqual([2]);
  });
});
