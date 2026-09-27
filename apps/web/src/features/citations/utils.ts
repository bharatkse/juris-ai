import type { Citation, Source } from "@/lib/api/types";

export function safeExternalUri(uri?: string | null): string | null {
  if (!uri) return null;
  try {
    const parsed = new URL(uri);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.toString()
      : null;
  } catch {
    return null;
  }
}

export function sourceForCitation(
  citation: Citation,
  sources: readonly Source[],
): Source | undefined {
  const citationTitle = citation.title.trim().toLocaleLowerCase();
  const citationSource = citation.source.trim().toLocaleLowerCase();
  return sources.find((source) => {
    const title = source.title.trim().toLocaleLowerCase();
    return title === citationTitle || title === citationSource;
  });
}

export function citationIdentity(citation: Citation, index: number): string {
  return [
    citation.title,
    citation.source,
    citation.reference ?? "",
    citation.page ?? "",
    index,
  ].join(":");
}
