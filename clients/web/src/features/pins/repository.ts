import { featureBackends } from "@/config/feature-backends";
import { httpPinRepository } from "@/features/pins/adapters/http";
import { createLocalPinRepository } from "@/features/pins/adapters/local";
import type { PinItem } from "@/features/pins/order";

export interface PinRepository {
  readonly persistence: "http" | "local";
  list(): Promise<PinItem[]>;
  replace(items: PinItem[]): Promise<PinItem[]>;
  toggle(target: PinItem): Promise<PinItem[]>;
}

export function getPinRepository(userId?: string): PinRepository {
  if (featureBackends.pins === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for pinned items.");
    }
    return createLocalPinRepository(userId);
  }
  return httpPinRepository;
}
