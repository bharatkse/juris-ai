/**
 * Browser-safe configuration. Never put BACKEND_API_URL or secrets here.
 */
import { z } from "zod";

const clientEnvSchema = z.object({
  NEXT_PUBLIC_CHAT_STREAMING: z.string().optional(),
  NEXT_PUBLIC_DEFAULT_THEME: z.enum(["light", "dark"]).optional(),
  NEXT_PUBLIC_FEATURE_CONVERSATION_RENAME: z.string().optional(),
});

export type ClientEnv = z.infer<typeof clientEnvSchema>;

export function parseClientEnv(
  source: Record<string, string | undefined> = {
    NEXT_PUBLIC_CHAT_STREAMING: process.env.NEXT_PUBLIC_CHAT_STREAMING,
    NEXT_PUBLIC_DEFAULT_THEME: process.env.NEXT_PUBLIC_DEFAULT_THEME,
    NEXT_PUBLIC_FEATURE_CONVERSATION_RENAME:
      process.env.NEXT_PUBLIC_FEATURE_CONVERSATION_RENAME,
  },
): ClientEnv {
  return clientEnvSchema.parse(source);
}

export function isChatStreamingEnabled(
  value = process.env.NEXT_PUBLIC_CHAT_STREAMING,
): boolean {
  return value?.trim().toLowerCase() !== "false";
}
