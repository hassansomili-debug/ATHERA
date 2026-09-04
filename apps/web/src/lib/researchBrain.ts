/**
 * العقل البحثي كما يقرؤه الباحث | The Research Brain, as the researcher reads it.
 *
 * **الخانات خمس، ولا نسبة.** والخادم يحسمها في
 * `services/research_assessment/view.py`؛ وهذا الملف ينقلها ولا يعيد
 * ترتيبها ولا يجمعها في رقم. و«بحثك جاهز بنسبة ٨٢٪» تخفي الفرق بين بحثٍ
 * ينقصه سطرٌ وبحثٍ ينقصه منهج، فلا حقل هنا تُكتب فيه ولا اشتقاقَ يُنتجها.
 *
 * **والرتبة تصل مع التنبيه.** سطرٌ يقول «ادّعاءٌ بلا دليل» بمعرّف قاعدةٍ
 * مجرّد يُقرأ حكمًا معتمَدًا، وكلّ قواعد السجل مسوّدة لم يراجعها مختصّ.
 * فـ`scientificRules` تُقرأ مرّة وتُضمّ إلى الأسطر عند العرض.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/** خانات التقييم الخمس — بأسمائها في العقد لا بترتيبٍ يُخترع في الشاشة. */
export const ASSESSMENT_CATEGORIES = [
  "known",
  "missing",
  "needs_review",
  "conflicts",
  "methodological_alerts",
] as const;

export type AssessmentCategory = (typeof ASSESSMENT_CATEGORIES)[number];

export interface AssessmentItem {
  key: string;
  detail: string;
  rule_id: string | null;
  entity_ids: string[];
  excerpt: string | null;
}

export interface ProjectAssessment {
  project_id: string;
  title: string;
  known: AssessmentItem[];
  missing: AssessmentItem[];
  needs_review: AssessmentItem[];
  conflicts: AssessmentItem[];
  methodological_alerts: AssessmentItem[];
  /** ما تعذّرت قراءته — يُعرض بجانب الحكم لا في حاشية. */
  read_notes: AssessmentItem[];
  is_advisory_only: boolean;
  blocking_count: number;
  advisory_note: string;
  note: string;
}

/**
 * رتبة القاعدة ومصدرها — أربع رتب، و`APPROVED` وحدها تحجب.
 *
 * `is_enforceable` تُقرأ من الخادم ولا تُشتقّ هنا: إعادةُ كتابة شرط الحجب
 * في المتصفّح تجعل شاشةً تَعِد بحجبٍ بعد اعتمادٍ لم يقع.
 */
export interface ScientificRule {
  id: string;
  category: string;
  severity: string;
  status: "DRAFT" | "EXPERT_REVIEWED" | "APPROVED" | "DEPRECATED";
  is_enforceable: boolean;
  condition: string;
  message: string;
  provenance: string;
  related_issue_keys: string[];
  version: number;
}

export const projectAssessment = (locale: Locale, projectId: string) =>
  apiFetch<ProjectAssessment>(
    `/api/v1/workspace/projects/${projectId}/assessment`,
    { locale },
  );

export const scientificRules = (locale: Locale) =>
  apiFetch<ScientificRule[]>("/api/v1/brain/rules", { locale });

/** فهرسُ القواعد بمعرّفاتها — لضمّ الرتبة إلى السطر الذي جاء منها. */
export function ruleIndex(rules: ScientificRule[]): Map<string, ScientificRule> {
  return new Map(rules.map((rule) => [rule.id, rule]));
}

/**
 * عددُ ما في الخانات كلها — **عددٌ لا نسبة**.
 *
 * وهو ما تُبنى عليه جملة «لا شيء في هذه الخانة» بعد وصول الجواب: خانةٌ
 * فارغة على شاشةٍ لم تسأل بعد تُقرأ براءةً، وبحثٌ فارغ ليس بحثًا سليمًا.
 */
export function totalItems(assessment: ProjectAssessment): number {
  return ASSESSMENT_CATEGORIES.reduce(
    (sum, category) => sum + assessment[category].length,
    0,
  );
}
