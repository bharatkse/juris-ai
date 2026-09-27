export type ApiFieldErrors = Record<string, string[]>;

export interface NormalizedApiError {
  code: string;
  message: string;
  httpStatus: number;
  requestId?: string;
  fields?: ApiFieldErrors;
  retryAfterSeconds?: number;
}

const STATUS_MESSAGES: Record<number, string> = {
  400: "The request could not be completed.",
  401: "Please sign in to continue.",
  403: "You do not have permission to do that.",
  404: "The requested resource was not found.",
  409: "That resource already exists.",
  422: "Please review the highlighted fields.",
  429: "Too many requests. Wait and try again.",
  500: "Something went wrong. Please try again.",
  502: "The legal service is temporarily unavailable.",
  503: "The legal service is temporarily unavailable.",
  504: "The request took too long. Please try again.",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function parseValidationFields(detail: unknown): ApiFieldErrors | undefined {
  if (!Array.isArray(detail)) {
    return undefined;
  }

  const fields: ApiFieldErrors = {};

  for (const issue of detail) {
    if (!isRecord(issue) || !Array.isArray(issue.loc)) {
      continue;
    }

    const path = issue.loc
      .filter((segment) => segment !== "body" && segment !== "query")
      .map(String)
      .join(".");
    const message = text(issue.msg);

    if (path && message) {
      fields[path] = [...(fields[path] ?? []), message];
    }
  }

  return Object.keys(fields).length ? fields : undefined;
}

function parseFieldMap(value: unknown): ApiFieldErrors | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const fields: ApiFieldErrors = {};
  for (const [field, errors] of Object.entries(value)) {
    if (typeof errors === "string") {
      fields[field] = [errors];
    } else if (Array.isArray(errors)) {
      const messages = errors.filter(
        (error): error is string => typeof error === "string",
      );
      if (messages.length) {
        fields[field] = messages;
      }
    }
  }

  return Object.keys(fields).length ? fields : undefined;
}

function statusCode(httpStatus: number): string {
  const names: Record<number, string> = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "RESOURCE_NOT_FOUND",
    409: "RESOURCE_CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
  };

  return names[httpStatus] ?? "INTERNAL_SERVER_ERROR";
}

export function parseRetryAfter(
  value?: string | null,
  now = Date.now(),
): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.ceil(seconds);
  }

  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return undefined;
  return Math.max(0, Math.ceil((timestamp - now) / 1000));
}

export function normalizeApiError(
  payload: unknown,
  httpStatus: number,
  headerRequestId?: string | null,
  retryAfter?: string | null,
): NormalizedApiError {
  const root = isRecord(payload) ? payload : {};
  const error = isRecord(root.error) ? root.error : {};
  const metadata = isRecord(root.metadata) ? root.metadata : {};
  const details = isRecord(error.details) ? error.details : {};
  const detailMessage = text(root.detail);

  const fields =
    parseValidationFields(root.detail) ??
    parseFieldMap(details.fields) ??
    parseFieldMap(root.fields);
  const retryAfterSeconds = parseRetryAfter(retryAfter);

  return {
    code: text(error.code) ?? text(root.code) ?? statusCode(httpStatus),
    message:
      text(error.message) ??
      detailMessage ??
      text(root.message) ??
      STATUS_MESSAGES[httpStatus] ??
      "Something went wrong. Please try again.",
    httpStatus,
    requestId:
      text(metadata.request_id) ??
      text(root.request_id) ??
      headerRequestId ??
      undefined,
    ...(fields ? { fields } : {}),
    ...(retryAfterSeconds !== undefined ? { retryAfterSeconds } : {}),
  };
}

export class ApiError extends Error implements NormalizedApiError {
  readonly code: string;
  readonly httpStatus: number;
  readonly requestId?: string;
  readonly fields?: ApiFieldErrors;
  readonly retryAfterSeconds?: number;

  constructor(error: NormalizedApiError) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.httpStatus = error.httpStatus;
    this.requestId = error.requestId;
    this.fields = error.fields;
    this.retryAfterSeconds = error.retryAfterSeconds;
  }
}
