import type { PinItem } from "@/features/pins/order";
import type { PinRepository } from "@/features/pins/repository";
import { apiFetch, jsonRequest } from "@/lib/api/client";

const ENDPOINT = "/api/backend/pins";

export const httpPinRepository: PinRepository = {
  persistence: "http",
  list() {
    return apiFetch<PinItem[]>(ENDPOINT);
  },
  replace(items) {
    return apiFetch<PinItem[]>(ENDPOINT, jsonRequest({ items }, { method: "PUT" }));
  },
  toggle(target) {
    return apiFetch<PinItem[]>(
      `${ENDPOINT}/toggle`,
      jsonRequest(target, { method: "POST" }),
    );
  },
};
