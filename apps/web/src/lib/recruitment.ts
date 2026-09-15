/**
 * الفرصُ البحثية | Research collaboration opportunities client (RC-T1C).
 *
 * **وهذا المجالُ ليس مجالَ «فرص النشر».** في المنصّة ثلاثةُ أشياء تحمل
 * كلمةَ «فرصة» ولا يجوز خلطُها:
 *
 *   `PublicationOpportunity`  ورقةٌ مقترحةٌ من رسالةٍ أو من فجوة — علمٌ.
 *   `ResearchOpportunity`     فجوةٌ تستحقّ بحثًا — علمٌ أيضًا.
 *   `RecruitmentOpportunity`  **دعوةُ تعاونٍ على بحثٍ قائم** — وهي هذه.
 *
 * ولذلك مسارُ الشاشة `collaboration-opportunities` لا `opportunities`:
 * الثانيةُ خريطةُ النشر القائمة، وتسميةُ هذا بها تُنتج شاشتين تدّعيان
 * العنوانَ نفسَه ومعناهما مختلف. **والاسمُ المعروضُ للباحث يبقى «الفرص
 * البحثية»** — الالتباسُ في الكود لا في اللغة.
 *
 * ولا تعاريفَ حالةٍ تُبنى هنا: الحالةُ النافذةُ تأتي من الخادم
 * (`effective_status`)، ومفرداتُ الأدوار والصلاحيات من مساراتها. فشاشةٌ
 * تشتقّ «مفتوحة» من تاريخين في المتصفّح تُخبر الباحثَ بغير ما ستقوله
 * القاعدةُ عند التقدّم.
 *
 * ولا حقلَ خاصًّا في الإسقاط العامّ: لا `project_id` ولا `tenant_id` ولا
 * `created_by` — الخادمُ لا يردّها أصلًا (RC-T1B)، والأنواعُ هنا تقول ذلك
 * كي لا تُكتب شاشةٌ تنتظرها.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

const BASE = "/api/v1/recruitment";

/** الإسقاطُ العامّ — ما يراه أيُّ باحثٍ يكتشف الإعلان. */
export interface PublicOpportunity {
  opportunity_id: string;
  title: string;
  description: string;
  contributions: string | null;
  requirements: string | null;
  specialization: string | null;
  openings_count: number;
  collaboration_type: string;
  public_label: string | null;
  starts_at: string | null;
  ends_at: string | null;
  effective_status: string;
}

/** وما يراه مديرُ البحث فوق ذلك — ولا يُعرض في الاكتشاف. */
export interface ManagerOpportunity extends PublicOpportunity {
  stored_status: string;
  deleted_at: string | null;
  applications_count: number;
  created_at: string;
}

export interface LinkedInvitation {
  invitation_id: string;
  state: string;
  usable: boolean;
  expires_at: string;
  membership_created: boolean;
}

export interface MyApplication {
  application_id: string;
  opportunity_id: string;
  title: string;
  status: string;
  message: string | null;
  submitted_at: string;
  decided_at: string | null;
  invitation: LinkedInvitation | null;
}

export interface ManagerApplication {
  application_id: string;
  display_name: string;
  status: string;
  message: string | null;
  submitted_at: string;
  decided_at: string | null;
  invitation: LinkedInvitation | null;
}

/** جوابُ الدعوة — **والرمزُ فيه يُعرض مرّةً ولا يُخزَّن**. */
export interface IssuedRecruitmentInvitation {
  application_id: string;
  application_status: string;
  invitation_id: string;
  invitation_state: string;
  role: string;
  permissions: string[];
  expires_at: string;
  token: string;
}

export interface OpportunityDraft {
  title: string;
  description: string;
  contributions?: string | null;
  requirements?: string | null;
  specialization?: string | null;
  openings_count?: number;
  collaboration_type?: string;
  public_label?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
}

function json(body: unknown): string {
  return JSON.stringify(body);
}

// ═══════════════════ الاكتشاف العامّ ═══════════════════

export function discoverOpportunities(locale: Locale): Promise<PublicOpportunity[]> {
  return apiFetch<PublicOpportunity[]>(`${BASE}/opportunities`, { locale });
}

export function opportunityDetail(
  locale: Locale,
  opportunityId: string,
): Promise<PublicOpportunity> {
  return apiFetch<PublicOpportunity>(`${BASE}/opportunities/${opportunityId}`, { locale });
}

// ═══════════════════ طلباتي ═══════════════════

export function applyToOpportunity(
  locale: Locale,
  opportunityId: string,
  message: string,
): Promise<MyApplication> {
  return apiFetch<MyApplication>(`${BASE}/opportunities/${opportunityId}/applications`, {
    method: "POST",
    locale,
    // **ولا هويّةَ في الجسم.** المتقدّمُ هو صاحبُ الرمز، والخادمُ يشتقّه
    // منه — لا من حقلٍ تُرسله الشاشة.
    body: json({ message: message.trim() || null }),
  });
}

export function myApplications(locale: Locale): Promise<MyApplication[]> {
  return apiFetch<MyApplication[]>(`${BASE}/applications/me`, { locale });
}

/** **المتقدّمُ يسحب، والمديرُ يُلغي** — فعلان مختلفان لا اسمان لفعل. */
export function withdrawApplication(
  locale: Locale,
  applicationId: string,
): Promise<MyApplication> {
  return apiFetch<MyApplication>(`${BASE}/applications/${applicationId}/withdraw`, {
    method: "POST",
    locale,
  });
}

// ═══════════ إعلاناتُ بحثٍ بعينه (للمدير) ═══════════
//
// **والبحثُ في المسار مُنتقي نطاقٍ لا سلطة.** فمن ليس مديرًا لهذا البحث
// يُردّ، ومَن هو مديرُه من مؤسسةٍ أخرى يعبُر إلى مستأجره بالجسر القانونيّ
// — وهذا هو سببُ كون هذه المسارات مُعشَّشةً تحت البحث أصلًا.

export function projectOpportunities(
  locale: Locale,
  projectId: string,
): Promise<ManagerOpportunity[]> {
  return apiFetch<ManagerOpportunity[]>(`${BASE}/projects/${projectId}/opportunities`, {
    locale,
  });
}

export function createOpportunity(
  locale: Locale,
  projectId: string,
  draft: OpportunityDraft,
): Promise<ManagerOpportunity> {
  return apiFetch<ManagerOpportunity>(`${BASE}/projects/${projectId}/opportunities`, {
    method: "POST",
    locale,
    body: json(draft),
  });
}

export function patchOpportunity(
  locale: Locale,
  projectId: string,
  opportunityId: string,
  patch: Partial<OpportunityDraft>,
): Promise<ManagerOpportunity> {
  return apiFetch<ManagerOpportunity>(
    `${BASE}/projects/${projectId}/opportunities/${opportunityId}`,
    { method: "PATCH", locale, body: json(patch) },
  );
}

export type Lifecycle = "publish" | "close";

export function setLifecycle(
  locale: Locale,
  projectId: string,
  opportunityId: string,
  action: Lifecycle,
): Promise<ManagerOpportunity> {
  return apiFetch<ManagerOpportunity>(
    `${BASE}/projects/${projectId}/opportunities/${opportunityId}/${action}`,
    { method: "POST", locale },
  );
}

export function deleteOpportunity(
  locale: Locale,
  projectId: string,
  opportunityId: string,
): Promise<ManagerOpportunity> {
  return apiFetch<ManagerOpportunity>(
    `${BASE}/projects/${projectId}/opportunities/${opportunityId}`,
    { method: "DELETE", locale },
  );
}

export function listApplicants(
  locale: Locale,
  projectId: string,
  opportunityId: string,
): Promise<ManagerApplication[]> {
  return apiFetch<ManagerApplication[]>(
    `${BASE}/projects/${projectId}/opportunities/${opportunityId}/applications`,
    { locale },
  );
}

export type Decision = "shortlist" | "decline";

export function decideApplication(
  locale: Locale,
  projectId: string,
  opportunityId: string,
  applicationId: string,
  decision: Decision,
): Promise<ManagerApplication> {
  return apiFetch<ManagerApplication>(
    `${BASE}/projects/${projectId}/opportunities/${opportunityId}` +
      `/applications/${applicationId}/${decision}`,
    { method: "POST", locale },
  );
}

/**
 * يُحوّل متقدّمًا إلى دعوةِ فريق — **والهويّةُ يشتقّها الخادم**.
 *
 * فلا `applicant_user_id` هنا ولا بريدٌ يُكتب فوقه: المديرُ يُرسل الدورَ
 * والصلاحياتِ وحدها، والقاعدةُ تُثبت أنّ المدعوَّ هو صاحبُ ذلك الطلب
 * بعينه. وإلّا صار حقلٌ في نموذجٍ بابًا لدعوة من لم يتقدّم.
 */
export function inviteApplicant(
  locale: Locale,
  projectId: string,
  opportunityId: string,
  applicationId: string,
  invite: { role: string; permissions: string[]; ttl_hours?: number | null },
): Promise<IssuedRecruitmentInvitation> {
  return apiFetch<IssuedRecruitmentInvitation>(
    `${BASE}/projects/${projectId}/opportunities/${opportunityId}` +
      `/applications/${applicationId}/invite`,
    { method: "POST", locale, body: json(invite) },
  );
}

// ═══════════════════ مفرداتٌ وصلاحيات ═══════════════════

export interface Vocabulary {
  key: string;
  label: string;
}

/** **والمفاتيحُ من الخادم، والعباراتُ من كتالوج الشاشة** — لا مفردةَ ثانية. */
export function memberRoles(locale: Locale): Promise<Vocabulary[]> {
  return apiFetch<Vocabulary[]>("/api/v1/vocab/member-roles", { locale });
}

export function projectPermissions(locale: Locale): Promise<Vocabulary[]> {
  return apiFetch<Vocabulary[]>("/api/v1/vocab/project-permissions", { locale });
}

// ═══════════════════ ما أملكه في بحث ═══════════════════

export interface ProjectAccess {
  project_id: string;
  is_owner: boolean;
  relationship: string;
  role: string | null;
  access_state: string | null;
  permissions: string[];
  can_manage_team: boolean;
  can_manage_sources: boolean;
  can_manage_data: boolean;
  can_manage_tasks: boolean;
  can_manage_submission: boolean;
}

/**
 * ما يملكه الطالبُ في هذا البحث — **إجابةُ الخادم لا حالةُ الشاشة**.
 *
 * وإخفاءُ زرٍّ بناءً عليها **تحسينُ عرضٍ لا حدُّ أمان**: كلُّ مسارٍ خلفه
 * يسأل عن صلاحيّته بنفسه. لكنّ عرضَ زرٍّ لا يعمل كذبٌ صغيرٌ يتكرّر.
 */
export function projectAccess(locale: Locale, projectId: string): Promise<ProjectAccess> {
  return apiFetch<ProjectAccess>(`/api/v1/projects/${projectId}/access`, { locale });
}

/**
 * التوقيتُ يُرسل واعيًا بمنطقته — **لا نصًّا ساذجًا**.
 *
 * فقيمةُ `datetime-local` في المتصفّح بلا منطقة (`2026-09-15T08:00`)، ولو
 * أُرسلت كما هي لَقرأها الخادمُ UTC: فيُعلن إعلانٌ قبل موعده بساعات أو
 * بعده. والتحويلُ هنا في موضعٍ واحد، فلا تفترق شاشتان فيه.
 */
export function localInputToIso(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

/** والعكسُ: قيمةٌ صالحةٌ لحقل `datetime-local` من ISO واعٍ بمنطقته. */
export function isoToLocalInput(value: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}` +
    `T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  );
}
