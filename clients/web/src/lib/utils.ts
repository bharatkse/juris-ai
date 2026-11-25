import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const LEGAL_DISCLAIMER =
  "Juris AI provides legal information, not legal advice, and does not create an attorney–client relationship.";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function getSafeNextPath(
  candidate: string | null | undefined,
  fallback = "/app",
): string {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) {
    return fallback;
  }

  if (candidate.includes("\\") || /[\u0000-\u001F]/u.test(candidate)) {
    return fallback;
  }

  try {
    const parsed = new URL(candidate, "https://juris.local");
    if (
      parsed.origin !== "https://juris.local" ||
      (parsed.pathname !== "/app" && !parsed.pathname.startsWith("/app/"))
    ) {
      return fallback;
    }

    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

export function getInitials(
  firstName?: string | null,
  lastName?: string | null,
  email?: string | null,
): string {
  const initials = [firstName, lastName]
    .filter((part): part is string => Boolean(part?.trim()))
    .map((part) => part.trim().charAt(0).toUpperCase())
    .join("");

  if (initials) {
    return initials.slice(0, 2);
  }

  return email?.trim().charAt(0).toUpperCase() || "J";
}
