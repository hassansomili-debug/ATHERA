"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * فريق المشروع وقراراته (§12، §24).
 *
 * **أربعةُ تمييزاتٍ تُعرض منفصلةً لأنها منفصلة في القاعدة:**
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

export default function TeamPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [inbox, setInbox] = useState<PendingAction[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [creditVocab, setCreditVocab] = useState<Vocabulary[]>([]);
  const [roleVocab, setRoleVocab] = useState<Vocabulary[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("co_author");
  const [credit, setCredit] = useState<string[]>([]);
  // يُعرض مرّةً واحدة بعد الدعوة — والخادم لا يعيده في أيّ قراءةٍ بعدها.
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  const [joinToken, setJoinToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // **رايتان لا واحدة، لأنهما سؤالان مختلفان**: هل وصلت قائمة أبحاثه؟ وهل
  // وصل فريق البحث المختار؟ ودمجهما كان يُنتج أسوأ الحالين: باحثٌ لا بحث
  // له يقرأ «لا مؤلفين مسجّلين» و«لا قرارات» — وهما دعويان عن بحثٍ غير
  // موجود أصلًا، والصواب أن يُقال له: ابدأ ببحث.
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // سلسلةُ وعدٍ لا `await` في تأثير — `react-hooks/set-state-in-effect`.
  useEffect(() => {
    Promise.all([
      apiFetch<Project[]>("/api/v1/portfolio/projects", { locale }),
      apiFetch<Vocabulary[]>("/api/v1/vocab/credit-roles", { locale }),
      apiFetch<Vocabulary[]>("/api/v1/vocab/member-roles", { locale }),
    ])
      .then(([list, creditRoles, memberRoles]) => {
        setProjects(list);
        setCreditVocab(creditRoles);
        setRoleVocab(memberRoles);
        if (list.length > 0) setProjectId(list[0]!.id);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      .finally(() => setProjectsLoaded(true));
  }, [locale, t]);

  const load = useCallback(async () => {
    if (!projectId) return;
    setError(null);
    try {
      const [people, log, pending] = await Promise.all([
        apiFetch<Member[]>(`/api/v1/projects/${projectId}/members`, { locale }),
        apiFetch<Decision[]>(`/api/v1/projects/${projectId}/decisions`, { locale }),
        apiFetch<PendingAction[]>(`/api/v1/projects/${projectId}/decisions/inbox`, {
          locale,
        }),
      ]);
      setMembers(people);
      setDecisions(log);
      setInbox(pending);
      // الدعواتُ تلزمها إدارةُ فريق؛ وغيابها ليس فشلًا يُعرض بحمرة.
      try {
        setInvitations(
          await apiFetch<Invitation[]>(`/api/v1/projects/${projectId}/invitations`, {
            locale,
          }),
        );
      } catch {
        setInvitations([]);
      }
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, projectId, t]);

  useDeferredLoad(load);

  async function addMember() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/projects/${projectId}/members`, {
        method: "POST",
        locale,
        body: JSON.stringify({ display_name: name, role, credit_roles: credit }),
      });
      setName("");
      setCredit([]);
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
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
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(invitationId: string) {
    setBusy(true);
    try {
      await apiFetch(`/api/v1/projects/${projectId}/invitations/${invitationId}`, {
        method: "DELETE",
        locale,
      });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function acceptInvitation() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/api/v1/invitations/accept", {
        method: "POST",
        locale,
        body: JSON.stringify({ token: joinToken.trim() }),
      });
      setJoinToken("");
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  /** **موافقتُك أنت.** ولا يقبل هذا المسار معرِّف عضوٍ سواك. */
  async function consentAsMyself(granted: boolean) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/projects/${projectId}/members/me/consent`, {
        method: "POST",
        locale,
        body: JSON.stringify({ granted }),
      });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  const awaitingMe = inbox.some((item) => item.is_mine && item.kind === "author_consent");

  return (
    <>
      <h1>{t("team.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("team.subtitle")}</p>
      <p className="provenance-note">{t("team.creditNote")}</p>
      <p className="provenance-note">{t("team.consentIsPersonal")}</p>
      {error ? <p className="error">{error}</p> : null}

      <label style={{ display: "block", marginBlockEnd: 12 }}>
        {t("team.project")}
        <select
          style={{ marginInlineStart: 8 }}
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.working_title}
            </option>
          ))}
        </select>
      </label>

      {/* لا بحث ⇒ لا فريق ولا قرارات: تُقال العلّة مرّة، ولا تُقال مرّتين
          بصيغةٍ توهم أن البحث قائمٌ وفريقه خالٍ. */}
      {projectsLoaded && projects.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>{t("team.noProject")}</p>
      ) : null}

      {/* ══ ما يحتاج فعلًا الآن — **قائمةٌ غيرُ السجلّ التاريخي** ══
          وخلطُهما يجعل الفريق يقرأ سطرًا لا يعرف أينتظره أم انتهى. */}
      <h2>{t("team.inbox")}</h2>
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

            <p className="metric-label">
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
          </article>
        ))}
      </div>

      {/* ══ الدعوات ══ */}
      <h2>{t("team.invitations")}</h2>
      <p className="provenance-note">{t("team.invitationNote")}</p>
      {projectId && loaded && invitations.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("team.emptyInvitations")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {invitations.map((invitation) => (
          <article className="card" key={invitation.id}>
            <div
              style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
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
        <article className="card" style={{ marginBlockStart: 12 }}>
          <strong>{t("team.tokenIssued")}</strong>
          {/* **يُعرض مرّةً واحدة.** والخادم يحفظ تجزئته لا نصّه، فلا سبيل
              إلى إظهاره ثانيةً — ولا سبيل إلى انتحاله لمن قرأ القاعدة. */}
          <p className="provenance-note">{t("team.tokenOnce")}</p>
          <code style={{ wordBreak: "break-all" }}>{issuedToken}</code>
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

      <article className="card" style={{ marginBlockStart: 12 }}>
        <strong>{t("team.joinByToken")}</strong>
        <p className="provenance-note">{t("team.joinNote")}</p>
        <input
          type="text"
          style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
          value={joinToken}
          onChange={(event) => setJoinToken(event.target.value)}
        />
        <button
          type="button"
          style={{ marginBlockStart: 8 }}
          disabled={busy || joinToken.trim().length < 16}
          onClick={() => void acceptInvitation()}
        >
          {t("team.acceptInvitation")}
        </button>
      </article>

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
