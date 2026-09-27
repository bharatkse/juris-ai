/**
 * Browser-safe configuration. Never put BACKEND_API_URL or secrets here.
 */

export function isChatStreamingEnabled(
  value = process.env.NEXT_PUBLIC_CHAT_STREAMING,
): boolean {
  return value?.trim().toLowerCase() !== "false";
}
