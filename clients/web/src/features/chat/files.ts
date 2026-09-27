export const MAX_CHAT_FILES = 5;
export const MAX_CHAT_FILE_BYTES = 20 * 1024 * 1024;
export const MAX_CHAT_MESSAGE_LENGTH = 10_000;
export const ALLOWED_CHAT_EXTENSIONS = [
  "pdf",
  "docx",
  "txt",
  "md",
  "html",
] as const;

export const CHAT_FILE_ACCEPT = ALLOWED_CHAT_EXTENSIONS.map(
  (extension) => `.${extension}`,
).join(",");

export interface FileSelectionResult {
  files: File[];
  errors: string[];
}

export function fileExtension(filename: string): string {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index + 1).toLowerCase() : "";
}

export function addValidatedFiles(
  current: readonly File[],
  incoming: readonly File[],
): FileSelectionResult {
  const files = [...current];
  const errors: string[] = [];
  const fingerprints = new Set(
    current.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
  );

  for (const file of incoming) {
    const extension = fileExtension(file.name);
    const fingerprint = `${file.name}:${file.size}:${file.lastModified}`;

    if (
      !ALLOWED_CHAT_EXTENSIONS.includes(
        extension as (typeof ALLOWED_CHAT_EXTENSIONS)[number],
      )
    ) {
      errors.push(
        `${file.name}: unsupported type. Use PDF, DOCX, TXT, MD, or HTML.`,
      );
      continue;
    }

    if (file.size > MAX_CHAT_FILE_BYTES) {
      errors.push(`${file.name}: file must be 20 MB or smaller.`);
      continue;
    }

    if (fingerprints.has(fingerprint)) {
      errors.push(`${file.name}: this file is already attached.`);
      continue;
    }

    if (files.length >= MAX_CHAT_FILES) {
      errors.push(`You can attach up to ${MAX_CHAT_FILES} files.`);
      break;
    }

    files.push(file);
    fingerprints.add(fingerprint);
  }

  return { files, errors };
}

export function validateChatMessage(message: string): string | null {
  const length = message.trim().length;
  if (length === 0) {
    return "Enter a message before sending.";
  }
  if (length > MAX_CHAT_MESSAGE_LENGTH) {
    return `Messages must be ${MAX_CHAT_MESSAGE_LENGTH.toLocaleString()} characters or fewer.`;
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.ceil(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
