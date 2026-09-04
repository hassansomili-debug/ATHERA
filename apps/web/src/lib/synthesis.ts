/**
 * طبقة التركيب | Synthesis: themes, contradictions, gaps, opportunities.
 *
 * **الأسماء تأتي من الخادم مترجَمة.** فلا تخترع الواجهة اسمًا لمفردة، ولا
 * تبني جدول ترجمةٍ ثانيًا يفترق عن جدول الخادم بأول إضافة — فيظهر في
 * الشاشة `weak_signal` بدل «إشارة ضعيفة» ولا يفشل شيء.
 *
 * **والحدُّ يُعرض مع الدعوى دائمًا.** `sources_considered` و`search_scope`
 * و`known_limitations_ar` حقولٌ إلزامية في العقد، ولا تُعرض فجوةٌ بدونها:
 * وصفٌ بلا حدّه يُقرأ جملةً مطلقة، ثم يُكتب في ورقة.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/** دورة الحياة — مفردات المنصّة نفسها، ولا `UNSURE` ولا `MAYBE`. */
export type SynthesisStatus =
  | "generated"
  | "needs_review"
  | "approved"
  | "rejected"
  | "unknown";

/** ما يقبله الخادم حكمًا — و«مقترَح» ليست منها: قبولها محوُ مراجعة. */
export type Decision = Exclude<SynthesisStatus, "generated">;

/** **الفرق الذي لا يُطوى**: تجميعٌ من عناوين مقابل تركيبٍ من محتوًى مقروء. */
export type ThemeBasis = "topic_cluster" | "content_synthesis";

export type GapStrength = "weak_signal" | "emerging_pattern" | "supported_candidate";

export type SourceScope = "metadata_only" | "abstract_only" | "full_text";

export interface VocabularyEntry {
  key: string;
  label_ar: string;
  label_en: string;
  meaning_ar: string | null;
}

/** حلقةٌ في سلسلة الأثر: مرجع ← خلية ← شاهد. */
export interface EvidenceLink {
  source_id: string;
  title: string;
  role: "supporting" | "contradicting" | "considered";
  basis_field_key: string | null;
  /** غيابه يعني سندًا من بياناتٍ وصفية — وتلك حالٌ تُعلَن لا تُخفى. */
  matrix_cell_id: string | null;
  evidence_scope: SourceScope;
  evidence_quote: string | null;
  evidence_locator: string | null;
  cell_state: string | null;
  cell_value_ar: string | null;
}

export interface Theme {
  id: string;
  label_ar: string;
  description_ar: string | null;
  basis: ThemeBasis;
  basis_label_ar: string;
  basis_meaning_ar: string;
  status: SynthesisStatus;
  status_label_ar: string;
  source_scope_summary: Record<string, number>;
  supporting_count: number;
  contradicting_count: number;
  is_traceable: boolean;
  generated_at: string | null;
  decided_at: string | null;
}

export interface ThemesView {
  project_id: string;
  themes: Theme[];
  corpus_size: number;
  note_ar: string;
  basis_vocabulary: VocabularyEntry[];
}

export interface ThemeTrace {
  theme: Theme;
  supporting: EvidenceLink[];
  contradicting: EvidenceLink[];
  note_ar: string;
}

export interface ContradictionSide {
  side: "a" | "b";
  source_id: string;
  title: string;
  result_ar: string;
  direction: string;
  direction_label_ar: string;
  significance: string;
  significance_label_ar: string;
  population_ar: string | null;
  country_ar: string | null;
  method_ar: string | null;
  measurement_ar: string | null;
  period_year: number | null;
  evidence_scope: SourceScope;
  matrix_cell_id: string | null;
}

export interface Contradiction {
  id: string;
  construct_a_ar: string;
  construct_b_ar: string | null;
  relationship_ar: string;
  conflict_kind: string;
  conflict_label_ar: string;
  context_divergence: string[];
  context_divergence_labels_ar: string[];
  context_explanation_ar: string | null;
  status: SynthesisStatus;
  status_label_ar: string;
  sides: ContradictionSide[];
  generated_at: string | null;
  decided_at: string | null;
}

export interface ContradictionsView {
  project_id: string;
  contradictions: Contradiction[];
  corpus_size: number;
  note_ar: string;
}

export interface SearchScope {
  indexes_searched: string[];
  /** تبقى `false`: لا بحث منهجيّ في الفهارس، والادّعاء بغيره يقلب المعنى. */
  search_was_systematic: boolean;
  corpus_size: number;
  content_read: number;
  full_text_read: number;
  saved_not_screened: number;
  excluded: number;
  taken_at: string | null;
}

export interface Gap {
  id: string;
  gap_type: string;
  gap_type_label_ar: string;
  description_ar: string;
  why_suggested_ar: string;
  known_limitations_ar: string;
  strength: GapStrength;
  strength_label_ar: string;
  strength_meaning_ar: string;
  sources_considered: number;
  search_scope: SearchScope;
  source_scope_distribution: Record<string, number>;
  supporting: EvidenceLink[];
  contradicting: EvidenceLink[];
  considered: EvidenceLink[];
  contradiction_id: string | null;
  status: SynthesisStatus;
  status_label_ar: string;
  generated_at: string | null;
  decided_at: string | null;
  may_become_opportunity: boolean;
}

/** **ما تعذّر الحكم فيه** — يُعرض بقدر ما يُعرض ما وُجد. */
export interface NotAssessed {
  gap_type: string;
  gap_type_label_ar: string;
  verdict: "insufficient_information";
  reason_ar: string;
}

export interface GapsView {
  project_id: string;
  gaps: Gap[];
  not_assessed: NotAssessed[];
  corpus_size: number;
  search_scope: SearchScope | null;
  strength_vocabulary: VocabularyEntry[];
  note_ar: string;
}

export interface RelatedStudy {
  source_id: string;
  title: string;
  role: string;
  evidence_scope: SourceScope;
}

export interface OpportunityPreview {
  gap_candidate_id: string;
  gap_type: string;
  gap_type_label_ar: string;
  what_we_noticed_ar: string;
  why_it_might_matter_ar: string;
  evidence_basis_ar: string;
  related_studies: RelatedStudy[];
  still_uncertain_ar: string;
  strength_label_ar: string;
  strength_meaning_ar: string;
  next_step_ar: string;
  editable_fields: string[];
  requires_confirmation: boolean;
}

export interface Opportunity {
  id: string;
  gap_candidate_id: string;
  gap_type: string;
  gap_type_label_ar: string;
  phenomenon_ar: string;
  context_ar: string | null;
  population_ar: string | null;
  constructs_ar: string | null;
  possible_contribution_ar: string;
  methodological_opportunity_ar: string | null;
  evidence_basis_ar: string;
  uncertainties_ar: string;
  created_at: string | null;
  spawned_project_id: string | null;
}

export interface OpportunitiesView {
  project_id: string;
  opportunities: Opportunity[];
  note_ar: string;
}

export interface ProjectPreview {
  working_title_ar: string;
  from_opportunity_id: string;
  gap_type_label_ar: string;
  will_create_ar: string[];
  /** **ما لن يقع** — وبدونه يظنّ الباحث أن مراجعه ستُنقل. */
  will_not_create_ar: string[];
  unchanged_ar: string[];
  requires_confirmation: boolean;
}

const base = "/api/v1/synthesis";

export const loadThemes = (locale: Locale, projectId: string) =>
  apiFetch<ThemesView>(`${base}/projects/${projectId}/themes`, { locale });

export const loadThemeTrace = (locale: Locale, projectId: string, themeId: string) =>
  apiFetch<ThemeTrace>(`${base}/projects/${projectId}/themes/${themeId}/trace`, {
    locale,
  });

export const loadContradictions = (locale: Locale, projectId: string) =>
  apiFetch<ContradictionsView>(`${base}/projects/${projectId}/contradictions`, {
    locale,
  });

export const loadGaps = (locale: Locale, projectId: string) =>
  apiFetch<GapsView>(`${base}/projects/${projectId}/gaps`, { locale });

export const loadOpportunities = (locale: Locale, projectId: string) =>
  apiFetch<OpportunitiesView>(`${base}/projects/${projectId}/opportunities`, {
    locale,
  });

/**
 * إعادة التحليل — **ولا تمحو حكمًا قاله الباحث**.
 *
 * والخادم هو من يحرس ذلك (يستبدل ما لم يُحكم فيه وحده)، والواجهة تقول ذلك
 * للباحث قبل الضغط: زرٌّ لا يُعرف أثره يُضغط ثم يُندَم عليه.
 */
export const analyze = (locale: Locale, projectId: string) =>
  apiFetch<ThemesView>(`${base}/projects/${projectId}/analyze`, {
    locale,
    method: "POST",
  });

export const decideTheme = (
  locale: Locale,
  projectId: string,
  themeId: string,
  status: Decision,
) =>
  apiFetch<Theme>(`${base}/projects/${projectId}/themes/${themeId}/decision`, {
    locale,
    method: "POST",
    body: JSON.stringify({ status }),
  });

export const decideContradiction = (
  locale: Locale,
  projectId: string,
  contradictionId: string,
  status: Decision,
) =>
  apiFetch<{ status: Decision }>(
    `${base}/projects/${projectId}/contradictions/${contradictionId}/decision`,
    { locale, method: "POST", body: JSON.stringify({ status }) },
  );

export const decideGap = (
  locale: Locale,
  projectId: string,
  gapId: string,
  status: Decision,
) =>
  apiFetch<Gap>(`${base}/projects/${projectId}/gaps/${gapId}/decision`, {
    locale,
    method: "POST",
    body: JSON.stringify({ status }),
  });

export const loadOpportunityPreview = (
  locale: Locale,
  projectId: string,
  gapId: string,
) =>
  apiFetch<OpportunityPreview>(
    `${base}/projects/${projectId}/gaps/${gapId}/opportunity-preview`,
    { locale },
  );

/** **البطاقة لا تُنشأ بلا تأكيدٍ صريح** — والخادم يرفضها بدونه أيضًا. */
export const createOpportunity = (
  locale: Locale,
  projectId: string,
  card: {
    gap_candidate_id: string;
    confirmed: true;
    phenomenon_ar: string;
    context_ar?: string | null;
    population_ar?: string | null;
    constructs_ar?: string | null;
    possible_contribution_ar: string;
    methodological_opportunity_ar?: string | null;
    evidence_basis_ar: string;
    uncertainties_ar: string;
  },
) =>
  apiFetch<Opportunity>(`${base}/projects/${projectId}/opportunities`, {
    locale,
    method: "POST",
    body: JSON.stringify(card),
  });

export const loadProjectPreview = (
  locale: Locale,
  projectId: string,
  opportunityId: string,
) =>
  apiFetch<ProjectPreview>(
    `${base}/projects/${projectId}/opportunities/${opportunityId}/project-preview`,
    { locale },
  );

export const createProjectFromOpportunity = (
  locale: Locale,
  projectId: string,
  opportunityId: string,
  workingTitleAr: string,
) =>
  apiFetch<Opportunity>(
    `${base}/projects/${projectId}/opportunities/${opportunityId}/project`,
    {
      locale,
      method: "POST",
      body: JSON.stringify({ confirmed: true, working_title_ar: workingTitleAr }),
    },
  );

/**
 * وصفُ المرشَّح في سطر — **اسمًا مُعلَنًا لكل زرٍّ متكرّر**.
 *
 * وفي كل شاشةٍ هنا صفٌّ من أزرارٍ متطابقة الاسم: «اعتماد» بجانب «اعتماد».
 * فمن يتنقّل بلوحة المفاتيح أو يسمع الشاشة لا يميّز بينها إطلاقًا.
 */
export function describe(item: { label?: string; title?: string }): string {
  return item.label ?? item.title ?? "";
}
