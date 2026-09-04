/**
 * مساحة عمل البحث | Project workspace client (PUBRIVA).
 *
 * **البحث هو الشيء المركزي.** فهذه الدوال تقرأ البحث بعلاقاته — ملفاته
 * ومراجعه وما تعرفه المنصّة عنه — لا وحداتٍ متجاورة يربط بينها الباحث في
 * رأسه.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

export interface ProjectSummary {
  id: string;
  title_ar: string;
  status: string;
  created_at: string;
  archived_at: string | null;
  deleted_at: string | null;
  files: number;
  sources: number;
  verified_facts: number;
  manuscripts: number;
}

export interface BrainEntry {
  key: string;
  label: string;
  state: "known" | "needs_review" | "missing" | "conflicting";
  value: string | null;
  sources: number;
}

export interface ProjectOverview {
  project: ProjectSummary;
  brain: BrainEntry[];
  recommended_next: { key: string; label: string } | null;
  blockers: string[];
  note: string;
}

export interface ProjectFile {
  file_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  added_at: string;
  state: string;
  processing_status: string;
  thesis_id: string | null;
  candidates: number;
  reviewed: number;
}

export interface ProjectSource {
  source_id: string;
  title: string;
  doi: string | null;
  publication_year: number | null;
  use_state: "included" | "saved_only" | "excluded";
  added_at: string;
  decided_at: string | null;
  /**
   * سببُ الاستبعاد يرافق حاله دائمًا.
   *
   * وحالٌ بلا سببها تُعرض حكمًا بلا تعليل: يقرأ الباحث «مستبعَدة» ولا يعرف
   * لماذا، فيعيد قراءة الدراسة — أو يخترع لها سببًا من ذاكرته.
   */
  exclusion_reason_code: string | null;
  reason_ar: string | null;
}

export interface Impact {
  is_safe: boolean;
  breaks_approved_work: boolean;
  summary: string;
  consequences: Array<{
    kind: string;
    count: number;
    label: string;
    breaks_approved_work: boolean;
  }>;
}

const base = "/api/v1/workspace";

export const listProjects = (locale: Locale, trash = false) =>
  apiFetch<ProjectSummary[]>(`${base}/projects?trash=${trash}`, { locale });

export const createProject = (locale: Locale, title: string) =>
  apiFetch<ProjectSummary>(`${base}/projects`, {
    locale,
    method: "POST",
    body: JSON.stringify({ title_ar: title }),
  });

export const archiveProject = (locale: Locale, id: string) =>
  apiFetch<ProjectSummary>(`${base}/projects/${id}/archive`, { locale, method: "POST" });

export const trashProject = (locale: Locale, id: string) =>
  apiFetch<Impact>(`${base}/projects/${id}`, { locale, method: "DELETE" });

export const restoreProject = (locale: Locale, id: string) =>
  apiFetch<ProjectSummary>(`${base}/projects/${id}/restore`, { locale, method: "POST" });

export const projectOverview = (locale: Locale, id: string) =>
  apiFetch<ProjectOverview>(`${base}/projects/${id}/overview`, { locale });

export const projectFiles = (locale: Locale, id: string) =>
  apiFetch<ProjectFile[]>(`${base}/projects/${id}/files`, { locale });

export const linkFile = (locale: Locale, id: string, fileId: string) =>
  apiFetch<ProjectFile>(`${base}/projects/${id}/files`, {
    locale,
    method: "POST",
    body: JSON.stringify({ asset_id: fileId }),
  });

export const fileImpact = (locale: Locale, id: string, fileId: string) =>
  apiFetch<Impact>(`${base}/projects/${id}/files/${fileId}/impact`, { locale });

/**
 * الإزالة تُقرّ قبل أن تقع.
 *
 * فالخادم يرفض بـ409 ما دام يقطع سندًا عن عملٍ اعتمده الباحث، ولا يُمرَّر
 * `acknowledged` إلا بعد أن يرى ما يترتب ويوافق — **والتحذير بعد الفعل ليس
 * تحذيرًا**.
 */
export const unlinkFile = (
  locale: Locale,
  id: string,
  fileId: string,
  acknowledged = false,
) =>
  apiFetch<Impact>(
    `${base}/projects/${id}/files/${fileId}?acknowledged=${acknowledged}`,
    { locale, method: "DELETE" },
  );

export const projectSources = (locale: Locale, id: string) =>
  apiFetch<ProjectSource[]>(`${base}/projects/${id}/sources`, { locale });

/**
 * قرّر حال المرجع في هذا البحث.
 *
 * **والاستبعاد يحمل سببه معه.** فالخادم يردّ استبعادًا بلا رمزٍ من قائمته
 * المغلقة، و«سبب آخر» يلزمه نصّه. وإرسالُ الحال أولًا ثم السبب في طلبٍ ثانٍ
 * كان سيترك دراسةً مستبعَدة بلا سبب لو فشل الثاني — وهي الحال نفسها التي
 * أُنشئ الحقل ليمنعها.
 */
export const setSourceUse = (
  locale: Locale,
  id: string,
  sourceId: string,
  useState: ProjectSource["use_state"],
  reason?: { reason_code?: string; reason_ar?: string },
) =>
  apiFetch<ProjectSource>(`${base}/projects/${id}/sources/${sourceId}`, {
    locale,
    method: "PATCH",
    body: JSON.stringify({ use_state: useState, ...(reason ?? {}) }),
  });

/** مصدرٌ في مكتبة الباحث — مرشَّحٌ للربط ببحث. */
export interface LibrarySource {
  id: string;
  title: string;
  doi: string | null;
  publication_year: number | null;
  journal_name: string | null;
  authors: string[] | null;
}

export const listLibrarySources = (locale: Locale) =>
  apiFetch<LibrarySource[]>("/api/v1/sources", { locale });

/**
 * اربط مرجعًا من المكتبة بهذا البحث.
 *
 * **مسارٌ كان في الخادم بلا بابٍ في المتصفح.** `POST …/sources` قائمٌ
 * ويُنشئ العلاقة بحال `saved_only`، ولم تكن في الواجهة نافذةٌ تبلغه —
 * فالباحث يرى مراجعه ولا يستطيع أن ينسبها إلى بحثه.
 *
 * والحال الابتدائية تأتي من الخادم لا من هنا: **الاستيراد ليس حكمًا
 * بالصلاحية دليلًا**، والترقية إلى «مُدرَج» قرارُ الباحث وحده.
 */
export const linkSource = (locale: Locale, id: string, sourceId: string) =>
  apiFetch<ProjectSource>(`${base}/projects/${id}/sources`, {
    locale,
    method: "POST",
    body: JSON.stringify({ asset_id: sourceId }),
  });
