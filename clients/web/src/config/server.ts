/**
 * Server-only env. Imported from Route Handlers / auth — not from client components.
 */

const DEFAULT_BACKEND_API_URL = "http://127.0.0.1:8001/api/v1";

export function getBackendApiUrl(): URL {
  const configured =
    process.env.BACKEND_API_URL?.trim() || DEFAULT_BACKEND_API_URL;
  const normalized = configured.endsWith("/") ? configured : `${configured}/`;
  const base = new URL(normalized);

  if (base.protocol !== "http:" && base.protocol !== "https:") {
    throw new Error("BACKEND_API_URL must use http or https");
  }

  return base;
}

export function backendApiUrl(path: string): string {
  const base = getBackendApiUrl();
  return new URL(path.replace(/^\/+/u, ""), base).toString();
}
