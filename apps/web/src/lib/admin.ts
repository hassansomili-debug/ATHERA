"use client";

import { useSyncExternalStore } from "react";

import { getAccessToken } from "./session";

/**
 * لوحة الإدارة — ما يحتاجه المتصفّح وحدَه (المرحلة ٩).
 *
 * ## الأدوارُ الإداريّة — نسخةٌ **محروسة** من المصدر
 *
 * المصدرُ القانونيّ `rbac.ADMIN_ROLE_KEYS` في الخادم، ومنه يُبنى حارسُ
 * `/api/v1/admin`. وهذه القائمةُ تقرّر **ظهورَ** رابطِ اللوحة لا الإذنَ به —
 * والإذنُ للخادم وحدَه. ويحرس تطابقَ القائمتين فحصٌ يقرأ `rbac.py` نفسَه
 * (`stage9-admin-nav`)، فدورٌ إداريٌّ جديدٌ في المصدر لا يُنسى هنا صامتًا.
 */
export const ADMIN_ROLE_KEYS: readonly string[] = [
  "college_admin",
  "institution_admin",
  "research_admin",
  "system_admin",
];

/**
 * أدوارُ الجلسة — **من ادّعاء `roles` في رمز الدخول**، وهو نفسُه ما يفحصه
 * `require_roles` في الخادم. فلا نسخةَ ثانية تُخزَّن في `localStorage`، ولا
 * طلبَ شبكةٍ مع كلّ صفحة. والتوقيعُ لا يُتحقَّق منه هنا: هذا عرضٌ لا إذن.
 */
export function rolesFromAccessToken(): string[] {
  const token = getAccessToken();
  if (!token) return [];
  const payload = token.split(".")[1];
  if (!payload) return [];
  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const claims = JSON.parse(atob(padded)) as { roles?: unknown };
    return Array.isArray(claims.roles) ? claims.roles.filter((r) => typeof r === "string") : [];
  } catch {
    return [];
  }
}

export function hasAdminRole(roles: readonly string[]): boolean {
  return roles.some((role) => ADMIN_ROLE_KEYS.includes(role));
}

/**
 * أيَظهر رابطُ اللوحة؟ — `false` على الخادم، ثمّ ما يقوله الرمزُ في المتصفّح.
 *
 * والتصييرُ الأوّلُ على الخادم لا يعرف الرمز؛ فالافتراضُ الإخفاءُ ثمّ الإظهار —
 * لا العكس، وإلّا لمع الرابطُ لحظةً لمن لا يحقّ له. و`useSyncExternalStore`
 * تقرأ اللقطةَ مع كلّ تصيير، فتتبع الجلسةَ إن تجدّدت أو انتهت بين صفحتين.
 */
function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

export function useAdminAccess(): boolean {
  return useSyncExternalStore(subscribe, () => hasAdminRole(rolesFromAccessToken()), () => false);
}

/** يملأ `{name}` في نصٍّ مترجَم. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    key in values ? String(values[key]) : `{${key}}`);
}

export function formatCount(locale: string, value: number): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-EG" : "en-US").format(value);
}

export function formatBytes(locale: string, bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const number = new Intl.NumberFormat(locale === "ar" ? "ar-EG" : "en-US",
    { maximumFractionDigits: unit === 0 ? 0 : 1 }).format(value);
  return `${number} ${units[unit]}`;
}

/**
 * تكلفةٌ **مسجَّلة** — بلا تقريبٍ يُذهب سنتاتٍ ذاتَ معنى.
 *
 * والقيمةُ نصٌّ عشريٌّ من الخادم (`Decimal`) فلا تمرّ بفاصلةٍ عائمةٍ قبل العرض
 * إلّا هنا، وبستّ خاناتٍ عشريّةٍ على الأكثر.
 */
export function formatUsd(locale: string, value: string | number): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-EG" : "en-US", {
    style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 6,
  }).format(Number(value));
}

export function formatWhen(locale: string, iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(locale === "ar" ? "ar-EG" : "en-US",
    { dateStyle: "medium", timeStyle: "short" });
}

export function shortId(id: string | null | undefined): string {
  return id ? `${id.slice(0, 8)}…` : "—";
}

// ═════════════════════════ أنواعُ الجواب (مرآةُ `schemas/admin.py`) ═════════════════════════

export interface ModelUsage {
  window_days: number;
  model_runs: number;
  succeeded: number;
  failed: number;
  ambiguous: number;
  other_status: number;
  input_tokens: number;
  output_tokens: number;
  recorded_cost_usd: string;
  runs_with_cost: number;
  runs_without_cost: number;
}

export interface AdminOverview {
  scope: { tenant_id: string; tenant_name: string; current_admin_roles: string[] };
  users: { member_count: number; active_identity_count: number; signed_in_7d: number;
    signed_in_30d: number };
  projects: { total: number; active: number; archived: number; trashed: number };
  files: { total: number; total_bytes: number; trashed: number; pending: number };
  theses: { total: number; by_processing_state: Record<string, number>; stalled: number };
  ai: ModelUsage;
  operations: { window_days: number; failed_agent_runs: number; blocked_agent_runs: number;
    failed_model_runs: number; ambiguous_model_runs: number; failed_tool_runs: number;
    denied_tool_runs: number; thesis_processing_failures: number };
  audit: { latest_seq: number | null; latest_at: string | null };
}

export interface AdminUserRow {
  user_id: string;
  display_name: string;
  email: string;
  preferred_locale: string;
  is_active: boolean;
  last_login_at: string | null;
  roles: string[];
  member_since: string;
  project_count: number;
  file_count: number;
  attributed_model_runs_30d: number;
}

export interface Page<T> { items: T[]; next_cursor: string | null }

export interface AdminUserDetail {
  user: AdminUserRow;
  first_membership_at: string;
  latest_membership_at: string;
  projects: Array<{ project_id: string; title: string; lifecycle: string; created_at: string }>;
  projects_truncated: boolean;
  file_bytes: number;
  thesis_count: number;
  ai_30d: ModelUsage;
  latest_model_activity_at: string | null;
  agent_runs_30d: number;
}

export interface AdminProjectRow {
  project_id: string;
  title: string;
  status: string;
  lifecycle: string;
  current_gate: string | null;
  owner_user_id: string | null;
  owner_name: string | null;
  created_at: string;
  updated_at: string;
  collaborators: number;
  files: number;
  manuscripts: number;
}

export interface UsageBucket {
  key: string;
  model_runs: number;
  failed: number;
  input_tokens: number;
  output_tokens: number;
  recorded_cost_usd: string;
  runs_with_cost: number;
}

export interface AdminUsage {
  window_days: number;
  summary: ModelUsage;
  agent_runs: number;
  tool_runs: number;
  latency: { runs_with_latency: number; average_ms: number | null; median_ms: number | null };
  by_day: UsageBucket[];
  by_provider: UsageBucket[];
  by_model: UsageBucket[];
  by_status: UsageBucket[];
  by_operation: UsageBucket[];
}

export interface AdminOperations {
  view: string;
  limit: number;
  agent_runs: Array<{ run_id: string; trace_id: string | null; agent_key: string; status: string;
    gate: string | null; started_at: string | null; finished_at: string | null;
    requested_by: string | null; requested_by_name: string | null; error_present: boolean }>;
  model_runs: Array<{ run_id: string; agent_run_id: string | null; provider: string;
    model: string; operation: string | null; status: string; latency_ms: number | null;
    created_at: string; error_present: boolean }>;
  tool_runs: Array<{ run_id: string; agent_run_id: string | null; tool_key: string;
    tool_kind: string | null; status: string; duration_ms: number | null; created_at: string;
    error_present: boolean }>;
  theses: Array<{ thesis_id: string; processing_state: string; failure_code: string | null;
    processing_state_changed_at: string | null; processing_attempts: number;
    stalled: boolean }>;
}
