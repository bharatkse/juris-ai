export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  gender: "male" | "female" | "other" | null;
  phone_number: string | null;
  date_of_birth: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthResult {
  authenticated: boolean;
  user?: User;
}

export interface Pagination {
  offset: number;
  limit: number;
  total: number;
  has_more: boolean;
}

export interface Paginated<T> {
  items: T[];
  pagination: Pagination;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type ConversationRole = "user" | "assistant" | "system" | "tool";

export type ApprovalStatus =
  | "waiting"
  | "approved"
  | "rejected"
  | "edited"
  | "expired";

export interface ApprovalMetadata {
  approval_id: string;
  status: ApprovalStatus;
  expires_at?: string;
  agent_action_id?: string;
  requested_by?: string;
  created_at?: string;
}

export type ApprovalDecision = "approve" | "reject";

export interface ApprovalResponse {
  approval_id: string;
  agent_action_id: string;
  requested_by: string;
  status: ApprovalStatus;
  created_at: string;
  expires_at: string;
}

export interface ApprovalDecisionResponse {
  approval: ApprovalResponse;
  resumed_event?: ConversationEvent | null;
}

export interface Citation {
  title: string;
  source: string;
  reference?: string | null;
  page?: number | null;
  snippet?: string | null;
}

export interface Source {
  title: string;
  uri?: string | null;
  type?: string | null;
}

export interface Usage {
  provider?: string | null;
  model?: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms?: number | null;
}

export interface ResponseMetadata {
  agents: string[];
  workflow?: string | null;
  approval?: ApprovalMetadata | null;
  [key: string]: unknown;
}

export interface ConversationEventMetadata {
  agents?: string[];
  workflow?: string | null;
  approval?: ApprovalMetadata | null;
  citations?: Citation[];
  sources?: Source[];
  usage?: Usage;
  attachments?: Array<{ name: string; size?: number; type?: string }>;
  [key: string]: unknown;
}

export interface ConversationEvent {
  id: string;
  conversation_id: string;
  parent_event_id: string | null;
  role: ConversationRole;
  content: string;
  metadata: ConversationEventMetadata;
  event_metadata?: ConversationEventMetadata;
  created_at: string;
}

export interface AIResponse {
  content: string;
  citations: Citation[];
  sources: Source[];
  usage: Usage;
  metadata: ResponseMetadata;
}

export interface ChatResponse {
  conversation_id: string;
  response: AIResponse;
  user_event: ConversationEvent;
  assistant_event: ConversationEvent;
}

export interface ChatStreamLifecycleMetadata {
  status: string;
  phase?: string;
  [key: string]: unknown;
}

export interface ChatStreamMessage {
  content: string;
  is_final: false;
  metadata: ChatStreamLifecycleMetadata;
}

export interface ChatStreamCompleteMetadata {
  status: "complete";
  citations: Citation[];
  sources: Source[];
  usage: Usage;
  response_metadata: ResponseMetadata;
  approval?: ApprovalMetadata | null;
  conversation_id: string;
  user_event_id: string;
  assistant_event_id: string;
  [key: string]: unknown;
}

export interface ChatStreamComplete {
  content: string;
  is_final: true;
  metadata: ChatStreamCompleteMetadata;
}

export interface AssistantAnswerDetails {
  citations: Citation[];
  sources: Source[];
  usage?: Usage;
}

export type ConversationAnswerCache = Record<string, AssistantAnswerDetails>;
export type ConversationApprovalCache = Record<string, ApprovalMetadata>;

export interface UpdateProfileInput {
  first_name: string | null;
  last_name: string | null;
  phone_number: string | null;
  date_of_birth: string | null;
  gender: User["gender"];
}
