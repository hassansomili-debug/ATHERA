/**
 * من كشفٍ إلى فعلٍ مقترح إلى معاينة | Finding → suggested action → preview.
 *
 * **الكشفُ لا يُنشئ التزامًا.** والسلسلة أربع حلقات:
 *
 *     كشف → فعلٌ مقترح → معاينة → يقبل الباحث → تُنشأ مهمة
 *
 * والحلقة الرابعة ليست في هذا الملف ولا في هذا المسار: نموذجُ المهمّة
 * للمسار «ب»، والطلبُ في `docs/integration/track-f-requests.md`. وما هنا
 * ينتهي عند المعاينة.
 *
 * **والمساران `GET`.** الفعلُ الذي لا يملك مسارَ كتابةٍ لا يكتب، ولا يحتاج
 * الباحث أن يصدّق وعدًا بأنّ شيئًا لم يُسجَّل — شكلُ الطلب يقوله.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/** خانةُ الكشف الذي جاء منه الاقتراح — بأسماء العقد لا بترتيبٍ يُخترع. */
export const ACTIONABLE_CATEGORIES = [
  "missing",
  "needs_review",
  "conflicts",
  "methodological_alerts",
] as const;

export type ActionableCategory = (typeof ACTIONABLE_CATEGORIES)[number];

/** حالات المعرفة الأربع — مفردة المستودع نفسها لا مفردةٌ ثانية للاقتراحات. */
export type KnowledgeState =
  | "known"
  | "missing"
  | "needs_review"
  | "conflicting";

export interface SuggestedAction {
  key: string;
  finding_key: string;
  category: string;
  state: KnowledgeState;
  action_kind: string;
  title: string;
  detail: string;
  rule_id: string | null;
  rule_status: string | null;
  rule_is_enforceable: boolean;
  provenance: string | null;
  excerpt: string | null;
  entity_ids: string[];
  has_evidence: boolean;
  /**
   * ثابتةٌ `false` في العقد.
   *
   * وتُقرأ ولا تُفترض: شاشةٌ تفترض أنّ الخادم لا يُنشئ شيئًا تبقى صادقةً
   * حتى يتغيّر الخادم، ثم تكذب بلا أن يتغيّر فيها سطر.
   */
  creates_obligation: boolean;
}

export interface SuggestedActionsResponse {
  project_id: string;
  actions: SuggestedAction[];
  advisory_note: string;
}

export interface UndeterminedField {
  key: string;
  label: string;
}

export interface TaskPreview {
  action_key: string;
  title: string;
  detail: string;
  source: string;
  excerpt: string | null;
  entity_ids: string[];
  /** ما لا يعرفه هذا المسار عن المهمّة — يُسمَّى ولا يُملأ باختراع. */
  undetermined_fields: UndeterminedField[];
  is_preview: boolean;
  created: boolean;
  not_created_note: string;
  pending_contract_note: string;
}

export const suggestedActions = (locale: Locale, projectId: string) =>
  apiFetch<SuggestedActionsResponse>(
    `/api/v1/projects/${projectId}/brain/suggested-actions`,
    { locale },
  );

export const suggestedActionPreview = (
  locale: Locale,
  projectId: string,
  actionKey: string,
) =>
  apiFetch<TaskPreview>(
    `/api/v1/projects/${projectId}/brain/suggested-actions/preview` +
      `?action_key=${encodeURIComponent(actionKey)}`,
    { locale },
  );

/**
 * اقتراحاتُ كشفٍ بعينه — يُضمّ الاقتراح إلى سطره في الشاشة.
 *
 * والمطابقة على `finding_key` **ومواضعه** معًا: القاعدة الواحدة تقع على
 * مواضع، ومطابقةُ المفتاح وحده تضمّ اقتراحَ متغيّرٍ إلى سطر متغيّرٍ آخر —
 * فيقرأ الباحث «راجع أداة الوسيط» تحت التابع.
 */
export function actionsFor(
  actions: SuggestedAction[],
  findingKey: string,
  entityIds: string[],
): SuggestedAction[] {
  const where = entityIds.length > 0 ? entityIds.join("-") : "-";
  return actions.filter(
    (action) =>
      action.finding_key === findingKey &&
      (action.entity_ids.length > 0 ? action.entity_ids.join("-") : "-") === where,
  );
}
