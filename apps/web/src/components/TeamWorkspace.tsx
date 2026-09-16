"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad, type Commit } from "@/lib/useDeferredLoad";
import { getMessages, translator, type Locale } from "@/lib/i18n";
import { InvitationAcceptPanel } from "@/components/InvitationAcceptPanel";
import { projectAccess, type ProjectAccess } from "@/lib/recruitment";
import { InviteDialog } from "@/components/team/InviteDialog";
import { MemberDetail } from "@/components/team/MemberDetail";
import { type Vocabulary } from "@/components/team/permissionGroups";
import {
  accessChip,
  type Decision,
  type Invitation,
  type Member,
  type MemberEvent,
  type PendingAction,
  type TeamProject,
} from "@/components/team/types";

/**
 * فريقُ البحث — **محرّكٌ واحدٌ، وهيئتان، وثلاثةُ أبوابٍ لا ثمانيةَ عشر**
 * (§12، §24، RC-T1C، RC-T1C UX-1).
 *
 * ## العطبُ الذي تعالجه هذه الدفعة
 *
 * كانت هذه الشاشةُ تعرض نموذجَ البيانات كلَّه في عمودٍ واحد: وصلتي، ثمّ
 * صلاحيّاتي، ثمّ ما ينتظرني، ثمّ موافقتي، ثمّ الأعضاء — وفي بطاقة كلِّ
 * عضوٍ تسعُ صلاحياتٍ وأدوارُ CRediT وحالُ التأليف والموافقةُ وطريقتُها
 * ومَن سجّلها — ثمّ الدعوات، ثمّ رمزُها، ثمّ نموذجُ الدعوة، ثمّ قبولُ
 * الدعوة، ثمّ مساهمٌ بلا حساب، ثمّ السجلّ، ثمّ القرارات.
 *
 * **وكلُّ سطرٍ منها صادق.** وردَّها المالكُ بعد استعمالٍ يدويّ: «تغيّرت
 * إدارةُ الفريق، لكنّ التجربةَ سيّئةٌ وغيرُ واضحة». وذاك حكمٌ على
 * **معمارِ المعلومة** لا على الصلاحيّات ولا على RLS: من يريد أن يعرف «من
 * في هذا البحث؟» لا يجوز أن يقرأ الجدولَ ليعرف.
 *
 * ## والأسئلةُ الخمسةُ التي تُجاب في خمس ثوانٍ
 *
 *     من في هذا البحث؟          ← الأعضاء، وهو البابُ الافتراضيّ
 *     ما دورُ كلٍّ منهم؟         ← سطرٌ في بطاقته
 *     من نشِطٌ ومن موقوف؟        ← شريحةُ حالٍ بنصٍّ لا بلونٍ وحده
 *     ما الذي ينتظر انتباهي؟     ← شريطٌ يظهر **إن وُجد**، ويغيب إن لم يوجد
 *     كيف أدعو باحثًا؟           ← زرٌّ أوّلٌ في الرأس
 *
 * وما عدا ذلك تفصيلٌ يُفتح عند الطلب: `MemberDetail` للعضو، و`InviteDialog`
 * للدعوة ورمزِها.
 *
 * ## ولا حقلَ حُذف
 *
 * فالتبسيطُ هنا **نقلُ التعقيد إلى موضع سؤاله**، لا إنقاصُ ما تقوله
 * المنصّة: الصلاحياتُ التسع كاملةٌ في لوح العضو، وCRediT في قسمها،
 * والتأليفُ والموافقةُ في قسمهما، والسجلُّ والقراراتُ في بابهما.
 *
 * ## وهيئتان بمحرّكٍ واحد
 *
 * `/team` العامّة تنتقي البحثَ وتعرض قبولَ الدعوة، وقسمُ البحث
 * `?section=team` يعمل على بحثٍ مُثبَّتٍ بلا مُنتقٍ ولا صندوقِ رمز.
 * **والمنطقُ واحد**: نسختان تفترقان بأوّل تعديل، فتصير إحداهما تعرض
 * الموافقةَ عن غير صاحبها. فالاختلافُ في التركيب وحده (`data-team-mode`)،
 * ولا سطرَ جلبٍ ولا فعلَ مكرَّر.
 *
 * ## وأربعةُ تمييزاتٍ تبقى منفصلةً لأنّها منفصلةٌ في القاعدة
 *
 *     الدورُ في الفريق  ليس صلاحية
 *     الصلاحيةُ         ليست مساهمةَ CRediT
 *     مساهمةُ CRediT    ليست تأليفًا
 *     العضويةُ          ليست موافقةً على التأليف
 *
 * وهي الآن في ثلاثة أقسامٍ داخل لوح العضو — لا في سطورٍ متلاصقةٍ يقرؤها
 * القارئُ فيفترض الأربعةَ معًا.
 *
 * **ولا زرَّ «وافق الجميع»، ولا «سجّل موافقته».** الموافقةُ فعلُ صاحبها:
 * من يفتح الشاشةَ يرى زرَّ موافقةٍ **لنفسه وحده**.
 *
 * ## وإخفاءُ زرٍّ تحسينُ عرضٍ لا حدُّ أمان
 *
 * وما يُعرض مرهونٌ بـ`/projects/{id}/access` — إجابةُ خادمٍ لا حالُ شاشة.
 * وكلُّ مسارٍ خلفه يسأل عن صلاحيّته بنفسه.
 */
type Tab = "members" | "invitations" | "history";
type HistoryTab = "activity" | "decisions";

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
  const mode = fixedProject ? "project" : "global";

  const [projects, setProjects] = useState<TeamProject[]>([]);
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

  // ── حالُ العرض: أيُّ بابٍ مفتوح، وأيُّ تفصيلٍ طُلب ──
  const [tab, setTab] = useState<Tab>("members");
  const [historyTab, setHistoryTab] = useState<HistoryTab>("activity");
  const [openMemberId, setOpenMemberId] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);
  const [attentionOpen, setAttentionOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // ── مساهمٌ بلا حساب: حقولُه حقولُه وحده ──
  //
  // وكانت تتقاسم الحالةَ مع نموذج الدعوة، فاسمٌ يُكتب لدعوةٍ يظهر في
  // «أضف مساهمًا» — وهما فعلان مختلفان لا يشتركان في مسوّدة.
  const [contribName, setContribName] = useState("");
  const [contribRole, setContribRole] = useState("co_author");
  const [contribCredit, setContribCredit] = useState<string[]>([]);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // **رايتان لا واحدة، لأنهما سؤالان مختلفان**: هل وصلت قائمة أبحاثه؟ وهل
  // وصل فريق البحث المختار؟ ودمجهما كان يُنتج أسوأ الحالين: باحثٌ لا بحث
  // له يقرأ «لا أعضاء» و«لا قرارات» — وهما دعويان عن بحثٍ غير موجود.
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
    Promise.all([apiFetch<TeamProject[]>("/api/v1/portfolio/projects", { locale }), catalogs])
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

  /** يجري الفعلَ ثمّ يُصالح الشاشة — ويردّ `false` إن رُدّ الفعل. */
  async function act(run: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await run();
      await refresh();
      return true;
    } catch (err) {
      say(err);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function addContributor() {
    const ok = await act(() =>
      apiFetch(`/api/v1/projects/${projectId}/members`, {
        method: "POST",
        locale,
        body: JSON.stringify({
          display_name: contribName, role: contribRole, credit_roles: contribCredit,
        }),
      }),
    );
    if (ok) {
      setContribName("");
      setContribCredit([]);
    }
  }

  /** يردّ رمزَ الدعوة عند النجاح — ويُعرض مرّةً واحدةً في نافذته. */
  async function invite(
    input: { name: string; email: string; role: string },
  ): Promise<string | null> {
    setBusy(true);
    setError(null);
    try {
      const created = await apiFetch<Invitation>(
        `/api/v1/projects/${projectId}/invitations`,
        {
          method: "POST",
          locale,
          body: JSON.stringify({
            email: input.email, display_name: input.name, role: input.role,
          }),
        },
      );
      await refresh();
      return created.token ?? null;
    } catch (err) {
      say(err);
      return null;
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
  function savePermissions(memberId: string, permissions: string[]): Promise<boolean> {
    return act(() =>
      apiFetch(`/api/v1/projects/${projectId}/members/${memberId}/permissions`, {
        method: "PUT",
        locale,
        body: JSON.stringify({ permissions }),
      }),
    );
  }

  function changeRole(memberId: string, next: string) {
    void act(() =>
      apiFetch(`/api/v1/projects/${projectId}/members/${memberId}/role`, {
        method: "PATCH",
        locale,
        body: JSON.stringify({ role: next }),
      }),
    );
  }

  /**
   * يُبدِّل عضوًا بعينه بما **ردّه الخادم** — لا بقراءةٍ ثانية تكتشفه.
   *
   * وما عداه يبقى كما هو: قراءةٌ لاحقةٌ طبيعيّة تُصالح البقيّة، ولا
   * تدهس هذا الصفَّ بجوابٍ أقدمَ منه.
   */
  function mergeMember(updated: Member) {
    setMembers((prev) =>
      prev.map((row) => (row.id === updated.id ? updated : row)));
  }

  /**
   * إيقافُ مدخلِ عضوٍ أو إعادتُه — **والجوابُ هو الحقيقةُ المعروضة**.
   *
   * ## العطبُ الذي أغلقه هذا، وهو باقٍ مُغلقًا في هذه الدفعة
   *
   * كان الزرّان يُرسمان من قائمةٍ تُعاد قراءتُها بعد التعديل مباشرة:
   * `PATCH` ثمّ `refresh()` ثمّ `GET /members`. وسقطت بوّابةُ الدمج على
   * ذلك بالضبط — ردَّ الخادمُ ٢٠٠ على الإيقاف، ثمّ قرأت الشاشةُ القائمةَ
   * على **الاتصال نفسِه** فعادت «نشِط»، فبقي زرُّ «أوقِف» ولم يظهر
   * «أعِد» أبدًا. ولا خطأَ في الخادم ولا في القاعدة: الردُّ يسبق
   * الإثبات (RC-T1-H1، وهو **باقٍ مفتوحًا** — هذا السطرُ يُغلق مظهرَه
   * هنا لا أصلَه).
   *
   * فنقطةُ التعديل تردّ صفَّ العضو كاملًا بحاله الجديدة، ويُدمج في
   * موضعه. **ولا تُعاد قراءةُ القائمة لاكتشاف ما ردّه الخادمُ توًّا** —
   * وهي كذلك رحلةٌ أقلّ إلى قاعدةٍ في إقليمٍ آخر.
   *
   * وانتقالُ الزرّين إلى لوح العضو **لا يغيّر هذا**: اللوحُ يقرأ صفَّه من
   * `members`، فما يُدمج هنا هو ما يراه هناك. ويحرسه
   * `tests/team-access-state-commit-race.spec.ts` بقارئٍ مُثبَّتٍ على
   * حالٍ قديمة — وقد أُعيد توجيهُه إلى اللوح ولم تُضعَف دعواه.
   */
  async function changeAccess(memberId: string, next: string) {
    setBusy(true);
    setError(null);
    try {
      const updated = await apiFetch<Member>(
        `/api/v1/projects/${projectId}/members/${memberId}/access`,
        {
          method: "PATCH",
          locale,
          body: JSON.stringify({ access_state: next }),
        },
      );
      mergeMember(updated);
      // وعضوٌ أُزيل لا لوحَ له: الإزالةُ تُغلق التفصيلَ وتُبقي الصفَّ.
      if (next === "removed") setOpenMemberId(null);
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
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
  const activeMembers = members.filter((row) => row.access_state === "active").length;
  const openInvitations = invitations.filter((row) => row.state === "invited").length;
  const myRole = access?.role
    ? roleVocab.find((item) => item.key === access.role)?.label ?? access.role
    : null;
  const openMember = members.find((row) => row.id === openMemberId) ?? null;
  const loading = !projectsLoaded || (projectId ? !loaded : false);
  const tabs: Tab[] = canManageTeam
    ? ["members", "invitations", "history"]
    : ["members", "history"];

  return (
    <div data-team-mode={mode} data-testid="team-workspace">
      {error ? <p className="error">{error}</p> : null}

      {/* ══════════ الهيئةُ العامّة وحدها: أيُّ بحثٍ، وهل تنتظرني دعوة ══════════

          وداخل صفحة البحث يكون البحثُ معلومًا من مساره، ومُنتقٍ ثانٍ فيها
          يسمح بتغييرٍ صامتٍ للسياق تحت عنوانٍ يقول بحثًا آخر. */}
      {!fixedProject ? (
        <label className="team-picker">
          {t("team.project")}
          <select
            value={projectId}
            data-testid="team-project-picker"
            onChange={(event) => {
              setProjectId(event.target.value);
              setOpenMemberId(null);
              setTab("members");
            }}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.working_title}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {/* **والقبولُ بالرمز في الهيئة العامّة وحدها** — وهو عملٌ شخصيّ لا
          إدارةُ فريق. ومَن يقبل ليس عضوًا بعد، فلا يقدر أصلًا على فتح
          قسمِ فريقِ بحثٍ ليجده هناك؛ ووجودُه في قسم البحث كان صندوقًا
          يلصق فيه **الأعضاءُ** رموزًا لا تخصّ هذا البحث. */}
      {!fixedProject ? (
        <InvitationAcceptPanel
          locale={locale}
          title={t("team.joinTeamAction")}
          onAccepted={() => refresh()}
        />
      ) : null}

      {!fixedProject && projectsLoaded && projects.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>{t("team.noProject")}</p>
      ) : null}

      {/* ══════════ رأسُ الفريق — اسمٌ، وعدَدان حقيقيّان، وفعلٌ أوّل ══════════ */}
      <header className="team-head">
        <div className="team-head-copy">
          {fixedProject ? <h2 className="team-title">{t("team.heading")}</h2> : null}
          <p className="team-lead">{t("team.headingNote")}</p>
          {/* **ولا نسبةَ إنجازٍ مخترعة**: عدَدان يُعدّان من صفوفٍ حقيقيّة. */}
          <p className="team-counts" data-testid="team-summary">
            <span className="chip chip-muted">
              {t("team.activeCount").replace("{n}", String(activeMembers))}
            </span>
            {canManageTeam ? (
              <span className="chip chip-muted">
                {t("team.pendingInvitationCount").replace("{n}", String(openInvitations))}
              </span>
            ) : null}
          </p>
        </div>
        <div className="team-head-actions">
          {canManageTeam ? (
            <button
              type="button"
              className="btn-primary"
              data-testid="team-invite-open"
              disabled={!projectId}
              onClick={() => setInviteOpen(true)}
            >
              {t("team.inviteMember")}
            </button>
          ) : null}
          {/* **ولا محرّكَ مهامٍّ ثانٍ هنا**: رابطٌ واحدٌ إلى الأصل. */}
          {projectId ? (
            <Link className="btn-quiet" href={`/${locale}/portfolio/${projectId}/tasks`}>
              {t("team.openTasks")}
            </Link>
          ) : null}
        </div>
      </header>

      {/* ══════════ وصلتُك بهذا البحث — **مؤشِّرٌ مُوجَز لا بطاقةٌ كبيرة** ══════════

          وكانت تطبع صلاحيّاتك التسعَ في صدر الشاشة، وهي أوّلُ ما يقرؤه من
          فتحها — وأقلُّ ما يحتاجه. فتُقال الوصلةُ في سطر، والتفصيلُ خلف
          زرٍّ لمن سأل عنه. */}
      {access ? (
        <section className="team-relationship" data-testid="team-my-access">
          <span className="chip chip-stage">
            {access.is_owner
              ? t("team.youAreOwner")
              : myRole
                ? `${t("team.youAreCollaborator")} — ${myRole}`
                : t("team.youAreCollaborator")}
          </span>
          <button
            type="button"
            className="btn-quiet team-inline-btn"
            aria-expanded={accessOpen}
            aria-controls="team-my-access-detail"
            data-testid="team-my-access-toggle"
            onClick={() => setAccessOpen((prev) => !prev)}
          >
            {t("team.viewMyAccess")}
          </button>
          {accessOpen ? (
            <div
              id="team-my-access-detail"
              className="team-access-detail"
              data-testid="team-my-access-detail"
            >
              <p className="metric-label">{t("team.myPermissions")}</p>
              <ul className="team-permission-list">
                {access.permissions.length === 0 ? (
                  <li className="metric-label">{t("team.noPermissions")}</li>
                ) : (
                  access.permissions.map((key) => (
                    <li key={key}>
                      {permissionVocab.find((item) => item.key === key)?.label ?? key}
                    </li>
                  ))
                )}
              </ul>
              {!canManageTeam ? (
                <p className="provenance-note">{t("team.needsManageTeam")}</p>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* ══════════ ما يحتاج انتباهي — **ولا يُعرض فارغًا أبدًا** ══════════

          وكان قسمٌ بعنوانٍ وشرحٍ وجملةِ «لا شيء ينتظر» يشغل صدرَ الشاشة في
          الحال الغالبة: لا شيء. **والفراغُ لا يحتاج عنوانًا** — فإن لم يكن
          بندٌ فلا سطرَ ولا عنوان. */}
      {inbox.length > 0 ? (
        <section className="team-attention" data-testid="team-attention">
          <button
            type="button"
            className="team-attention-btn"
            aria-expanded={attentionOpen}
            aria-controls="team-attention-items"
            data-testid="team-attention-toggle"
            onClick={() => setAttentionOpen((prev) => !prev)}
          >
            {t("team.attention").replace("{n}", String(inbox.length))}
          </button>
          {attentionOpen ? (
            <div id="team-attention-items" className="team-attention-items">
              <p className="provenance-note">{t("team.inboxNote")}</p>
              {inbox.map((item) => (
                <article className="card" key={`${item.kind}-${item.subject_id}`}>
                  <div className="team-row">
                    <strong>{item.kind_label}</strong>
                    <span className="metric-label">
                      {item.is_mine ? t("team.waitsOnYou") : t("team.waitsOnSomeoneElse")}
                    </span>
                  </div>
                  <p style={{ marginBlock: 4 }}>{item.statement}</p>
                </article>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* **وزرُّ الموافقة لصاحبها وحده.** ولا يظهر عن أحدٍ آخر أبدًا. */}
      {awaitingMe ? (
        <article className="card team-consent-call" data-testid="team-my-consent">
          <strong>{t("team.yourConsent")}</strong>
          <p className="provenance-note">{t("team.yourConsentNote")}</p>
          <div className="team-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
              onClick={() => void consentAsMyself(true)}
            >
              {t("team.consentGrant")}
            </button>
            <button
              type="button"
              className="btn-quiet"
              disabled={busy}
              onClick={() => void consentAsMyself(false)}
            >
              {t("team.consentDecline")}
            </button>
          </div>
        </article>
      ) : null}

      {/* ══════════ ثلاثةُ أبوابٍ — والافتراضُ «الأعضاء» ══════════ */}
      <nav aria-label={t("team.heading")}>
        <ul className="team-tabs" role="tablist">
          {tabs.map((key) => (
            <li key={key} role="none">
              <button
                type="button"
                role="tab"
                id={`team-tab-${key}`}
                aria-selected={tab === key}
                aria-controls={`team-panel-${key}`}
                className={tab === key ? "chip chip-stage" : "chip chip-muted"}
                data-testid={`team-tab-${key}`}
                onClick={() => setTab(key)}
              >
                {t(`team.tab.${key}`)}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {loading ? <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p> : null}

      {/* ══════════ ١ · الأعضاء — البابُ الأوّل، وبطاقةٌ تقول أربعةً ══════════ */}
      {tab === "members" ? (
        <section
          role="tabpanel"
          id="team-panel-members"
          aria-labelledby="team-tab-members"
          data-testid="team-panel-members"
        >
          {!loading && projectId && members.length === 0 && !error ? (
            <p style={{ color: "var(--muted)" }}>{t("team.emptyMembers")}</p>
          ) : null}
          <ul className="team-member-list">
            {members.map((member) => (
              <li key={member.id}>
                <article
                  className="card team-member"
                  data-testid={`team-member-${member.id}`}
                  /* دورُ العضو سمةٌ تُقرأ — فالفحصُ يرشّح به بلا لبسٍ مع نصّ. */
                  data-member-role={member.role}
                  data-member-access={member.access_state}
                >
                  <span className="team-avatar" aria-hidden="true">
                    {member.display_name.trim().slice(0, 1)}
                  </span>
                  <div className="team-member-copy">
                    <strong className="team-member-name">{member.display_name}</strong>
                    <span className="team-member-role">{member.role_label}</span>
                    {/* **مؤشِّراتٌ موجزةٌ تُعَدّ ولا تُسرَد.** «٥ صلاحيات» تقول
                        قدرًا، وسردُ الخمسةِ يقول جدولًا. والتفصيلُ في اللوح
                        لمن سأل عنه. */}
                    <span className="team-member-meta">
                      <span className={accessChip(member.access_state)}>
                        {member.access_label}
                      </span>
                      {member.permissions.length > 0 ? (
                        <span className="metric-label">
                          {t("team.permissionCount")
                            .replace("{n}", String(member.permissions.length))}
                        </span>
                      ) : null}
                      {member.credit_roles.length > 0 ? (
                        <span className="metric-label">
                          {t("team.creditCount")
                            .replace("{n}", String(member.credit_roles.length))}
                        </span>
                      ) : null}
                      {/* **والغيابُ لا يحتاج تحذيرًا**: «مؤلف» تُعرض إن كان،
                          ولا تُطبع «ليس مؤلفًا» على كلِّ بطاقةٍ سواه. */}
                      {member.is_author ? (
                        <span className="chip chip-muted">{t("team.author")}</span>
                      ) : null}
                      {!member.is_account_linked ? (
                        <span className="chip chip-muted">{t("team.noAccountShort")}</span>
                      ) : null}
                    </span>
                  </div>
                  {canManageTeam ? (
                    <button
                      type="button"
                      className="btn-quiet team-manage-btn"
                      data-testid={`team-manage-${member.id}`}
                      aria-label={`${t("team.manage")} — ${member.display_name}`}
                      onClick={() => setOpenMemberId(member.id)}
                    >
                      {t("team.manage")}
                    </button>
                  ) : null}
                </article>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* ══════════ ٢ · الدعوات — ولا تُخلط بالأعضاء ══════════

          فالمدعوُّ ليس عضوًا: لا يصير أحدٌ عضوًا حتى يقبل بحسابه هو. */}
      {tab === "invitations" && canManageTeam ? (
        <section
          role="tabpanel"
          id="team-panel-invitations"
          aria-labelledby="team-tab-invitations"
          data-testid="team-panel-invitations"
        >
          <p className="provenance-note">{t("team.invitationNote")}</p>
          {!loading && projectId && invitations.length === 0 && !error ? (
            <p style={{ color: "var(--muted)" }}>{t("team.emptyInvitations")}</p>
          ) : null}
          <ul className="team-member-list">
            {invitations.map((invitation) => (
              <li key={invitation.id}>
                <article className="card" data-testid={`team-invitation-${invitation.id}`}>
                  <div className="team-row">
                    <strong>{invitation.invited_display_name}</strong>
                    <span className="chip chip-muted">{invitation.state_label}</span>
                  </div>
                  <p className="metric-label">
                    {invitation.invited_email} · {invitation.proposed_role_label}
                  </p>
                  {invitation.expires_at ? (
                    <p className="metric-label">
                      {t("team.expires")}:{" "}
                      {new Date(invitation.expires_at).toLocaleString(locale)}
                    </p>
                  ) : null}
                  {invitation.state === "invited" ? (
                    <button
                      type="button"
                      className="btn-quiet"
                      disabled={busy}
                      data-testid={`team-revoke-${invitation.id}`}
                      onClick={() => void revoke(invitation.id)}
                    >
                      {t("team.revokeInvitation")}
                    </button>
                  ) : null}
                </article>
              </li>
            ))}
          </ul>

          {/* ══ إجراءاتٌ إضافية — **ومساهمٌ بلا حساب ليس دعوةَ باحث** ══

              فالأوّلُ يسجّل اسمًا يُنشر، والثاني يفتح بابَ منصّة. وعرضُهما
              متجاورَين متساويَين كان يجعل المديرَ يضيف اسمًا وهو يظنّ أنّه
              دعا شريكًا — فينتظر قبولًا لا يأتي. */}
          <section className="team-advanced">
            <button
              type="button"
              className="btn-quiet"
              aria-expanded={advancedOpen}
              aria-controls="team-advanced-panel"
              data-testid="team-advanced-toggle"
              onClick={() => setAdvancedOpen((prev) => !prev)}
            >
              {t("team.moreActions")}
            </button>
            {advancedOpen ? (
              <div
                id="team-advanced-panel"
                className="card"
                data-testid="team-advanced-panel"
              >
                <strong>{t("team.addContributorNoAccount")}</strong>
                <p className="provenance-note">{t("team.addMemberNote")}</p>
                <div className="form team-form">
                  <label htmlFor="team-contributor-name">
                    {t("team.contributorName")}
                    <input
                      id="team-contributor-name"
                      type="text"
                      value={contribName}
                      onChange={(event) => setContribName(event.target.value)}
                    />
                  </label>
                  <label htmlFor="team-contributor-role">
                    {t("team.role")}
                    <select
                      id="team-contributor-role"
                      value={contribRole}
                      onChange={(event) => setContribRole(event.target.value)}
                    >
                      {roleVocab.map((item) => (
                        <option key={item.key} value={item.key}>{item.label}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <fieldset className="team-permission-group">
                  <legend className="metric-label">{t("team.creditRoles")}</legend>
                  {/* **ولا اقتراحَ لأدوار CRediT من نشاطٍ في المنصّة.** */}
                  {creditVocab.map((item) => (
                    <label key={item.key} className="team-check">
                      <input
                        type="checkbox"
                        checked={contribCredit.includes(item.key)}
                        onChange={(event) =>
                          setContribCredit((prev) =>
                            event.target.checked
                              ? [...prev, item.key]
                              : prev.filter((key) => key !== item.key),
                          )
                        }
                      />{" "}
                      <span>{item.label}</span>
                    </label>
                  ))}
                </fieldset>
                <button
                  type="button"
                  className="btn-quiet"
                  style={{ marginBlockStart: 10 }}
                  disabled={busy || contribName.trim().length < 2 || !projectId}
                  data-testid="team-add-contributor"
                  onClick={() => void addContributor()}
                >
                  {t("team.add")}
                </button>
              </div>
            ) : null}
          </section>
        </section>
      ) : null}

      {/* ══════════ ٣ · السجل — تاريخٌ يُقرأ، لا صدرُ شاشة ══════════

          ومصدران لا يُدمجان في البيانات: وقائعُ الفريق (`ProjectMemberEvent`)
          وقراراتُه (`Decision`). ويُعرضان في بابٍ واحدٍ بفرعين — فالقارئُ
          يسأل «ما جرى؟» سؤالًا واحدًا، ويبقى المصدران متمايزين. */}
      {tab === "history" ? (
        <section
          role="tabpanel"
          id="team-panel-history"
          aria-labelledby="team-tab-history"
          data-testid="team-panel-history"
        >
          <ul className="team-subtabs" role="tablist">
            {(["activity", "decisions"] as const).map((key) => (
              <li key={key} role="none">
                <button
                  type="button"
                  role="tab"
                  id={`team-history-tab-${key}`}
                  aria-selected={historyTab === key}
                  aria-controls={`team-history-panel-${key}`}
                  className={historyTab === key ? "chip chip-stage" : "chip chip-muted"}
                  data-testid={`team-history-tab-${key}`}
                  onClick={() => setHistoryTab(key)}
                >
                  {t(`team.history.${key}`)}
                </button>
              </li>
            ))}
          </ul>

          {historyTab === "activity" ? (
            <div
              role="tabpanel"
              id="team-history-panel-activity"
              aria-labelledby="team-history-tab-activity"
              data-testid="team-activity"
            >
              <p className="provenance-note">{t("team.activityNote")}</p>
              {!loading && projectId && events.length === 0 && !error ? (
                <p style={{ color: "var(--muted)" }}>{t("team.emptyActivity")}</p>
              ) : null}
              <ul className="team-member-list">
                {events.map((event) => (
                  <li key={event.id}>
                    <article className="card">
                      <div className="team-row">
                        {/* ولا مفاتيحُ أحداثٍ داخليّة حين توجد ترجمة. */}
                        <strong>{eventLabel(event.event_kind)}</strong>
                        <span className="metric-label">
                          {new Date(event.occurred_at).toLocaleString(locale)}
                        </span>
                      </div>
                      {event.note_ar ? <p style={{ marginBlock: 4 }}>{event.note_ar}</p> : null}
                    </article>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div
              role="tabpanel"
              id="team-history-panel-decisions"
              aria-labelledby="team-history-tab-decisions"
              data-testid="team-decisions"
            >
              <p className="provenance-note">{t("team.ledgerNote")}</p>
              {!loading && projectId && decisions.length === 0 && !error ? (
                <p style={{ color: "var(--muted)" }}>{t("team.emptyDecisions")}</p>
              ) : null}
              <ul className="team-member-list">
                {decisions.map((decision) => (
                  <li key={decision.id}>
                    <article
                      className="card"
                      style={decision.is_superseded ? { opacity: 0.6 } : undefined}
                    >
                      <div className="team-row">
                        <strong>{decision.kind_label}</strong>
                        <span
                          className={decision.is_superseded ? "chip chip-muted" : "chip chip-ok"}
                        >
                          {decision.is_superseded ? t("team.superseded") : t("team.current")}
                          {decision.gate ? ` · ${decision.gate}` : ""}
                        </span>
                      </div>
                      <p style={{ marginBlock: 4 }}>{decision.statement}</p>
                      {decision.supersedes_id ? (
                        <p className="provenance-note">{t("team.supersedesEarlier")}</p>
                      ) : null}
                    </article>
                  </li>
                ))}
              </ul>
              {/* **والمنسوخُ يبقى معروضًا**: إخفاؤه يجعل السجلَّ يبدو كأنّ
                  الرأيَ الحاليّ هو الوحيد الذي كان. */}
              <p className="provenance-note">{t("team.decisionHistoryNote")}</p>
            </div>
          )}
        </section>
      ) : null}

      {/* ══════════ ما يُفتح فوق الصفحة ══════════

          و`key` على معرّف العضو: عضوٌ آخر مُركّبٌ آخر، فحالاتُ اللوح
          ابتدائيّةٌ بحكم React لا بـ`setState` في تأثير. */}
      {openMember ? (
        <MemberDetail
          key={openMember.id}
          member={openMember}
          t={t}
          locale={locale}
          canManageTeam={canManageTeam}
          busy={busy}
          roleVocab={roleVocab}
          permissionVocab={permissionVocab}
          onClose={() => setOpenMemberId(null)}
          onChangeRole={changeRole}
          onSavePermissions={savePermissions}
          onChangeAccess={(memberId, next) => void changeAccess(memberId, next)}
        />
      ) : null}

      {canManageTeam ? (
        <InviteDialog
          open={inviteOpen}
          t={t}
          busy={busy}
          roleVocab={roleVocab}
          defaultRole="co_author"
          onClose={() => setInviteOpen(false)}
          onInvite={invite}
        />
      ) : null}
    </div>
  );
}
