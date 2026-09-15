"use client";

import { useCallback, useEffect, useState } from "react";

import { AtheraApiError } from "@/lib/api";
import { getMessages, translator, type Locale } from "@/lib/i18n";
import {
  type ManagerApplication,
  type ManagerOpportunity,
  type IssuedRecruitmentInvitation,
  type OpportunityDraft,
  type ProjectAccess,
  type Vocabulary,
  createOpportunity,
  decideApplication,
  deleteOpportunity,
  inviteApplicant,
  isoToLocalInput,
  listApplicants,
  localInputToIso,
  memberRoles,
  patchOpportunity,
  projectAccess,
  projectOpportunities,
  projectPermissions,
  setLifecycle,
} from "@/lib/recruitment";

/**
 * الفرصُ البحثية لبحثٍ بعينه — **إدارةُ إعلانٍ واختيارُ متعاون** (RC-T1C).
 *
 * وهي أداةُ تعاونٍ حول البحث، **لا مرحلةً من رحلته العلمية**: لا تُحسب في
 * اكتمالٍ ولا تُفتح بوابةً ولا تدخل الخيطَ الذهبي. ولذلك تقع في قسمٍ من
 * صفحة البحث ولا تُضاف إلى المراحل التسع.
 *
 * ## ولا لغةَ توظيف
 *
 * فلا «راتب» ولا «سيرة ذاتية» ولا «عقد» ولا «تقييم مرشَّح». وهذا تعاونٌ
 * بحثيّ: من يُقبل يصير عضوًا في فريقٍ بصلاحياتٍ صريحة، لا موظَّفًا.
 *
 * ## والحالةُ النافذةُ من الخادم
 *
 * فـ«مفتوحة» ليست `status == "open"`: الإعلانُ المنشورُ الذي لم يبلغ
 * `starts_at` مجدولٌ لا مفتوح، والذي مضى `ends_at` منتهٍ. والخادمُ يحسبها
 * (`effective_status`)، وشاشةٌ تحسبها بنفسها تُخبر المديرَ بغير ما تقوله
 * القاعدةُ للمتقدّم.
 *
 * ## والرمزُ يُعرض مرّةً في الذاكرة وحدها
 *
 * لا في العنوان، ولا في `localStorage`، ولا في قياسٍ ولا سجلّ. وإعادةُ
 * التحميل تُذهبه — وذاك هو المقصود: المنصّةُ تحفظ تجزئتَه لا نصَّه، فلا
 * تستطيع إظهارَه ثانيةً ولو أرادت.
 */
const EMPTY: OpportunityDraft = {
  title: "",
  description: "",
  contributions: "",
  requirements: "",
  specialization: "",
  openings_count: 1,
  collaboration_type: "research_assistant",
  public_label: "",
  starts_at: "",
  ends_at: "",
};

function statusLabel(t: (k: string) => string, status: string): string {
  const label = t(`collaborationOpportunities.${status}`);
  return label === `collaborationOpportunities.${status}` ? status : label;
}

export function ProjectRecruitment({
  locale,
  projectId,
}: {
  locale: Locale;
  projectId: string;
}) {
  const t = translator(getMessages(locale));

  const [access, setAccess] = useState<ProjectAccess | null>(null);
  const [rows, setRows] = useState<ManagerOpportunity[]>([]);
  const [roles, setRoles] = useState<Vocabulary[]>([]);
  const [permissions, setPermissions] = useState<Vocabulary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [draft, setDraft] = useState<OpportunityDraft>(EMPTY);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<OpportunityDraft>(EMPTY);

  const [openApplicants, setOpenApplicants] = useState<string | null>(null);
  const [applicants, setApplicants] = useState<ManagerApplication[]>([]);
  const [inviteFor, setInviteFor] = useState<string | null>(null);
  const [inviteRole, setInviteRole] = useState("co_author");
  const [invitePermissions, setInvitePermissions] = useState<string[]>(["view_project"]);
  const [inviteTtl, setInviteTtl] = useState("");
  // **رمزُ الدعوة — حالُ React وحده.** لا عنوانٌ ولا تخزينٌ ولا سجلّ.
  const [issued, setIssued] = useState<IssuedRecruitmentInvitation | null>(null);
  const [copied, setCopied] = useState(false);

  const say = useCallback(
    (err: unknown) =>
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
    [locale, t],
  );

  const reload = useCallback(() => {
    projectOpportunities(locale, projectId)
      .then(setRows)
      .catch(say)
      .finally(() => setLoaded(true));
  }, [locale, projectId, say]);

  useEffect(() => {
    Promise.all([
      projectAccess(locale, projectId),
      memberRoles(locale),
      projectPermissions(locale),
    ])
      .then(([mine, roleVocab, permissionVocab]) => {
        setAccess(mine);
        setRoles(roleVocab);
        setPermissions(permissionVocab);
      })
      .catch(say);
    projectOpportunities(locale, projectId)
      .then(setRows)
      .catch(say)
      .finally(() => setLoaded(true));
  }, [locale, projectId, say]);

  const canManage = access?.can_manage_team ?? false;

  async function act(run: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await run();
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  function toPayload(value: OpportunityDraft): OpportunityDraft {
    return {
      title: value.title.trim(),
      description: value.description.trim(),
      contributions: value.contributions?.trim() || null,
      requirements: value.requirements?.trim() || null,
      specialization: value.specialization?.trim() || null,
      openings_count: value.openings_count ?? 1,
      collaboration_type: value.collaboration_type || "research_assistant",
      public_label: value.public_label?.trim() || null,
      // **التوقيتُ واعٍ بمنطقته أو لا يُرسل.** ونصٌّ ساذجٌ يُقرأ UTC،
      // فيُفتح الإعلانُ قبل موعده بساعات أو بعده.
      starts_at: localInputToIso(value.starts_at ?? ""),
      ends_at: localInputToIso(value.ends_at ?? ""),
    };
  }

  async function create() {
    await act(async () => {
      await createOpportunity(locale, projectId, toPayload(draft));
      setDraft(EMPTY);
      setCreating(false);
    });
  }

  async function saveEdit(opportunityId: string) {
    setBusy(true);
    setError(null);
    try {
      await patchOpportunity(locale, projectId, opportunityId, toPayload(editDraft));
      setEditingId(null);
      reload();
    } catch (err) {
      // **و٤٠٩ هنا ليست فشلًا مبهمًا**: وصلت طلباتٌ فجُمّدت الحقولُ
      // الجوهرية. ويُقال ذلك بعبارةٍ تُرشد، ولا تُطرح تعديلاتُ المدير
      // من الشاشة بصمت — تبقى في الحقول ليُعيد ما يجوز منها.
      if (err instanceof AtheraApiError && err.status === 409) {
        setError(t("projectRecruitment.editConflict"));
      } else {
        say(err);
      }
    } finally {
      setBusy(false);
    }
  }

  async function showApplicants(opportunityId: string) {
    if (openApplicants === opportunityId) {
      setOpenApplicants(null);
      setApplicants([]);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const list = await listApplicants(locale, projectId, opportunityId);
      setApplicants(list);
      setOpenApplicants(opportunityId);
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  /**
   * **الجوابُ هو الحقيقة — ولا تُعاد القراءة بعد الكتابة.**
   *
   * فنقطةُ القرار تردّ الصفَّ المُحدَّث كاملًا، وقراءةٌ ثانيةٌ بعدها
   * ليست تأكيدًا: هي رحلةٌ زائدةٌ إلى قاعدةٍ في إقليمٍ آخر (**وعدُّ
   * الرحلات هو زمنُ الاستجابة هنا**)، وهي كذلك **قراءةٌ قد تسبق الإثبات**.
   *
   * وهذا مقيسٌ لا مُخمَّن. سقطت رحلةُ CI عند هذه النقطة بالضبط: ردَّ
   * الخادمُ ٢٠٠ ومعه «في القائمة المختصرة»، فقرأت الشاشةُ بعده بجزءٍ من
   * الألف من الثانية فعادت «قيد النظر». والسببُ في ترتيب FastAPI نفسِه
   * (`routing.py`)::
   *
   *     async with AsyncExitStack() as request_stack:   # التبعيّةُ هنا
   *         ...
   *         await response(scope, receive, send)        # ← يُرسَل الردّ
   *     # ← تُفكّ الحزمةُ الآن، وهنا **تُثبَّت المعاملة**
   *
   * فالردُّ يبلغ العميلَ قبل `COMMIT`. والنافذةُ دون المليّ ثانية، فلا
   * تُرى على جهازٍ سريع وتُرى على مُشغِّل CI — وهو أسوأُ أنواع العطب:
   * يعمل عندك ويكذب على المستعمِل.
   *
   * **فلا يُبنى شيءٌ على قراءةٍ تتبع كتابةً.** والصفُّ الذي ردّه الخادمُ
   * يُدمج في موضعه، ويبقى ما عداه. وهذا حدٌّ مُعلَنٌ في نموذج التهديد.
   */
  function merge(updated: ManagerApplication) {
    setApplicants((prev) =>
      prev.map((row) =>
        row.application_id === updated.application_id ? updated : row,
      ),
    );
  }

  async function decide(
    opportunityId: string,
    applicationId: string,
    decision: "shortlist" | "decline",
  ) {
    setBusy(true);
    setError(null);
    try {
      merge(await decideApplication(
        locale, projectId, opportunityId, applicationId, decision));
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  async function sendInvite(opportunityId: string, applicationId: string) {
    setBusy(true);
    setError(null);
    setIssued(null);
    setCopied(false);
    try {
      const ttl = inviteTtl.trim() ? Number(inviteTtl.trim()) : null;
      const result = await inviteApplicant(locale, projectId, opportunityId, applicationId, {
        role: inviteRole,
        permissions: invitePermissions,
        ttl_hours: Number.isFinite(ttl as number) ? (ttl as number) : null,
      });
      setIssued(result);
      setInviteFor(null);
      // **وحالُ الطلب تُشتقّ من جواب الدعوة نفسِه** — لا بقراءةٍ ثانية.
      // والدعوةُ المرتبطةُ تُعرض بحالها كما ردّها الخادم.
      setApplicants((prev) =>
        prev.map((row) =>
          row.application_id === applicationId
            ? {
                ...row,
                status: result.application_status,
                invitation: {
                  invitation_id: result.invitation_id,
                  state: result.invitation_state,
                  usable: result.invitation_state === "invited",
                  expires_at: result.expires_at,
                  membership_created: false,
                },
              }
            : row,
        ),
      );
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  function field(
    label: string,
    value: string,
    onChange: (next: string) => void,
    options: { area?: boolean; type?: string; hint?: string; id: string } = { id: "" },
  ) {
    return (
      <label htmlFor={options.id} style={{ display: "block", marginBlockStart: 8 }}>
        {label}
        {options.area ? (
          <textarea
            id={options.id}
            rows={3}
            style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
            value={value}
            onChange={(event) => onChange(event.target.value)}
          />
        ) : (
          <input
            id={options.id}
            type={options.type ?? "text"}
            style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
            value={value}
            onChange={(event) => onChange(event.target.value)}
          />
        )}
        {options.hint ? <span className="metric-label">{options.hint}</span> : null}
      </label>
    );
  }

  function form(
    value: OpportunityDraft,
    setValue: (next: OpportunityDraft) => void,
    prefix: string,
  ) {
    return (
      <>
        {field(
          t("projectRecruitment.titleLabel"),
          value.title,
          (next) => setValue({ ...value, title: next }),
          { id: `${prefix}-title` },
        )}
        {field(
          t("projectRecruitment.descriptionLabel"),
          value.description,
          (next) => setValue({ ...value, description: next }),
          { area: true, id: `${prefix}-description` },
        )}
        {field(
          t("projectRecruitment.contributionsLabel"),
          value.contributions ?? "",
          (next) => setValue({ ...value, contributions: next }),
          { area: true, id: `${prefix}-contributions` },
        )}
        {field(
          t("projectRecruitment.requirementsLabel"),
          value.requirements ?? "",
          (next) => setValue({ ...value, requirements: next }),
          { area: true, id: `${prefix}-requirements` },
        )}
        {field(
          t("projectRecruitment.specializationLabel"),
          value.specialization ?? "",
          (next) => setValue({ ...value, specialization: next }),
          { id: `${prefix}-specialization` },
        )}
        {field(
          t("projectRecruitment.openingsLabel"),
          String(value.openings_count ?? 1),
          (next) => setValue({ ...value, openings_count: Math.max(1, Number(next) || 1) }),
          { type: "number", id: `${prefix}-openings` },
        )}
        {field(
          t("projectRecruitment.publicLabelLabel"),
          value.public_label ?? "",
          (next) => setValue({ ...value, public_label: next }),
          { hint: t("projectRecruitment.publicLabelHint"), id: `${prefix}-label` },
        )}
        {field(
          t("projectRecruitment.startsAtLabel"),
          value.starts_at ?? "",
          (next) => setValue({ ...value, starts_at: next }),
          { type: "datetime-local", id: `${prefix}-starts` },
        )}
        {field(
          t("projectRecruitment.endsAtLabel"),
          value.ends_at ?? "",
          (next) => setValue({ ...value, ends_at: next }),
          { type: "datetime-local", id: `${prefix}-ends` },
        )}
      </>
    );
  }

  return (
    <section aria-label={t("projectRecruitment.title")} data-testid="project-recruitment">
      <h2>{t("projectRecruitment.title")}</h2>
      <p className="provenance-note">{t("projectRecruitment.note")}</p>
      {error ? <p className="error">{error}</p> : null}

      {/* **الإدارةُ تحتاج `manage_team`** — ويُقال ذلك بدل عرضِ أزرارٍ تُردّ. */}
      {access && !canManage ? (
        <p style={{ color: "var(--muted)" }} data-testid="recruitment-needs-manage-team">
          {t("projectRecruitment.needsManageTeam")}
        </p>
      ) : null}

      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("collaborationOpportunities.loading")}</p>
      ) : rows.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("projectRecruitment.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((row) => (
          <article
            className="card"
            key={row.opportunity_id}
            data-testid={`opportunity-${row.opportunity_id}`}
            style={row.deleted_at ? { opacity: 0.6 } : undefined}
          >
            <div
              style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
            >
              <strong>{row.title}</strong>
              {/* **الحالةُ النافذةُ هي المعروضة**، والمخزَّنةُ بجوارها
                  للمدير — فيرى «منشور» و«مجدول» معًا ولا يخلطهما. */}
              <span className="chip chip-stage" data-testid={`opportunity-status-${row.opportunity_id}`}>
                {statusLabel(t, row.effective_status)}
              </span>
            </div>
            <p className="metric-label">
              {t("projectRecruitment.storedVersus")}: {statusLabel(t, row.stored_status)} ·{" "}
              {t("collaborationOpportunities.openings")}: {row.openings_count} ·{" "}
              {t("projectRecruitment.applicantsCount")}: {row.applications_count}
            </p>
            {row.public_label ? <p className="metric-label">{row.public_label}</p> : null}
            <p style={{ marginBlock: 6 }}>{row.description}</p>

            {canManage ? (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 8 }}>
                {row.effective_status === "draft" || row.effective_status === "closed" ? (
                  <button
                    type="button"
                    className="chip chip-stage"
                    disabled={busy}
                    data-testid={`opportunity-publish-${row.opportunity_id}`}
                    onClick={() => void act(() => setLifecycle(locale, projectId, row.opportunity_id, "publish"))}
                  >
                    {t("projectRecruitment.publish")}
                  </button>
                ) : null}
                {row.effective_status === "open" || row.effective_status === "scheduled" ? (
                  <button
                    type="button"
                    className="chip chip-muted"
                    disabled={busy}
                    data-testid={`opportunity-close-${row.opportunity_id}`}
                    onClick={() => void act(() => setLifecycle(locale, projectId, row.opportunity_id, "close"))}
                  >
                    {t("projectRecruitment.close")}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="chip chip-muted"
                  disabled={busy}
                  data-testid={`opportunity-edit-${row.opportunity_id}`}
                  onClick={() => {
                    setEditingId(editingId === row.opportunity_id ? null : row.opportunity_id);
                    setEditDraft({
                      title: row.title,
                      description: row.description,
                      contributions: row.contributions ?? "",
                      requirements: row.requirements ?? "",
                      specialization: row.specialization ?? "",
                      openings_count: row.openings_count,
                      collaboration_type: row.collaboration_type,
                      public_label: row.public_label ?? "",
                      starts_at: isoToLocalInput(row.starts_at),
                      ends_at: isoToLocalInput(row.ends_at),
                    });
                  }}
                >
                  {t("projectRecruitment.edit")}
                </button>
                <button
                  type="button"
                  className="chip chip-muted"
                  disabled={busy}
                  data-testid={`opportunity-applicants-${row.opportunity_id}`}
                  onClick={() => void showApplicants(row.opportunity_id)}
                >
                  {openApplicants === row.opportunity_id
                    ? t("projectRecruitment.hideApplicants")
                    : t("projectRecruitment.applicants")}
                </button>
                {!row.deleted_at ? (
                  <button
                    type="button"
                    className="chip chip-muted"
                    disabled={busy}
                    data-testid={`opportunity-delete-${row.opportunity_id}`}
                    onClick={() => void act(() => deleteOpportunity(locale, projectId, row.opportunity_id))}
                  >
                    {t("projectRecruitment.softDelete")}
                  </button>
                ) : null}
              </div>
            ) : null}

            {editingId === row.opportunity_id ? (
              <div style={{ marginBlockStart: 10 }} data-testid={`opportunity-editor-${row.opportunity_id}`}>
                <p className="provenance-note">{t("projectRecruitment.lockedNote")}</p>
                {form(editDraft, setEditDraft, `edit-${row.opportunity_id}`)}
                <button
                  type="button"
                  style={{ marginBlockStart: 8 }}
                  disabled={busy}
                  data-testid={`opportunity-save-${row.opportunity_id}`}
                  onClick={() => void saveEdit(row.opportunity_id)}
                >
                  {t("projectRecruitment.save")}
                </button>
                <button
                  type="button"
                  className="chip chip-muted"
                  style={{ marginInlineStart: 8 }}
                  onClick={() => setEditingId(null)}
                >
                  {t("projectRecruitment.cancel")}
                </button>
              </div>
            ) : null}

            {/* ══ المتقدّمون — **وما يُعرض هو ما يردّه الخادم** ══
                لا بريدٌ ولا مستأجرٌ ولا معرّفُ حساب: الإسقاطُ الآمن اسمٌ
                معروضٌ ورسالةٌ وحالٌ ووقتٌ، وحالُ دعوةٍ إن وُجدت. */}
            {openApplicants === row.opportunity_id ? (
              <div style={{ marginBlockStart: 10 }} data-testid={`applicants-${row.opportunity_id}`}>
                <h3>{t("projectRecruitment.applicants")}</h3>
                {applicants.length === 0 ? (
                  <p style={{ color: "var(--muted)" }}>{t("projectRecruitment.noApplicants")}</p>
                ) : null}
                <div style={{ display: "grid", gap: 8 }}>
                  {applicants.map((application) => (
                    <article
                      className="card"
                      key={application.application_id}
                      data-testid={`applicant-${application.application_id}`}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 12,
                          flexWrap: "wrap",
                        }}
                      >
                        <strong>{application.display_name}</strong>
                        <span
                          className="metric-label"
                          data-testid={`applicant-status-${application.application_id}`}
                        >
                          {t(`recruitment.applicationStatus.${application.status}`)}
                        </span>
                      </div>
                      {application.message ? (
                        <p style={{ marginBlock: 4 }}>{application.message}</p>
                      ) : null}
                      <p className="metric-label">
                        {t("collaborationOpportunities.submittedAt")}:{" "}
                        {new Date(application.submitted_at).toLocaleString(locale)}
                      </p>
                      {application.invitation ? (
                        <p className="metric-label">
                          {t(`recruitment.invitationState.${application.invitation.state}`)}
                          {" · "}
                          {application.invitation.usable
                            ? t("collaborationOpportunities.invitationUsable")
                            : t("collaborationOpportunities.invitationUnusable")}
                        </p>
                      ) : null}

                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 8 }}>
                        {application.status === "pending" ? (
                          <button
                            type="button"
                            className="chip chip-stage"
                            disabled={busy}
                            data-testid={`applicant-shortlist-${application.application_id}`}
                            onClick={() =>
                              void decide(row.opportunity_id, application.application_id, "shortlist")
                            }
                          >
                            {t("projectRecruitment.shortlist")}
                          </button>
                        ) : null}
                        {application.status === "pending" || application.status === "shortlisted" ? (
                          <>
                            <button
                              type="button"
                              className="chip chip-muted"
                              disabled={busy}
                              data-testid={`applicant-decline-${application.application_id}`}
                              onClick={() =>
                                void decide(row.opportunity_id, application.application_id, "decline")
                              }
                            >
                              {t("projectRecruitment.decline")}
                            </button>
                            <button
                              type="button"
                              className="chip chip-stage"
                              disabled={busy}
                              data-testid={`applicant-invite-${application.application_id}`}
                              onClick={() =>
                                setInviteFor(
                                  inviteFor === application.application_id
                                    ? null
                                    : application.application_id,
                                )
                              }
                            >
                              {t("projectRecruitment.invite")}
                            </button>
                          </>
                        ) : null}
                      </div>

                      {/* ══ نموذجُ الدعوة — **دورٌ وصلاحياتٌ صريحة** ══
                          ولا هويّةَ فيه: لا معرّفُ حساب، ولا مستأجر، ولا
                          بريدٌ يُكتب فوقه. والخادمُ يشتقّ المدعوَّ من
                          الطلب نفسِه، فلا يصير حقلٌ بابًا لدعوة من لم
                          يتقدّم. */}
                      {inviteFor === application.application_id ? (
                        <div
                          style={{ marginBlockStart: 10 }}
                          data-testid={`invite-form-${application.application_id}`}
                        >
                          <strong>{t("projectRecruitment.inviteTitle")}</strong>
                          <p className="provenance-note">{t("projectRecruitment.inviteNote")}</p>
                          <label
                            htmlFor={`invite-role-${application.application_id}`}
                            style={{ display: "block", marginBlockStart: 8 }}
                          >
                            {t("projectRecruitment.roleLabel")}
                            <select
                              id={`invite-role-${application.application_id}`}
                              style={{ display: "block", marginBlockStart: 4 }}
                              value={inviteRole}
                              data-testid={`invite-role-${application.application_id}`}
                              onChange={(event) => setInviteRole(event.target.value)}
                            >
                              {roles.map((item) => (
                                <option key={item.key} value={item.key}>
                                  {item.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <fieldset style={{ marginBlockStart: 8 }}>
                            <legend className="metric-label">
                              {t("projectRecruitment.permissionsLabel")}
                            </legend>
                            {permissions.map((item) => (
                              <label key={item.key} style={{ display: "block", marginBlockStart: 4 }}>
                                <input
                                  type="checkbox"
                                  data-testid={`invite-permission-${item.key}`}
                                  checked={invitePermissions.includes(item.key)}
                                  onChange={(event) =>
                                    setInvitePermissions((prev) =>
                                      event.target.checked
                                        ? [...prev, item.key]
                                        : prev.filter((key) => key !== item.key),
                                    )
                                  }
                                />{" "}
                                {item.label}
                              </label>
                            ))}
                          </fieldset>
                          <label
                            htmlFor={`invite-ttl-${application.application_id}`}
                            style={{ display: "block", marginBlockStart: 8 }}
                          >
                            {t("projectRecruitment.ttlLabel")}
                            <input
                              id={`invite-ttl-${application.application_id}`}
                              type="number"
                              min={1}
                              style={{ display: "block", marginBlockStart: 4 }}
                              value={inviteTtl}
                              onChange={(event) => setInviteTtl(event.target.value)}
                            />
                            <span className="metric-label">{t("projectRecruitment.ttlHint")}</span>
                          </label>
                          <button
                            type="button"
                            style={{ marginBlockStart: 8 }}
                            disabled={busy || invitePermissions.length === 0}
                            data-testid={`invite-submit-${application.application_id}`}
                            onClick={() =>
                              void sendInvite(row.opportunity_id, application.application_id)
                            }
                          >
                            {t("projectRecruitment.sendInvite")}
                          </button>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </article>
        ))}
      </div>

      {/* ══ الرمزُ مرّةً واحدة ══ */}
      {issued ? (
        <article className="card" style={{ marginBlockStart: 12 }} data-testid="recruitment-token">
          <strong>{t("projectRecruitment.tokenIssued")}</strong>
          <p className="provenance-note">{t("projectRecruitment.tokenOnce")}</p>
          <p className="provenance-note">{t("projectRecruitment.tokenCannotRecover")}</p>
          <p className="metric-label">
            {t("projectRecruitment.tokenRecipient")} ·{" "}
            {t(`recruitment.invitationState.${issued.invitation_state}`)}
          </p>
          {/* **ولا يُقصّ النصُّ المنسوخ.** ورمزٌ طويلٌ يُلَفّ ولا يدفع
              الصفحةَ أفقيًّا على ٣٧٥px. */}
          <code
            data-testid="recruitment-token-value"
            style={{ overflowWrap: "anywhere", display: "block", marginBlock: 6 }}
          >
            {issued.token}
          </code>
          <button
            type="button"
            className="chip chip-muted"
            onClick={() => {
              void navigator.clipboard?.writeText(issued.token).then(() => setCopied(true));
            }}
          >
            {copied ? t("projectRecruitment.copied") : t("projectRecruitment.copy")}
          </button>
          <button
            type="button"
            className="chip chip-muted"
            style={{ marginInlineStart: 8 }}
            onClick={() => setIssued(null)}
          >
            {t("projectRecruitment.dismissToken")}
          </button>
        </article>
      ) : null}

      {/* ══ إعلانٌ جديد ══ */}
      {canManage ? (
        <article className="card" style={{ marginBlockStart: 12 }}>
          <strong>{t("projectRecruitment.newDraft")}</strong>
          {creating ? (
            <>
              {form(draft, setDraft, "new")}
              <button
                type="button"
                style={{ marginBlockStart: 8 }}
                disabled={busy || draft.title.trim().length < 3 || draft.description.trim().length < 10}
                data-testid="opportunity-create-submit"
                onClick={() => void create()}
              >
                {busy ? t("projectRecruitment.creating") : t("projectRecruitment.create")}
              </button>
              <button
                type="button"
                className="chip chip-muted"
                style={{ marginInlineStart: 8 }}
                onClick={() => setCreating(false)}
              >
                {t("projectRecruitment.cancel")}
              </button>
            </>
          ) : (
            <p style={{ marginBlockStart: 8 }}>
              <button
                type="button"
                className="chip chip-stage"
                data-testid="opportunity-new"
                onClick={() => setCreating(true)}
              >
                {t("projectRecruitment.newDraft")}
              </button>
            </p>
          )}
        </article>
      ) : null}
    </section>
  );
}
