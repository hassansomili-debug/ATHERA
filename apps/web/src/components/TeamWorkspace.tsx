"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad, type Commit } from "@/lib/useDeferredLoad";
import { getMessages, translator, type Locale } from "@/lib/i18n";
import { InvitationAcceptPanel } from "@/components/InvitationAcceptPanel";
import { projectAccess, type ProjectAccess } from "@/lib/recruitment";

/**
 * فريقُ البحث وقراراته — **محرّكٌ واحدٌ لشاشتين** (§12، §24، RC-T1C).
 *
 * الشاشةُ العامّة `/team` تختار البحثَ من قائمة، وقسمُ البحث
 * `?section=team` يعمل على بحثٍ مُثبَّت بلا مُنتقٍ ثانٍ. **والمنطقُ واحد**:
 * نسختان تفترقان بأوّل تعديل، فتصير إحداهما تعرض الموافقةَ عن غيرِ صاحبها
 * أو تبتلع دعوةً تقولها الأخرى.
 *
 * **وأربعةُ تمييزاتٍ تُعرض منفصلةً لأنها منفصلةٌ في القاعدة:**
 *
 *   الدورُ في الفريق  ليس صلاحية
 *   الصلاحيةُ         ليست مساهمةَ CRediT
 *   مساهمةُ CRediT    ليست تأليفًا
 *   العضويةُ          ليست موافقةً على التأليف
 *
 * وشاشةٌ تعرض «عضو» وحدها تجعل القارئ يفترض الأربعة معًا، فيقرأ اسمًا في
 * قائمة الفريق على أنه مؤلفٌ وافق — وهو ما لا تقوله البيانات.
 *
 * وأدوار CRediT تُختار يدويًّا ولا تُقترح: اقتراحها من نشاط أحد في المنصة
 * يحوّل «من فعل ماذا» من إقرار إلى استنتاج، وهو ما يصنع نزاعات التأليف.
 *
 * **ولا زرَّ «وافق الجميع» هنا، ولا زرَّ «سجّل موافقته».** الموافقةُ فعلُ
 * صاحبها: من يفتح الشاشة يرى زرَّ موافقةٍ **لنفسه وحده**، ويرى عن غيره
 * حالًا يقرؤها ولا يكتبها.
 *
 * ## والصلاحياتُ تُحرَّر صريحةً
 *
 * فكانت تُعرض ولا تُعدَّل، والخادمُ يقبل تعديلَها منذ RC-T1A. فمديرُ
 * الفريق يمنح `manage_sources` **بلا أن يمسّ الدور** — وذاك هو الفرقُ
 * الذي تقوم عليه هذه الطبقة، ولا يُرى إلّا في شاشةٍ تفصلهما.
 *
 * ## وما يُعرض مرهونٌ بما يملكه الطالب
 *
 * ويُقرأ من `/projects/{id}/access` — إجابةُ خادم لا حالُ شاشة. وإخفاءُ
 * زرٍّ **تحسينُ عرضٍ لا حدُّ أمان**: كلُّ مسارٍ خلفه يسأل عن صلاحيّته
 * بنفسه. لكنّ زرًّا يُعرض ثمّ يُردّ يُعلّم الباحثَ أنّ المنصّةَ تُخطئ.
 */
interface Project {
  id: string;
  working_title: string;
}

interface Vocabulary {
  key: string;
  label: string;
}

interface Member {
  id: string;
  display_name: string;
  user_id: string | null;
  is_account_linked: boolean;
  invited_email: string | null;
  role: string;
  role_label: string;
  access_state: string;
  access_label: string;
  permissions: string[];
  permission_labels: string[];
  credit_roles: string[];
  credit_labels: string[];
  is_author: boolean;
  author_position: number | null;
  consent_state: string;
  consent_label: string;
  consent_method: string | null;
  consent_method_label: string | null;
  consent_recorded_at: string | null;
  consent_recorded_by: string | null;
  consent_needs_recollection: boolean;
}

interface Invitation {
  id: string;
  invited_email: string;
  invited_display_name: string;
  proposed_role_label: string;
  proposed_permissions: string[];
  state: string;
  state_label: string;
  expires_at: string;
  token?: string;
}

interface PendingAction {
  kind: string;
  kind_label: string;
  subject_id: string;
  statement: string;
  is_mine: boolean;
}

interface Decision {
  id: string;
  decision_kind: string;
  kind_label: string;
  statement: string;
  gate: string | null;
  decided_at: string | null;
  supersedes_id: string | null;
  is_superseded: boolean;
  is_current: boolean;
  superseded_by_id: string | null;
}

interface MemberEvent {
  id: string;
  member_id: string | null;
  invitation_id: string | null;
  event_kind: string;
  occurred_at: string;
  note_ar: string | null;
}

export function TeamWorkspace({
  locale,
  fixedProjectId,
}: {
  locale: Locale;
  /** بحثٌ مُثبَّتٌ من مساره — فلا مُنتقٍ ثانٍ داخل صفحة البحث. */
  fixedProjectId?: string;
}) {
  const t = translator(getMessages(locale));
  const fixedProject = Boolean(fixedProjectId);

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>(fixedProjectId ?? "");
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [inbox, setInbox] = useState<PendingAction[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [events, setEvents] = useState<MemberEvent[]>([]);
  const [access, setAccess] = useState<ProjectAccess | null>(null);
  const [creditVocab, setCreditVocab] = useState<Vocabulary[]>([]);
  const [roleVocab, setRoleVocab] = useState<Vocabulary[]>([]);
  const [permissionVocab, setPermissionVocab] = useState<Vocabulary[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("co_author");
  const [credit, setCredit] = useState<string[]>([]);
  // يُعرض مرّةً واحدة بعد الدعوة — والخادم لا يعيده في أيّ قراءةٍ بعدها.
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  // تحريرُ صلاحيات عضوٍ واحد — **مسوّدةٌ محلّية حتى تُحفظ**.
  const [editing, setEditing] = useState<string | null>(null);
  const [draftPermissions, setDraftPermissions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // **رايتان لا واحدة، لأنهما سؤالان مختلفان**: هل وصلت قائمة أبحاثه؟ وهل
  // وصل فريق البحث المختار؟ ودمجهما كان يُنتج أسوأ الحالين: باحثٌ لا بحث
  // له يقرأ «لا مؤلفين مسجّلين» و«لا قرارات» — وهما دعويان عن بحثٍ غير
  // موجود أصلًا، والصواب أن يُقال له: ابدأ ببحث.
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const say = useCallback(
    (err: unknown) =>
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
    [locale, t],
  );

  // سلسلةُ وعدٍ لا `await` في تأثير — `react-hooks/set-state-in-effect`.
  useEffect(() => {
    const catalogs = Promise.all([
      apiFetch<Vocabulary[]>("/api/v1/vocab/credit-roles", { locale }),
      apiFetch<Vocabulary[]>("/api/v1/vocab/member-roles", { locale }),
      // **ومفردةُ الصلاحيات من الخادم** — ولا تُكرَّر في React: مفردتان
      // تفترقان بأوّل صلاحيةٍ تُضاف، فتعرض الشاشةُ ثمانيةً والقاعدةُ تسع.
      apiFetch<Vocabulary[]>("/api/v1/vocab/project-permissions", { locale }),
    ]);
    if (fixedProject) {
      catalogs
        .then(([creditRoles, memberRoles, permissions]) => {
          setCreditVocab(creditRoles);
          setRoleVocab(memberRoles);
          setPermissionVocab(permissions);
        })
        .catch(say)
        .finally(() => setProjectsLoaded(true));
      return;
    }
    Promise.all([apiFetch<Project[]>("/api/v1/portfolio/projects", { locale }), catalogs])
      .then(([list, [creditRoles, memberRoles, permissions]]) => {
        setProjects(list);
        setCreditVocab(creditRoles);
        setRoleVocab(memberRoles);
        setPermissionVocab(permissions);
        if (list.length > 0) setProjectId(list[0]!.id);
      })
      .catch(say)
      .finally(() => setProjectsLoaded(true));
  }, [fixedProject, locale, say]);

  const load = useCallback(async (commit: Commit) => {
    if (!projectId) return;
    // قبل أوّل `await`: لجيله بالبناء، إذ لم يبدأ جيلٌ بعده.
    setError(null);
    try {
      const [people, log, pending, mine] = await Promise.all([
        apiFetch<Member[]>(`/api/v1/projects/${projectId}/members`, { locale }),
        apiFetch<Decision[]>(`/api/v1/projects/${projectId}/decisions`, { locale }),
        apiFetch<PendingAction[]>(`/api/v1/projects/${projectId}/decisions/inbox`, {
          locale,
        }),
        projectAccess(locale, projectId),
      ]);
      commit(() => {
        setMembers(people);
        setDecisions(log);
        setInbox(pending);
        setAccess(mine);
      });
      // الدعواتُ تلزمها إدارةُ فريق؛ وغيابها ليس فشلًا يُعرض بحمرة.
      // **والفرعُ الداخلي يُبوَّب كغيره** — وهو من أكثر ما يُنسى.
      try {
        const invited = await apiFetch<Invitation[]>(
          `/api/v1/projects/${projectId}/invitations`, { locale },
        );
        commit(() => setInvitations(invited));
      } catch {
        commit(() => setInvitations([]));
      }
      // والسجلُّ يقرؤه كلُّ عضوٍ له اطّلاع — لا يحتاج إدارةَ فريق.
      try {
        const trail = await apiFetch<MemberEvent[]>(
          `/api/v1/projects/${projectId}/member-events`, { locale },
        );
        commit(() => setEvents(trail));
      } catch {
        commit(() => setEvents([]));
      }
    } catch (err) {
      const message = err instanceof AtheraApiError
        ? err.localized(locale) : t("common.loadFailed");
      commit(() => setError(message));
    } finally {
      commit(() => setLoaded(true));
    }
  }, [locale, projectId, t]);

  const refresh = useDeferredLoad(load);

  async function act(run: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await run();
      await refresh();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  async function addMember() {
    await act(async () => {
      await apiFetch(`/api/v1/projects/${projectId}/members`, {
        method: "POST",
        locale,
        body: JSON.stringify({ display_name: name, role, credit_roles: credit }),
      });
      setName("");
      setCredit([]);
    });
  }

  async function invite() {
    setBusy(true);
    setError(null);
    setIssuedToken(null);
    try {
      const created = await apiFetch<Invitation>(
        `/api/v1/projects/${projectId}/invitations`,
        {
          method: "POST",
          locale,
          body: JSON.stringify({ email, display_name: name, role }),
        },
      );
      setIssuedToken(created.token ?? null);
      setEmail("");
      setName("");
      await refresh();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(invitationId: string) {
    await act(() =>
      apiFetch(`/api/v1/projects/${projectId}/invitations/${invitationId}`, {
        method: "DELETE",
        locale,
      }),
    );
  }

  /** **الصلاحيةُ صفٌّ يُكتب — والدورُ لا يُمسّ معها.** */
  async function savePermissions(memberId: string) {
    await act(async () => {
      await apiFetch(`/api/v1/projects/${projectId}/members/${memberId}/permissions`, {
        method: "PUT",
        locale,
        body: JSON.stringify({ permissions: draftPermissions }),
      });
      setEditing(null);
      setDraftPermissions([]);
    });
  }

  async function changeRole(memberId: string, next: string) {
    await act(() =>
      apiFetch(`/api/v1/projects/${projectId}/members/${memberId}/role`, {
        method: "PATCH",
        locale,
        body: JSON.stringify({ role: next }),
      }),
    );
  }

  async function changeAccess(memberId: string, next: string) {
    await act(() =>
      apiFetch(`/api/v1/projects/${projectId}/members/${memberId}/access`, {
        method: "PATCH",
        locale,
        body: JSON.stringify({ access_state: next }),
      }),
    );
  }

  /** **موافقتُك أنت.** ولا يقبل هذا المسار معرِّف عضوٍ سواك. */
  async function consentAsMyself(granted: boolean) {
    await act(() =>
      apiFetch(`/api/v1/projects/${projectId}/members/me/consent`, {
        method: "POST",
        locale,
        body: JSON.stringify({ granted }),
      }),
    );
  }

  const awaitingMe = inbox.some((item) => item.is_mine && item.kind === "author_consent");
  const canManageTeam = access?.can_manage_team ?? false;
  const eventLabel = (kind: string) => {
    const label = t(`team.events.${kind}`);
    return label === `team.events.${kind}` ? kind : label;
  };

  return (
    <>
      {error ? <p className="error">{error}</p> : null}

      {/* **مُنتقي البحث للشاشة العامّة وحدها.** وداخل صفحة البحث يكون
          البحثُ معلومًا من مساره، ومُنتقٍ ثانٍ فيها يسمح بتغييرٍ صامتٍ
          للسياق تحت عنوانٍ يقول بحثًا آخر. */}
      {!fixedProject ? (
        <label style={{ display: "block", marginBlockEnd: 12 }}>
          {t("team.project")}
          <select
            style={{ marginInlineStart: 8 }}
            value={projectId}
            data-testid="team-project-picker"
            onChange={(event) => setProjectId(event.target.value)}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.working_title}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {/* لا بحث ⇒ لا فريق ولا قرارات: تُقال العلّة مرّة، ولا تُقال مرّتين
          بصيغةٍ توهم أن البحث قائمٌ وفريقه خالٍ. */}
      {!fixedProject && projectsLoaded && projects.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>{t("team.noProject")}</p>
      ) : null}

      {/* ══ وصلتُك بهذا البحث وما تملكه فيه — **من الخادم** ══ */}
      {access ? (
        <article className="card" data-testid="team-my-access">
          <div className="metric-label">{t("team.myRelationship")}</div>
          <p style={{ marginBlock: 4 }}>
            <span className="chip chip-stage">
              {access.is_owner ? t("team.relationshipOwner") : t("team.relationshipCollaborator")}
            </span>
          </p>
          <p className="metric-label">
            {t("team.myPermissions")}:{" "}
            {access.permissions
              .map((key) => permissionVocab.find((item) => item.key === key)?.label ?? key)
              .join("، ") || t("team.noPermissions")}
          </p>
          {!canManageTeam ? (
            <p className="provenance-note">{t("team.needsManageTeam")}</p>
          ) : null}
        </article>
      ) : null}

      {/* ══ ما يحتاج فعلًا الآن — **قائمةٌ غيرُ السجلّ التاريخي** ══
          وخلطُهما يجعل الفريق يقرأ سطرًا لا يعرف أينتظره أم انتهى. */}
      <h2>{t("team.whatAwaitsMe")}</h2>
      <p className="provenance-note">{t("team.inboxNote")}</p>
      {!projectsLoaded || (projectId && !loaded) ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : projectId && inbox.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("team.emptyInbox")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {inbox.map((item) => (
          <article className="card" key={`${item.kind}-${item.subject_id}`}>
            <div
              style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
            >
              <strong>{item.kind_label}</strong>
              <span className="metric-label">
                {item.is_mine ? t("team.waitsOnYou") : t("team.waitsOnSomeoneElse")}
              </span>
            </div>
            <p style={{ marginBlock: 4 }}>{item.statement}</p>
          </article>
        ))}
      </div>
      {/* **ولا محرّكَ مهامٍّ ثانٍ هنا.** المهامُّ الحقيقيةُ في صفحتها،
          فيُفتح الأصلُ ولا تُقلَّد شاشةٌ بنِسَبِ إنجازٍ مخترعة. */}
      {projectId ? (
        <p style={{ marginBlockStart: 8 }}>
          <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/tasks`}>
            {t("team.openTasks")}
          </Link>
        </p>
      ) : null}

      {/* **زرُّ الموافقة لصاحبها وحده.** ولا يظهر عن أحدٍ آخر أبدًا. */}
      {awaitingMe ? (
        <article className="card" style={{ marginBlockStart: 12 }}>
          <strong>{t("team.yourConsent")}</strong>
          <p className="provenance-note">{t("team.yourConsentNote")}</p>
          <button type="button" disabled={busy} onClick={() => void consentAsMyself(true)}>
            {t("team.consentGrant")}
          </button>
          <button
            type="button"
            style={{ marginInlineStart: 8 }}
            disabled={busy}
            onClick={() => void consentAsMyself(false)}
          >
            {t("team.consentDecline")}
          </button>
        </article>
      ) : null}

      <h2>{t("team.members")}</h2>
      <p className="provenance-note">{t("team.roleIsNotPermission")}</p>
      {!projectsLoaded || (projectId && !loaded) ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : projectId && members.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("team.emptyMembers")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {members.map((member) => (
          <article
            className="card"
            key={member.id}
            data-testid={`team-member-${member.id}`}
            style={member.access_state === "active" ? undefined : { opacity: 0.6 }}
          >
            <div
              style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
            >
              <strong>{member.display_name}</strong>
              <span className="metric-label">
                {member.role_label} · {member.access_label}
              </span>
            </div>

            {/* **مربوطٌ بحساب أو لا** — والفرق ليس تفصيلًا: صفٌّ بلا حساب
                لا يدخل، ولا يوافق، ولا يُنسب إليه فعل في المنصّة. */}
            <p className="metric-label">
              {member.is_account_linked ? t("team.accountLinked") : t("team.nameOnly")}
              {member.invited_email ? ` · ${member.invited_email}` : ""}
            </p>

            <p className="metric-label" data-testid={`team-member-permissions-${member.id}`}>
              {t("team.permissions")}:{" "}
              {member.permission_labels.join("، ") || t("team.noPermissions")}
            </p>
            <p className="metric-label">
              {t("team.creditRoles")}: {member.credit_labels.join("، ") || t("common.none")}
            </p>

            {/* ── التأليفُ والموافقة: سطرٌ مستقلٌّ عن العضوية ── */}
            <p className="metric-label">
              {member.is_author
                ? `${t("team.declaredAuthor")}${
                    member.author_position ? ` · ${member.author_position}` : ""
                  }`
                : t("team.notAnAuthor")}
            </p>
            {member.consent_needs_recollection ? (
              <p className="error">{t("team.consentUnverified")}</p>
            ) : (
              <p className={member.consent_state === "granted" ? "badge-ok" : "metric-label"}>
                {t("team.consent")}: {member.consent_label}
                {member.consent_method_label ? ` · ${member.consent_method_label}` : ""}
              </p>
            )}

            {/* ══ إدارةُ العضو — **لمن يحمل `manage_team` وحده** ══ */}
            {canManageTeam ? (
              <div style={{ marginBlockStart: 10, display: "grid", gap: 8 }}>
                <label className="metric-label">
                  {t("team.changeRole")}
                  <select
                    style={{ marginInlineStart: 8 }}
                    value={member.role}
                    disabled={busy}
                    data-testid={`team-role-${member.id}`}
                    onChange={(event) => void changeRole(member.id, event.target.value)}
                  >
                    {roleVocab.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>

                {editing === member.id ? (
                  <fieldset data-testid={`team-permission-editor-${member.id}`}>
                    <legend className="metric-label">{t("team.permissions")}</legend>
                    {permissionVocab.map((item) => (
                      <label
                        key={item.key}
                        style={{ display: "block", marginBlockStart: 4 }}
                      >
                        <input
                          type="checkbox"
                          data-testid={`team-permission-${member.id}-${item.key}`}
                          checked={draftPermissions.includes(item.key)}
                          onChange={(event) =>
                            setDraftPermissions((prev) =>
                              event.target.checked
                                ? [...prev, item.key]
                                : prev.filter((key) => key !== item.key),
                            )
                          }
                        />{" "}
                        {item.label}
                      </label>
                    ))}
                    <button
                      type="button"
                      style={{ marginBlockStart: 8 }}
                      disabled={busy || draftPermissions.length === 0}
                      data-testid={`team-permission-save-${member.id}`}
                      onClick={() => void savePermissions(member.id)}
                    >
                      {t("team.savePermissions")}
                    </button>
                    <button
                      type="button"
                      className="chip chip-muted"
                      style={{ marginInlineStart: 8 }}
                      onClick={() => {
                        setEditing(null);
                        setDraftPermissions([]);
                      }}
                    >
                      {t("projectRecruitment.cancel")}
                    </button>
                  </fieldset>
                ) : (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="chip chip-muted"
                      data-testid={`team-edit-permissions-${member.id}`}
                      onClick={() => {
                        setEditing(member.id);
                        setDraftPermissions(member.permissions);
                      }}
                    >
                      {t("team.managePermissions")}
                    </button>
                    {member.access_state === "active" ? (
                      <button
                        type="button"
                        className="chip chip-muted"
                        disabled={busy}
                        data-testid={`team-suspend-${member.id}`}
                        onClick={() => void changeAccess(member.id, "suspended")}
                      >
                        {t("team.suspend")}
                      </button>
                    ) : null}
                    {member.access_state === "suspended" ? (
                      <button
                        type="button"
                        className="chip chip-stage"
                        disabled={busy}
                        data-testid={`team-restore-${member.id}`}
                        onClick={() => void changeAccess(member.id, "active")}
                      >
                        {t("team.restore")}
                      </button>
                    ) : null}
                    {member.access_state !== "removed" ? (
                      <button
                        type="button"
                        className="chip chip-muted"
                        disabled={busy}
                        data-testid={`team-remove-${member.id}`}
                        onClick={() => void changeAccess(member.id, "removed")}
                      >
                        {t("team.remove")}
                      </button>
                    ) : null}
                  </div>
                )}
              </div>
            ) : null}
          </article>
        ))}
      </div>

      {/* ══ الدعوات ══ */}
      {canManageTeam ? (
        <>
          <h2>{t("team.invitations")}</h2>
          <p className="provenance-note">{t("team.invitationNote")}</p>
          {projectId && loaded && invitations.length === 0 && !error ? (
            <p style={{ color: "var(--muted)" }}>{t("team.emptyInvitations")}</p>
          ) : null}
          <div style={{ display: "grid", gap: 8 }}>
            {invitations.map((invitation) => (
              <article className="card" key={invitation.id}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <strong>{invitation.invited_display_name}</strong>
                  <span className="metric-label">{invitation.state_label}</span>
                </div>
                <p className="metric-label">
                  {invitation.invited_email} · {invitation.proposed_role_label}
                </p>
                {invitation.state === "invited" ? (
                  <button type="button" disabled={busy} onClick={() => void revoke(invitation.id)}>
                    {t("team.revokeInvitation")}
                  </button>
                ) : null}
              </article>
            ))}
          </div>

          {issuedToken ? (
            <article className="card" style={{ marginBlockStart: 12 }} data-testid="team-token">
              <strong>{t("team.tokenIssued")}</strong>
              {/* **يُعرض مرّةً واحدة.** والخادم يحفظ تجزئته لا نصّه، فلا سبيل
                  إلى إظهاره ثانيةً — ولا سبيل إلى انتحاله لمن قرأ القاعدة. */}
              <p className="provenance-note">{t("team.tokenOnce")}</p>
              {/* ورمزٌ طويلٌ لا يدفع الصفحةَ أفقيًّا على ٣٧٥px. */}
              <code style={{ overflowWrap: "anywhere", display: "block" }}>{issuedToken}</code>
            </article>
          ) : null}

          <article className="card" style={{ marginBlockStart: 12 }}>
            <strong>{t("team.inviteMember")}</strong>
            <p className="provenance-note">{t("team.inviteNote")}</p>
            <label style={{ display: "block", marginBlockStart: 8 }}>
              {t("team.displayName")}
              <input
                type="text"
                style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label style={{ display: "block", marginBlockStart: 8 }}>
              {t("team.email")}
              <input
                type="email"
                style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label style={{ display: "block", marginBlockStart: 8 }}>
              {t("team.role")}
              <select
                style={{ display: "block", marginBlockStart: 4 }}
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                {roleVocab.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              style={{ marginBlockStart: 8 }}
              disabled={busy || name.trim().length < 2 || !email.includes("@") || !projectId}
              onClick={() => void invite()}
            >
              {t("team.sendInvitation")}
            </button>
          </article>
        </>
      ) : null}

      {/* **والقبولُ بالرمز متاحٌ لكلّ أحد** — ومَن يقبل ليس عضوًا بعد،
          فلا يُشترط له `manage_team` ولا عضويّةٌ قائمة. */}
      <InvitationAcceptPanel locale={locale} onAccepted={() => refresh()} />

      {canManageTeam ? (
        <article className="card" style={{ marginBlockStart: 12 }}>
          <strong>{t("team.addMember")}</strong>
          {/* **مساهمٌ بلا حساب.** ويُقال ذلك صراحةً حتى لا يُظنّ شريكًا يدخل. */}
          <p className="provenance-note">{t("team.addMemberNote")}</p>
          <label style={{ display: "block", marginBlockStart: 8 }}>
            {t("team.displayName")}
            <input
              type="text"
              style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label style={{ display: "block", marginBlockStart: 8 }}>
            {t("team.role")}
            <select
              style={{ display: "block", marginBlockStart: 4 }}
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {roleVocab.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <fieldset style={{ marginBlockStart: 8 }}>
            <legend className="metric-label">{t("team.creditRoles")}</legend>
            {creditVocab.map((item) => (
              <label key={item.key} style={{ display: "inline-block", marginInlineEnd: 12 }}>
                <input
                  type="checkbox"
                  checked={credit.includes(item.key)}
                  onChange={(event) =>
                    setCredit((prev) =>
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
          <button
            type="button"
            style={{ marginBlockStart: 8 }}
            disabled={busy || name.trim().length < 2 || !projectId}
            onClick={() => void addMember()}
          >
            {t("team.add")}
          </button>
        </article>
      ) : null}

      {/* ══ سجلُّ الفريق — **وقائعُ محفوظةٌ لا حالٌ تُستنتج** ══
          ولا بِنيةَ تدقيقٍ ثانية: `ProjectMemberEvent` هو المصدر. */}
      <h2>{t("team.activity")}</h2>
      <p className="provenance-note">{t("team.activityNote")}</p>
      {projectId && loaded && events.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("team.emptyActivity")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }} data-testid="team-activity">
        {events.map((event) => (
          <article className="card" key={event.id}>
            <div
              style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
            >
              <strong>{eventLabel(event.event_kind)}</strong>
              <span className="metric-label">
                {new Date(event.occurred_at).toLocaleString(locale)}
              </span>
            </div>
            {event.note_ar ? <p style={{ marginBlock: 4 }}>{event.note_ar}</p> : null}
          </article>
        ))}
      </div>

      <h2>{t("team.decisions")}</h2>
      <p className="provenance-note">{t("team.ledgerNote")}</p>
      {!projectsLoaded || (projectId && !loaded) ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : projectId && decisions.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("team.emptyDecisions")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {decisions.map((decision) => (
          <article
            className="card"
            key={decision.id}
            style={decision.is_superseded ? { opacity: 0.6 } : undefined}
          >
            <div
              style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
            >
              <strong>{decision.kind_label}</strong>
              <span className="metric-label">
                {decision.is_superseded ? t("team.superseded") : t("team.current")}
                {decision.gate ? ` · ${decision.gate}` : ""}
              </span>
            </div>
            <p style={{ marginBlock: 4 }}>{decision.statement}</p>
            {decision.supersedes_id ? (
              <p className="provenance-note">{t("team.supersedesEarlier")}</p>
            ) : null}
          </article>
        ))}
      </div>
      <p className="provenance-note">{t("team.decisionHistoryNote")}</p>
    </>
  );
}
