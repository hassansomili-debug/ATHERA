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

/* ═══════════ الذكاء البحثيّ: أين يقف البحث وما الخطوة التالية ═══════════
 *
 * **ولا منطقَ رحلةٍ يُعاد بناؤه هنا** (§80). الخادمُ يقول الحال والسبب
 * والفعل، والشاشةُ تعرض. وكلُّ شرطٍ يُكتب في React نسخةٌ ثانية من قاعدةٍ
 * تفترق عن أصلها بأول تعديل — ثمّ تعرض الشاشةُ حكمًا لا يقوله الخادم.
 */

/** حالُ الفعل كما يقولها الخادم — لا تُشتقّ في المتصفّح. */
export type ActionStatus =
  | "recommended"
  | "available"
  | "blocked"
  | "optional"
  | "completed";

export interface JourneyAction {
  action_key: string;
  category: string;
  status: ActionStatus;
  title: string;
  reason: string;
  route: string | null;
  blocking_reasons: string[];
  requirements: string[];
  evidence_refs: string[];
}

/** بوّابةٌ حتمية — ما **يمكن** الآن، مفصولًا عمّا يُستحسن. */
export interface JourneyCapability {
  key: string;
  allowed: boolean;
  blocking_reasons: string[];
}

export interface ProjectJourney {
  project_id: string;
  title: string;
  /** بصمةُ الحال — **لا تُعرض للباحث العاديّ** (§84)، وتُقرأ في التشخيص. */
  context_fingerprint: string;
  fingerprint_schema: string;
  first_seen_at: string;
  last_seen_at: string;
  recommended: JourneyAction | null;
  actions: JourneyAction[];
  capabilities: JourneyCapability[];
  known_count: number;
  missing_count: number;
  needs_review_count: number;
  conflict_count: number;
  superseded_now: number;
  limitations: string;
  note: string;
}

/**
 * جوابٌ مشوَّهٌ **قراءةٌ لم تصل**، لا شاشةٌ تنهار.
 *
 * و`apiFetch` تُرجع ما وصل كما هو: ردٌّ بحالة 200 وجسمٍ غيرِ متوقَّع يمرّ
 * بلا خطأ، فتقرأ الشاشةُ `undefined.filter` وتسقط الشجرةُ كلُّها — ويقرأ
 * الباحثُ صفحةً بيضاء عن بحثٍ لا عيب فيه.
 *
 * وهذا وقع فعلًا: تجهيزةُ فحصٍ قائمة تردّ `[]` على ما لا تعرفه، فأسقطت
 * شاشةَ العقل بأكملها عند إضافة هذه اللوحة. والعلاجُ أن يُفحص الشكل، لا
 * أن تُعدَّل التجهيزة وحدها — فالإنتاج قد يردّ مشوَّهًا كما ردّت هي.
 */
function isJourney(value: unknown): value is ProjectJourney {
  const row = value as ProjectJourney | null;
  return (
    !!row &&
    typeof row === "object" &&
    !Array.isArray(row) &&
    Array.isArray(row.actions) &&
    Array.isArray(row.capabilities) &&
    typeof row.context_fingerprint === "string"
  );
}

export const projectJourney = (locale: Locale, projectId: string) =>
  apiFetch<unknown>(
    `/api/v1/workspace/projects/${projectId}/journey`,
    { locale },
  ).then((body) => {
    if (!isJourney(body)) {
      throw new Error("journey payload is not shaped like a journey");
    }
    return body;
  });

/**
 * مسارُ الفعل موصولًا بلغة القارئ.
 *
 * والخادمُ يرسله بلا لغة عمدًا: رابطٌ عربيٌّ يُفتح لقارئٍ إنجليزيّ يخرجه
 * من لغته بلا أن يطلب.
 */
export function localeRoute(locale: Locale, route: string | null): string | null {
  if (!route) return null;
  return `/${locale}${route}`;
}
