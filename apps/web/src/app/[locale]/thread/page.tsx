"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مختبر الخيط الذهبي (§15).
 *
 * الدرجة معروضة، لكن **البوابة لا تُقرأ منها**: العدّاد الحاجب وقائمة
 * العناصر المفقودة هما ما يفتح البوابة أو يغلقها (§15.3). ولذلك يظهران
 * بجانب الرقم دائمًا، لا خلف نقرة.
 */
interface Finding {
  check_key: string;
  kind: string;
  is_blocking: boolean;
  detail: string;
  excerpt: string | null;
}

interface Consistency {
  score: number;
  findings: Finding[];
  missing_elements: string[];
  blocking_count: number;
  advisory_count: number;
  can_pass_gate: boolean;
  note: string;
}

interface Project {
  id: string;
  working_title: string;
}

export default function ThreadPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [data, setData] = useState<Consistency | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Project[]>("/api/v1/portfolio/projects", { locale })
      .then((rows) => {
        setProjects(rows);
        if (rows.length > 0) setProjectId(rows[0]!.id);
      })
      .catch(() => setProjects([]));
  }, [locale]);

  useEffect(() => {
    if (!projectId) return;
    apiFetch<Consistency>(`/api/v1/projects/${projectId}/thread/consistency`, { locale })
      .then(setData)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale, projectId, t]);

  return (
    <>
      <h1>{t("thread.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("thread.subtitle")}</p>

      {projects.length > 1 ? (
        <select
          value={projectId ?? ""}
          onChange={(e) => setProjectId(e.target.value)}
          style={{
            padding: "8px 12px",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            background: "var(--surface)",
            color: "inherit",
            font: "inherit",
            marginBlockEnd: "var(--space)",
          }}
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.working_title}
            </option>
          ))}
        </select>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
      {!projectId ? <p style={{ color: "var(--muted)" }}>{t("thread.noProject")}</p> : null}

      {data ? (
        <>
          <section className="grid">
            <article className="card">
              <div className="metric-label">{t("thread.score")}</div>
              <div className="metric-value">{data.score}</div>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.blocking")}</div>
              <div className="metric-value" style={{ color: data.blocking_count ? "#b3261e" : undefined }}>
                {data.blocking_count}
              </div>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.advisory")}</div>
              <div className="metric-value" style={{ color: data.advisory_count ? "var(--athera-gold)" : undefined }}>
                {data.advisory_count}
              </div>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.missing")}</div>
              <div className="metric-value">{data.missing_elements.length}</div>
            </article>
          </section>

          <p className="provenance-note">
            {data.can_pass_gate ? t("thread.gateOpen") : t("thread.gateBlocked")} — {t("thread.gateNote")}
          </p>

          {data.findings.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>{t("thread.clean")}</p>
          ) : null}

          <div style={{ display: "grid", gap: 8 }}>
            {data.findings.map((finding, index) => (
              <article className="card" key={`${finding.check_key}-${index}`}>
                <div className="metric-label" style={{ color: finding.is_blocking ? "#b3261e" : "var(--athera-gold)" }}>
                  {finding.is_blocking ? t("thread.structural") : t("thread.linguistic")}
                </div>
                <p style={{ marginBlock: 6, fontSize: 14 }}>{finding.detail}</p>
                {finding.excerpt ? (
                  <blockquote
                    style={{
                      margin: 0,
                      paddingInlineStart: 12,
                      borderInlineStart: "3px solid var(--border)",
                      color: "var(--muted)",
                      fontSize: 13,
                    }}
                  >
                    {t("thread.excerpt")}: «{finding.excerpt}»
                  </blockquote>
                ) : null}
              </article>
            ))}
          </div>

          <p className="provenance-note">{data.note}</p>
        </>
      ) : null}
    </>
  );
}
