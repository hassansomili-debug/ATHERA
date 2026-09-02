"use client";

import { use, useCallback, useEffect, useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { stageKeyFor } from "@/lib/stages";
import { ContextLinks } from "@/components/ContextLinks";
import {
  type ProjectSummary,
  createProject,
  listProjects,
  restoreProject,
  trashProject,
} from "@/lib/workspace";

/**
 * محفظة الأبحاث.
 *
 * كانت تعرض «الوحدة المتوقعة» — وهي وحدة لائحة ترقية مُسقَطة، لا مقياس بحث.
 * أُزيلت مع إعادة التموضع (ADR-0005). والحقل `expected_units` ما زال يعود من
 * الـAPI ولا تقرؤه الواجهة؛ يُزال من العقد في مرحلة S3.
 */
interface Project {
  id: string;
  working_title: string;
  study_type: string | null;
  status: string;
  target_journal_name: string | null;
  target_index_tier: string | null;
  current_gate: string | null;
  is_thesis_derived: boolean;
}

interface ReferencePlan {
  projects: number;
  sole_authored: number;
  planned_units: number;
  is_binding: boolean;
  note_ar: string;
  note_en: string;
}

/**
 * أدوات المشروع — كانت في القائمة الدائمة، وموضعها هنا.
 *
 * ستّتها تخدم مشروعًا قائمًا لا الباحث عمومًا: خيطه الذهبي، وسجل ادعاءاته،
 * وفرص النشر المشتقّة منه، وفريقه، وقراراته المنتظرة، ونشراته. ومساراتها
 * لم تتغيّر — من حفظ رابطًا منها ما زال يعمل.
 */
const PROJECT_TOOLS = [
  { key: "nav.thread", path: "thread", hint: "workspace.threadHint" },
  { key: "nav.claims", path: "claims", hint: "workspace.claimsHint" },
  { key: "nav.opportunities", path: "opportunities", hint: "workspace.opportunitiesHint" },
  { key: "nav.team", path: "team", hint: "workspace.teamHint" },
  { key: "nav.approvals", path: "approvals", hint: "workspace.approvalsHint" },
  { key: "nav.briefs", path: "briefs", hint: "workspace.briefsHint" },
];

export default function PortfolioPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [trashed, setTrashed] = useState<ProjectSummary[]>([]);
  const [plan, setPlan] = useState<ReferencePlan | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
    [locale, t],
  );

  const reload = useCallback(() => {
    apiFetch<Project[]>("/api/v1/portfolio/projects", { locale }).then(setProjects).catch(say);
    listProjects(locale, true).then(setTrashed).catch(() => setTrashed([]));
  }, [locale, say]);

  async function startProject(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await createProject(locale, newTitle.trim());
      setNewTitle("");
      router.push(`/${locale}/portfolio/${created.id}`);
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  async function moveToTrash(id: string) {
    setBusy(true);
    try {
      await trashProject(locale, id);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  async function putBack(id: string) {
    setBusy(true);
    try {
      await restoreProject(locale, id);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    Promise.all([
      apiFetch<Project[]>("/api/v1/portfolio/projects", { locale }),
      apiFetch<ReferencePlan>("/api/v1/portfolio/reference-plan", { locale }),
    ])
      .then(([rows, referencePlan]) => {
        setProjects(rows);
        setPlan(referencePlan);
      })
      .catch(say);
    listProjects(locale, true).then(setTrashed).catch(() => setTrashed([]));
  }, [locale, say]);

  return (
    <>
      <h1>{t("portfolio.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("portfolio.subtitle")}</p>
      {error ? <p className="error">{error}</p> : null}

      {plan ? (
        <article className="card" style={{ marginBlockEnd: "var(--space)" }}>
          <div className="metric-label">{t("portfolio.referencePlan")}</div>
          <div style={{ fontSize: 14, marginBlock: 6 }}>
            {plan.projects} · {plan.sole_authored} · {plan.planned_units}
          </div>
          <div className="metric-label">{locale === "en" ? plan.note_en : plan.note_ar}</div>
        </article>
      ) : null}

      {/* **الاستمارةُ قبل الفكرة توقف الباحث عند الباب.** فعنوانٌ واحد يكفي. */}
      <article className="card" style={{ marginBlockEnd: "var(--space)" }}>
        <div className="metric-label">{t("project.newTitle")}</div>
        <p style={{ marginBlockStart: 4, fontSize: 14 }}>{t("project.newHint")}</p>
        <form className="form" onSubmit={startProject} style={{ maxInlineSize: 520 }}>
          <label htmlFor="new-project-title">{t("project.titleLabel")}</label>
          <input
            id="new-project-title"
            value={newTitle}
            minLength={3}
            required
            placeholder={t("project.titlePlaceholder")}
            onChange={(event) => setNewTitle(event.target.value)}
          />
          <button type="submit" disabled={busy || newTitle.trim().length < 3}>
            {busy ? t("project.creating") : t("project.create")}
          </button>
        </form>
      </article>

      {projects.length === 0 ? <p style={{ color: "var(--muted)" }}>{t("portfolio.empty")}</p> : null}

      <div style={{ display: "grid", gap: 8 }}>
        {projects.map((project) => (
          <article className="card" key={project.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              {/* العنوان هو المدخل — **ولا يُنسخ معرّف**. */}
              <Link href={`/${locale}/portfolio/${project.id}`}>
                <strong>{project.working_title}</strong>
              </Link>
              <span className="chip chip-stage">{t(`stages.${stageKeyFor(project.current_gate)}`)}</span>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 10 }}>
              {project.study_type ? <span className="chip chip-muted">{project.study_type}</span> : null}
              {project.target_journal_name ? (
                <span className="chip chip-muted">
                  {t("portfolio.targetJournal")}: {project.target_journal_name}
                </span>
              ) : null}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 10 }}>
              <Link className="chip chip-muted" href={`/${locale}/portfolio/${project.id}`}>
                {t("project.open")}
              </Link>
              <button
                type="button"
                className="chip chip-muted"
                disabled={busy}
                onClick={() => moveToTrash(project.id)}
              >
                {t("project.trash")}
              </button>
            </div>
          </article>
        ))}
      </div>

      {/* السلّة: لا يُتلف شيء، والاستعادة ترجع البحث كما كان. */}
      <h2>{t("project.trashTab")}</h2>
      <p className="metric-label" style={{ marginBlockStart: 0 }}>{t("project.trashNote")}</p>
      {trashed.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>{t("project.emptyTrash")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {trashed.map((project) => (
          <article className="card" key={project.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <span>{project.title_ar}</span>
              <button
                type="button"
                className="chip chip-stage"
                disabled={busy}
                onClick={() => putBack(project.id)}
              >
                {t("project.restore")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <ContextLinks
        locale={locale}
        messages={getMessages(locale)}
        label="workspace.toolsLabel"
        items={PROJECT_TOOLS}
        note="workspace.toolsNote"
      />
    </>
  );
}
