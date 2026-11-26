import { afterEach, describe, expect, it } from "vitest";

import { createLocalMemoryRepository } from "@/features/memory/adapters/local";

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

describe("local memory repository", () => {
  const storage = new MemoryStorage();

  afterEach(() => {
    storage.clear();
  });

  it("persists, versions, and namespaces per user", async () => {
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: storage,
    });
    const alice = createLocalMemoryRepository("alice");
    const bob = createLocalMemoryRepository("bob");
    await alice.create({ title: "Prefers SC citations", content: "Use SCR." });
    await bob.create({ title: "Bob fact", content: "Other." });
    const aliceItems = await alice.list();
    const bobItems = await bob.list();
    expect(aliceItems).toHaveLength(1);
    expect(bobItems).toHaveLength(1);
    expect(aliceItems[0]?.title).toBe("Prefers SC citations");
    await alice.update(aliceItems[0]!.id, { content: "Updated." });
    expect((await alice.get(aliceItems[0]!.id)).content).toBe("Updated.");
    await alice.delete(aliceItems[0]!.id);
    expect(await alice.list()).toHaveLength(0);
    expect(await bob.list()).toHaveLength(1);
  });
});
