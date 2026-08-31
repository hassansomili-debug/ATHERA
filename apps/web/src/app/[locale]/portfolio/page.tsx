"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { stageKeyFor } from "@/lib/stages";
import { ContextLinks } from "@/components/ContextLinks";

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

  const [projects, setProjects] = useState<Project[]>([]);
  const [plan, setPlan] = useState<ReferencePlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<Project[]>("/api/v1/portfolio/projects", { locale }),
      apiFetch<ReferencePlan>("/api/v1/portfolio/reference-plan", { locale }),
    ])
      .then(([rows, referencePlan]) => {
        setProjects(rows);
        setPlan(referencePlan);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale, t]);

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

      {projects.length === 0 ? <p style={{ color: "var(--muted)" }}>{t("portfolio.empty")}</p> : null}

      <div style={{ display: "grid", gap: 8 }}>
        {projects.map((project) => (
          <article className="card" key={project.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{project.working_title}</strong>

            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 10 }}>
              <span className="chip chip-stage">{t(`stages.${stageKeyFor(project.current_gate)}`)}</span>
              {project.study_type ? <span className="chip chip-muted">{project.study_type}</span> : null}
              {project.target_journal_name ? (
                <span className="chip chip-muted">
                  {t("portfolio.targetJournal")}: {project.target_journal_name}
                </span>
              ) : null}
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
