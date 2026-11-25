/**
 * Server-only env. Imported from Route Handlers / auth — not from client components.
 */
import { z } from "zod";

const DEFAULT_BACKEND_API_URL = "http://127.0.0.1:8001/api/v1";

const serverEnvSchema = z.object({
  BACKEND_API_URL: z
    .string()
    .trim()
    .url()
    .refine(
      (value) => value.startsWith("http://") || value.startsWith("https://"),
      "BACKEND_API_URL must use http or https",
    )
    .optional(),
});

export function getBackendApiUrl(): URL {
  const parsed = serverEnvSchema.parse({
    BACKEND_API_URL: process.env.BACKEND_API_URL || undefined,
  });
  const configured = parsed.BACKEND_API_URL || DEFAULT_BACKEND_API_URL;
  const normalized = configured.endsWith("/") ? configured : `${configured}/`;
  return new URL(normalized);
}

export function backendApiUrl(path: string): string {
  const base = getBackendApiUrl();
  return new URL(path.replace(/^\/+/u, ""), base).toString();
}
