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
  /** **دعوى الفهرس لا قراءةٌ وقعت** — والاسم يقول ذلك، فلا يُقرأ «النص متاح». */
  index_says_open_access: boolean;
  document_type: string | null;
  /** تنبيهٌ لا حكم: الاستبعاد للتكرار يبقى قرارك بسببه المسجَّل. */
  possible_duplicate: boolean;
  abstract_sources: number;
  /** فهرسان أرسلا ملخّصين مختلفين — يُعرض اختلافًا ولا يُحسم بغلبة أحدهما. */
  abstracts_disagree: boolean;
}

/** خيارات التصفية الموجودة **في هذا البحث** — لا قائمة عامّة تُعرض للكلّ. */
export interface ScreeningFacets {
  registries: string[];
  document_types: string[];
  year_min: number | null;
  year_max: number | null;
}

/**
 * مرشّحات الفرز كما تُرسَل إلى الخادم.
 *
 * **والتصفية تقع هناك لا هنا.** ألفُ مرجعٍ لا تُحمَّل إلى المتصفّح لتُرمى
 * تسعُ مئة منها؛ ولو وقعت هنا لقال العدّاد «ثلاث دراسات» وهي ثلاثمائة.
 */
export interface ScreeningQuery {
  use_state?: ScreeningCard["use_state"];
  page?: number;
  page_size?: number;
  year_from?: number;
  year_to?: number;
  registry?: string;
  document_type?: string;
  open_access?: boolean;
  has_abstract?: boolean;
  has_full_text?: boolean;
  possible_duplicate?: boolean;
}

export interface ScreeningView {
  project_id: string;
  cards: ScreeningCard[];
  /**
   * العدّادات من الخادم — **وبكل المرشّحات إلا حال الفرز نفسها**.
   *
   * فالتبويب يسأل «كم مُدرَجة ضمن ما أراه الآن»، وعدٌّ فوق الصفحة المعروضة
   * يقول صفرًا في كل تبويبٍ سواه.
   */
  saved_only: number;
  included: number;
  excluded: number;
  all: number;
  page: number;
  page_size: number;
  /** ما تطابقه المرشّحات كلُّها ومنها الحال — وهو ما يُصفَّح. */
  total: number;
  pages: number;
  duplicates: number;
  facets: ScreeningFacets;
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
  /** من أي ملخّصٍ قُرئت، ومن أرسل ذلك الملخّص. */
  source_abstract_id: string | null;
  abstract_provider: string | null;
  /** **تُقال حين تُعرف وتُترك حين لا تُعرف** — ولا تُشتقّ من ترتيب مقطع. */
  evidence_page: number | null;
  evidence_section: string | null;
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
  page: number;
  page_size: number;
  /** عدد الدراسات المدرجة كلِّها — لا عدد صفوف هذه الصفحة. */
  total: number;
  pages: number;
  note_ar: string;
}

export interface SourceExtractionResult {
  source_id: string;
  scope: SourceScope;
  filled: number;
  marked_missing: number;
  /** خانات كتبتَها أو حكمتَ فيها — لم تُمسّ، ويُقال عددها. */
  left_to_the_researcher: number;
  fields: string[];
}

export interface MatrixExtractionView {
  project_id: string;
  results: SourceExtractionResult[];
  note_ar: string;
}

export interface AbstractRecord {
  id: string | null;
  provider: string;
  provider_identifier: string | null;
  text: string;
  retrieved_at: string | null;
}

export interface SourceAbstracts {
  source_id: string;
  abstracts: AbstractRecord[];
  disagree: boolean;
}

const base = "/api/v1/workspace";

/**
 * سطرُ الاستعلام — **وما لم يُختَر لا يُرسَل**.
 *
 * ومرشّحٌ يُرسَل بقيمةٍ فارغة ليس حيادًا: الخادم يقرؤه شرطًا، فتختفي
 * دراساتٌ لم يستبعدها أحد.
 */
function queryOf(query: ScreeningQuery): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export const loadScreening = (
  locale: Locale,
  projectId: string,
  query: ScreeningQuery = {},
) =>
  apiFetch<ScreeningView>(
    `${base}/projects/${projectId}/screening${queryOf(query)}`,
    { locale },
  );

/**
 * قرارُ فرزٍ على مجموعة — **يقع كلُّه أو لا يقع منه شيء**.
 *
 * ولا يُرسَل مرجعٌ مرجعًا في حلقة: تسعةَ عشرَ طلبًا نجحت وواحدٌ فشل تترك
 * الباحث لا يعرف أيُّها وقع، فيعيد الأمر فيقع بعضه مرّتين. فالطلب واحد،
 * والخادم يفحص المجموعة كلَّها قبل أن يكتب حرفًا.
 */
export const decideSources = (
  locale: Locale,
  projectId: string,
  sourceIds: string[],
  decision: {
    use_state: ScreeningCard["use_state"];
    reason_code?: string;
    reason_ar?: string;
  },
) =>
  apiFetch<{ applied: number; source_ids: string[]; note_ar: string }>(
    `${base}/projects/${projectId}/screening/batch`,
    {
      locale,
      method: "POST",
      body: JSON.stringify({ source_ids: sourceIds, ...decision }),
    },
  );

export const loadAbstracts = (locale: Locale, projectId: string, sourceId: string) =>
  apiFetch<SourceAbstracts>(
    `${base}/projects/${projectId}/sources/${sourceId}/abstracts`,
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

export const loadMatrix = (
  locale: Locale,
  projectId: string,
  page = 1,
  pageSize = 25,
) =>
  apiFetch<MatrixView>(
    `${base}/projects/${projectId}/matrix?page=${page}&page_size=${pageSize}`,
    { locale },
  );

/**
 * اقرأ ما هو متاحٌ لهذه الدراسات واكتب مقترحاتها.
 *
 * **وما يعود مقترحاتٌ تنتظر مراجعتك، لا معرفةً معتمدة.** وما لم تذكره
 * الدراسة يبقى «غير مذكور» — ولا يُملأ باسمٍ مخترَع.
 */
export const extractMatrix = (locale: Locale, projectId: string, sourceIds: string[]) =>
  apiFetch<MatrixExtractionView>(`${base}/projects/${projectId}/matrix/extract`, {
    locale,
    method: "POST",
    body: JSON.stringify({ source_ids: sourceIds }),
  });

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
    evidence_page?: number | null;
    evidence_section?: string | null;
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
