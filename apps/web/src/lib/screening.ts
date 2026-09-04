/**
 * الفرز ومصفوفة الأدبيات | Screening and the literature matrix (PUBRIVA).
 *
 * **قرارُ الفرز يمرّ بالمسار القائم نفسه.** `setSourceUse` في `workspace.ts`
 * هي التي تكتب حال الاستعمال، وهذا الملف لا يكتب حالًا بنفسه — دالّتان
 * تكتبان الشيء نفسه تفترقان بأول شرطٍ يُضاف، فتصير شاشةٌ تشترط سبب
 * الاستبعاد وأخرى لا تشترطه.
 *
 * **والمدى ليس تفصيلًا تقنيًّا.** `reading_scope` هو الفرق بين قراءةٍ
 * وادّعاء قراءة، ولذلك يُعرض في الشاشة نصًّا صريحًا: «تم التحليل من الملخص
 * فقط» ليست حاشية، هي أهمّ ما في الخانة.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";
import { setSourceUse } from "./workspace";

/** حال الخانة — مفردات المنصّة نفسها، لا مفردات ثانية تعني الشيء نفسه. */
export type CellState = "known" | "needs_review" | "missing" | "conflicting";

/** مدى ما قُرئ من المصدر. مرتَّبٌ من الأضعف إلى الأقوى. */
export type SourceScope = "metadata_only" | "abstract_only" | "full_text";

export type ExtractionMethod = "researcher" | "metadata" | "model";

export type VerificationStatus = "unverified" | "approved" | "rejected" | "unknown";

export interface ScreeningCard {
  source_id: string;
  title: string;
  authors: string[];
  publication_year: number | null;
  venue: string | null;
  /** يغيب ما لم يكن المرجع متحقَّقًا — ولا يُعرض معرّفٌ لم يُفحص. */
  doi: string | null;
  registry: string | null;
  verification_status: string;
  retraction_status: string;
  use_state: "included" | "saved_only" | "excluded";
  exclusion_reason_code: string | null;
  reason_ar: string | null;
  decided_at: string | null;
  added_at: string | null;
  reading_scope: SourceScope;
  has_abstract: boolean;
}

export interface ScreeningView {
  project_id: string;
  cards: ScreeningCard[];
  saved_only: number;
  included: number;
  excluded: number;
  /** مفردة الأسباب تأتي من الخادم — والواجهة تعرض أسماءها ولا تخترع رمزًا. */
  reason_codes: string[];
}

export interface MatrixCell {
  field_key: string;
  value_ar: string | null;
  cell_state: CellState;
  source_scope: SourceScope;
  extraction_method: ExtractionMethod;
  verification_status: VerificationStatus;
  source_file_id: string | null;
  evidence_quote: string | null;
  evidence_locator: string | null;
}

export interface MatrixRow {
  source_id: string;
  title: string;
  authors: string[];
  publication_year: number | null;
  doi: string | null;
  reading_scope: SourceScope;
  cells: MatrixCell[];
}

export interface MatrixView {
  project_id: string;
  fields: string[];
  rows: MatrixRow[];
  note_ar: string;
}

const base = "/api/v1/workspace";

export const loadScreening = (
  locale: Locale,
  projectId: string,
  useState?: ScreeningCard["use_state"],
) =>
  apiFetch<ScreeningView>(
    `${base}/projects/${projectId}/screening${useState ? `?use_state=${useState}` : ""}`,
    { locale },
  );

/**
 * قرارُ فرزٍ واحد — **والاستبعاد يحمل سببه معه**.
 *
 * ولا تُرسَل الحال بلا سببها ثم يُرسَل السبب في طلبٍ ثانٍ: فشلُ الثاني
 * يترك دراسةً مستبعَدة بلا سبب، وهي بالضبط الحال التي أُنشئ الحقل ليمنعها.
 */
export const decideSource = (
  locale: Locale,
  projectId: string,
  sourceId: string,
  decision: {
    use_state: ScreeningCard["use_state"];
    reason_code?: string;
    reason_ar?: string;
  },
) =>
  setSourceUse(locale, projectId, sourceId, decision.use_state, {
    reason_code: decision.reason_code,
    reason_ar: decision.reason_ar,
  });

export const loadMatrix = (locale: Locale, projectId: string) =>
  apiFetch<MatrixView>(`${base}/projects/${projectId}/matrix`, { locale });

export const setMatrixCell = (
  locale: Locale,
  projectId: string,
  sourceId: string,
  fieldKey: string,
  cell: {
    cell_state: CellState;
    source_scope: SourceScope;
    value_ar?: string | null;
    evidence_quote?: string | null;
    evidence_locator?: string | null;
  },
) =>
  apiFetch<MatrixCell>(
    `${base}/projects/${projectId}/matrix/${sourceId}/${fieldKey}`,
    { locale, method: "PUT", body: JSON.stringify(cell) },
  );

export const verifyMatrixCell = (
  locale: Locale,
  projectId: string,
  sourceId: string,
  fieldKey: string,
  verification: Exclude<VerificationStatus, "unverified">,
) =>
  apiFetch<MatrixCell>(
    `${base}/projects/${projectId}/matrix/${sourceId}/${fieldKey}/verify`,
    { locale, method: "POST", body: JSON.stringify({ verification_status: verification }) },
  );

/**
 * وصفُ المرجع في سطرٍ واحد — **يُستعمل اسمًا مُعلَنًا لكل زرّ متكرّر**.
 *
 * وفي شاشة الفرز عشرات الأزرار المتطابقة الاسم: «إدراج» بجانب «إدراج»
 * بجانب «إدراج». فمن يتنقّل بلوحة المفاتيح أو يسمع الشاشة لا يميّز بينها
 * إطلاقًا. فيُلحق بكل زرٍّ عنوان دراسته.
 */
export function describe(card: { title: string; publication_year: number | null }): string {
  return card.publication_year ? `${card.title} (${card.publication_year})` : card.title;
}
