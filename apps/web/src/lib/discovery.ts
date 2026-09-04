/**
 * اكتشاف المراجع | Reference discovery client.
 *
 * **ثلاثة أشياء لا يجوز أن تصير شيئًا واحدًا**: نتيجةُ بحثٍ في فهرسٍ
 * خارجي، ومرجعٌ مخزَّن في مكتبة الباحث، ودليلٌ يُبنى عليه ادعاء. ولذلك
 * `Candidate` هنا **بلا معرّف في قاعدتنا وبلا حال استعمال**: النوع نفسه
 * يمنع أن يُمرَّر مرشَّحٌ حيث يُنتظر مرجع.
 *
 * والحفظ فعلٌ مستقل يمرّ بالمسار القائم `POST /sources/import` — لا يُعاد
 * بناؤه هنا: مسارٌ ثانٍ للاستيراد يعني قاعدتَي تحقّقٍ تفترقان يومًا.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/** ما قاله فهرسٌ واحد — منسوبًا إليه بالاسم. */
export interface ProviderClaim {
  provider: string;
  provider_id: string;
  doi: string | null;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  abstract: string | null;
  url: string | null;
  open_access: boolean | null;
  citation_count: number | null;
  /** `type` نصّ الفهرس كما قاله، و`work_type` سلّة العرض الموحّدة بين الفهارس. */
  type: string | null;
  work_type: string | null;
  retraction_status: string;
}

/** لماذا اجتمعت ادعاءات الفهارس في بطاقةٍ واحدة — يُعرض ليُراجَع. */
export type MatchBasis = "doi" | "provider_id" | "title_year_author" | "single";

/**
 * سببُ موضع النتيجة في الترتيب، بلغة الباحث.
 *
 * **ولا نسبة في هذا النوع.** «٩٧٪ صلة» رقمٌ لا وحدة له ولا مرجع، ويقرؤه
 * الباحث حكمًا كميًّا على ورقةٍ لم يقرأها. والخادم لا يرسل درجة أصلًا،
 * فلا تستطيع هذه الشاشة اختراع واحدة ولو أرادت.
 */
export interface RankReason {
  code: string;
  /** `match` سببُ ترجيح، و`caution` تنبيهٌ يُقرأ قبل البناء عليه. */
  kind: "match" | "caution" | string;
  terms: string[];
  /** الاستشهاد لا يُذكر بلا قائله: «١٣٤ في OpenAlex». */
  provider: string | null;
  count: number | null;
  year: number | null;
}

/** مصطلحٌ مقترح — معروضٌ لا مُطبَّق. `applied` تعود `false` دائمًا. */
export interface SuggestedTerm {
  term: string;
  source_term: string;
  kind: string;
  applied: boolean;
}

/**
 * ما فهمه الخادم من نصّ الباحث.
 *
 * `raw` سؤاله و`sent` ما غادر إلى الفهارس. يُعرضان معًا حين يختلفان —
 * وهذا هو الحدّ بين «فهمِ الاستعلام» و«إعادةِ كتابته»: ما دام النصّان
 * مرئيَّين، لا يقع تبديلٌ لا يراه صاحبه.
 */
export interface QueryUnderstanding {
  raw: string;
  sent: string;
  doi: string | null;
  phrase: string | null;
  authors: string[];
  year: number | null;
  year_from: number | null;
  year_to: number | null;
  keywords: string[];
  accepted_terms: string[];
  suggestions: SuggestedTerm[];
}

export interface ReferenceCandidate {
  doi: string | null;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  abstract: string | null;
  url: string | null;
  open_access: boolean | null;
  type: string | null;
  work_type: string | null;
  retraction_status: string;
  providers: string[];
  /** عدّاد كل فهرسٍ منسوبًا إليه — **ولا مجموع**. */
  citation_counts: Record<string, number>;
  match_basis: MatchBasis;
  claims: ProviderClaim[];
  can_be_saved: boolean;
  /** أسبابُ موضعه في الترتيب — **ولا درجة**: الخادم لا يرسل واحدة. */
  reasons: RankReason[];
  matched_terms: string[];
  missing_terms: string[];
}

export interface ProviderStatus {
  provider: string;
  ok: boolean;
  detail: string | null;
  results: number;
}

export interface ExternalAccessLink {
  url: string;
  host: string;
  verified: boolean;
  note_ar: string;
  note_en: string;
}

export interface ReferenceSearchResponse {
  candidates: ReferenceCandidate[];
  providers: ProviderStatus[];
  providers_enabled: boolean;
  any_provider_failed: boolean;
  all_providers_failed: boolean;
  external_link: ExternalAccessLink | null;
  /** بأيّ شيء رُتِّبت النتائج. يُقال صراحةً لأن الباحث يفترض الترتيب الزمني. */
  ordered_by: string;
  query_understanding: QueryUnderstanding | null;
  note_ar: string;
  note_en: string;
}

export interface ReferenceSearchFilters {
  yearFrom?: number | null;
  yearTo?: number | null;
  workType?: string | null;
  openAccessOnly?: boolean;
  /**
   * ما قبِله الباحث من المصطلحات المقترحة — **ولا شيء غيره يوسّع البحث**.
   * وإرسال قائمة فارغة هو الحال الطبيعية: الاقتراح معروضٌ لا مُطبَّق.
   */
  acceptedTerms?: string[];
}

export const searchReferences = (
  locale: Locale,
  query: string,
  filters: ReferenceSearchFilters = {},
) =>
  apiFetch<ReferenceSearchResponse>("/api/v1/references/search", {
    locale,
    method: "POST",
    body: JSON.stringify({
      query,
      limit: 20,
      year_from: filters.yearFrom ?? null,
      year_to: filters.yearTo ?? null,
      work_type: filters.workType || null,
      open_access_only: Boolean(filters.openAccessOnly),
      accepted_terms: filters.acceptedTerms ?? [],
    }),
  });

/** المرجع المخزَّن كما يعيده الخادم — وله معرّفٌ في قاعدتنا، بخلاف المرشَّح. */
export interface StoredSource {
  id: string;
  doi: string | null;
  title: string;
  publication_year: number | null;
  journal_name: string | null;
  verification_status: string;
}

/**
 * احفظ في مكتبتي — **بمعرّفٍ شرعي وحده**.
 *
 * الخادم يحلّ الـDOI في فهرسٍ حقيقي أو يردّ بخطأ؛ ولا يُخزَّن مرجعٌ
 * مختلق. ومرشَّحٌ بلا DOI لا يُحفظ أصلًا — وذلك يُقال للباحث في الشاشة،
 * ولا يُسدّ بمعرّفٍ يُصنع له.
 */
export const saveToLibrary = (locale: Locale, doi: string) =>
  apiFetch<StoredSource>("/api/v1/sources/import", {
    locale,
    method: "POST",
    body: JSON.stringify({ doi }),
  });
