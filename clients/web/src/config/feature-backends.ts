/**
 * Adapter selection for features that may run against FastAPI or a
 * device-local store. Components never branch on mock data.
 */

export type FeatureBackend = "http" | "local";

function backend(
  value: string | undefined,
  fallback: FeatureBackend,
): FeatureBackend {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "http" || normalized === "local") {
    return normalized;
  }
  return fallback;
}

function flag(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const featureBackends = {
  memory: backend(process.env.NEXT_PUBLIC_FEATURE_MEMORY_BACKEND, "http"),
  projects: backend(process.env.NEXT_PUBLIC_FEATURE_PROJECTS_BACKEND, "local"),
  pins: backend(process.env.NEXT_PUBLIC_FEATURE_PINS_BACKEND, "local"),
  documents: backend(
    process.env.NEXT_PUBLIC_FEATURE_DOCUMENTS_BACKEND,
    "local",
  ),
  preferences: backend(
    process.env.NEXT_PUBLIC_FEATURE_PREFERENCES_BACKEND,
    "local",
  ),
  notifications: backend(
    process.env.NEXT_PUBLIC_FEATURE_NOTIFICATIONS_BACKEND,
    "local",
  ),
  integrations: backend(
    process.env.NEXT_PUBLIC_FEATURE_INTEGRATIONS_BACKEND,
    "local",
  ),
  apiKeys: backend(process.env.NEXT_PUBLIC_FEATURE_API_KEYS_BACKEND, "local"),
  titles: backend(
    process.env.NEXT_PUBLIC_FEATURE_CONVERSATION_TITLES_BACKEND,
    "local",
  ),
} as const;

export const roleFlags = {
  admin: flag(process.env.NEXT_PUBLIC_FEATURE_ADMIN),
  permissions: flag(process.env.NEXT_PUBLIC_FEATURE_PERMISSIONS),
} as const;

export type FeatureBackendName = keyof typeof featureBackends;

export function localBackedFeatures(): FeatureBackendName[] {
  return (Object.keys(featureBackends) as FeatureBackendName[]).filter(
    (name) => featureBackends[name] === "local",
  );
}
