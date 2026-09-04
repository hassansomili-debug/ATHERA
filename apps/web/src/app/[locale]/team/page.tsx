"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * فريق المشروع وقراراته (§12، §24).
 *
 * أدوار CRediT تُختار يدويًّا ولا تُقترح: اقتراحها من نشاط أحد في المنصة
 * يحوّل «من فعل ماذا» من إقرار إلى استنتاج، وهو ما يجعل نزاعات التأليف.
 *
 * والموافقة تُسجَّل لكل مؤلف على حدة — لا زرّ «وافق الجميع»، لأن موافقة
 * تُمنح بضغطة واحدة عن آخرين ليست موافقة.
 *
 * وسجل القرارات يعرض المنسوخ والناسخ معًا: إخفاء القديم يجعل السجل يبدو
 * كأن الرأي الحالي هو الرأي الوحيد الذي كان.
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
  role: string;
  role_label: string;
  credit_roles: string[];
  credit_labels: string[];
  consent_recorded_at: string | null;
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
}

export default function TeamPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [members, setMembers] = useState<Member[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [creditVocab, setCreditVocab] = useState<Vocabulary[]>([]);
  const [roleVocab, setRoleVocab] = useState<Vocabulary[]>([]);
  const [name, setName] = useState("");
  const [role, setRole] = useState("co_author");
  const [credit, setCredit] = useState<string[]>([]);
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
    try {
      const [people, log] = await Promise.all([
        apiFetch<Member[]>(`/api/v1/projects/${projectId}/members`, { locale }),
        apiFetch<Decision[]>(`/api/v1/projects/${projectId}/decisions`, { locale }),
      ]);
      setMembers(people);
      setDecisions(log);
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

  async function recordConsent(memberId: string) {
    setBusy(true);
    try {
      await apiFetch(`/api/v1/projects/${projectId}/members/${memberId}/consent`, {
        method: "POST",
        locale,
      });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>{t("team.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("team.subtitle")}</p>
      <p className="provenance-note">{t("team.creditNote")}</p>
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

      <h2>{t("team.members")}</h2>
      {!projectsLoaded || (projectId && !loaded) ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : projectId && members.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("team.emptyMembers")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {members.map((member) => (
          <article className="card" key={member.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{member.display_name}</strong>
              <span className="metric-label">{member.role_label}</span>
            </div>
            <p className="metric-label">
              {t("team.creditRoles")}: {member.credit_labels.join("، ") || t("common.none")}
            </p>
            {member.consent_recorded_at ? (
              <p className="badge-ok">{t("team.consentRecorded")}</p>
            ) : (
              <button type="button" disabled={busy} onClick={() => void recordConsent(member.id)}>
                {t("team.recordConsent")}
              </button>
            )}
          </article>
        ))}
      </div>

      <article className="card" style={{ marginBlockStart: 12 }}>
        <strong>{t("team.addMember")}</strong>
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
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
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
