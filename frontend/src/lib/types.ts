/** Mirrors backend/app/schemas (the OpenAPI spec at /docs is the source of truth). */

export type Role = "AUTHOR" | "ADMIN";
export type TicketStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
export type TicketPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type TicketCategory =
  | "ROYALTY_PAYMENTS"
  | "ISBN_METADATA"
  | "PRINTING_QUALITY"
  | "DISTRIBUTION_AVAILABILITY"
  | "BOOK_STATUS_PRODUCTION"
  | "GENERAL_INQUIRY";
export type MessageKind = "AUTHOR_MESSAGE" | "ADMIN_REPLY" | "INTERNAL_NOTE";
export type AiStatus = "PENDING" | "DONE" | "FALLBACK" | "SKIPPED";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  author_id: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Book {
  id: string;
  title: string;
  isbn: string | null;
  genre: string | null;
  publication_date: string | null;
  status: string;
  is_published: boolean;
  mrp: string | null;
  royalty_per_copy: string | null;
  copies_sold: number;
  royalty_earned: string;
  royalty_paid: string;
  royalty_pending: string;
  last_payout_date: string | null;
  print_partner: string | null;
  available_on: string[];
}

export interface BooksSummary {
  total_books: number;
  published_books: number;
  in_production_books: number;
  total_copies_sold: number;
  total_royalty_earned: string;
  total_royalty_paid: string;
  total_royalty_pending: string;
  payout_threshold: string;
  pending_below_threshold: boolean;
}

export interface BooksResponse {
  items: Book[];
  summary: BooksSummary;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
}

export interface BookRef {
  id: string;
  title: string;
  status: string;
}
export interface AuthorRef {
  id: string;
  name: string;
  email: string;
  city: string | null;
}
export interface UserRef {
  id: string;
  name: string;
}

export interface Attachment {
  id: string;
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
}

export interface Message {
  id: string;
  kind: MessageKind;
  body: string;
  sender_name: string | null;
  sender_role: Role | null;
  created_at: string;
}

export interface TicketListItem {
  id: string;
  number: number;
  subject: string;
  status: TicketStatus;
  category: TicketCategory;
  category_label: string;
  priority: TicketPriority;
  book: BookRef | null;
  author: AuthorRef | null;
  assigned_to: UserRef | null;
  message_count: number;
  created_at: string;
  last_activity_at: string;
}

export interface Ticket extends TicketListItem {
  description: string;
  messages: Message[];
  attachments: Attachment[];
  resolved_at: string | null;
}

export interface AiMeta {
  status: AiStatus;
  category: TicketCategory | null;
  priority: TicketPriority | null;
  confidence: number | null;
  reasoning: string | null;
  category_overridden: boolean;
  priority_overridden: boolean;
  draft_generated_at: string | null;
}

export interface AdminTicket extends Ticket {
  ai: AiMeta;
  ai_draft: string | null;
  book_detail: Book | null;
}

export interface DraftOut {
  draft: string;
  generated_at: string;
  cached: boolean;
  model: string | null;
}

export interface QueueStats {
  by_status: Record<TicketStatus, number>;
  open_by_priority: Record<TicketPriority, number>;
  unassigned_open: number;
  oldest_open_created_at: string | null;
}

export interface AiUsageRow {
  purpose: string;
  calls: number;
  ok: number;
  failed: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  estimated_cost_usd: string;
}

export interface AiUsage {
  model: string;
  since: string | null;
  rows: AiUsageRow[];
  total_cost_usd: string;
  pricing_note: string;
}

export interface TicketCreate {
  book_id: string | null;
  subject: string;
  description: string;
  attachments: { filename: string; mime_type: string | null; size_bytes: number | null }[];
}

export interface AdminTicketUpdate {
  status?: TicketStatus;
  category?: TicketCategory;
  priority?: TicketPriority;
  assigned_to_id?: string | null;
}

export interface QueueFilters {
  status?: TicketStatus[];
  category?: TicketCategory | "";
  priority?: TicketPriority | "";
  assigned?: "" | "me" | "unassigned";
  q?: string;
  created_from?: string;
  created_to?: string;
  sort?: "urgency" | "newest" | "oldest" | "activity";
  limit?: number;
  offset?: number;
}
