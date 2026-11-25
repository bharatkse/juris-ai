/**
 * Client feature flags. Only enable UI the backend actually serves.
 * Server remains the authority; these only hide or disable controls.
 */

function flag(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const features = {
  /** FastAPI has UpdateConversationRequest but no PATCH conversation route. */
  conversationRename: flag(process.env.NEXT_PUBLIC_FEATURE_CONVERSATION_RENAME),
  /** No usage/quota read API. */
  usageDashboard: false,
  /** No document library or ingestion-status API; uploads ride on POST /chat. */
  documentLibrary: false,
} as const;

export type ClientFeature = keyof typeof features;
