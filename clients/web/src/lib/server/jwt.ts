export function userIdFromAccessToken(token: string): string | null {
  const segments = token.split(".");
  if (segments.length < 2 || !segments[1]) {
    return null;
  }

  try {
    const json = Buffer.from(segments[1], "base64url").toString("utf8");
    const payload = JSON.parse(json) as { sub?: unknown };
    return typeof payload.sub === "string" && payload.sub.length > 0
      ? payload.sub
      : null;
  } catch {
    return null;
  }
}
