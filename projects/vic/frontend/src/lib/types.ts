export type Provider = "gemini" | "chatgpt" | "claude" | "unknown";

export interface SessionEntry {
  session: number;
  date: string;
  provider: Provider;
  provider_label: string;
  title: string;
  summary: string;
  decisions: string[];
  bugs: string[];
  fixes: string[];
  architecture: string[];
  open_questions: string[];
  message_count: number;
}

export interface ProcessResult {
  providers: Provider[];
  session_count: number;
  message_count: number;
  date_range: [string, string];
  themes: [string, number][];
  projects: Record<string, { date: string; provider: string; title: string; summary: string }[]>;
  sessions: SessionEntry[];
  jsonl: string;
  exec_summary: string;
}

export interface ApiError {
  error: string;
}
