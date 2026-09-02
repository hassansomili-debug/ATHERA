/**
 * مكتبة الباحث | The researcher's library.
 *
 * **تعريفٌ واحد لملف المكتبة.** كان الشكل مُعلنًا داخل صفحة المكتبة وحدها،
 * فأول شاشةٍ أخرى تحتاجه تنسخه — ونسختان تفترقان بأول حقلٍ يُضاف، فتقرأ
 * إحداهما حقلًا لا تعرفه الأخرى. فيُستخرج إلى موضعٍ واحد تقرأه الشاشتان.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

export interface LibraryFile {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
  processing_status: string;
  thesis_id: string | null;
  candidates: number;
  reviewed: number;
}

export const listLibraryFiles = (locale: Locale) =>
  apiFetch<LibraryFile[]>("/api/v1/files", { locale });
