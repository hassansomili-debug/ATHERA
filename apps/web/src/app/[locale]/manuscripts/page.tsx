"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مصنع المخطوطات (§19، §20).
 *
 * البوابة G9 هنا ليست زرًّا: الواجهة تعرض العوائق التي أعادها الخادم، والزر
 * يبقى معطّلًا ما دام واحد منها قائمًا. المنع يقع في الخادم، وهذه الشاشة
 * تشرحه فقط — فلو استُدعي الـAPI مباشرة لظل المنع ساريًا.
 */
interface Manuscript {
  id: string;
  project_id: string;
  title: string;
  title_ar: string;
  language: string;
  status: string;
  current_version_label: string | null;
  g9_approved_at: string | null;
}

interface ReadinessIssue {
  section_key: string;
  issue_key: string;
  detail: string;
  excerpt: string | null;
}

interface Readiness {
  manuscript_id: string;
  can_pass_g9: boolean;
  issues: ReadinessIssue[];
  missing_sections: string[];
  sections_checked: number;
  note: string;
}

export default function ManuscriptsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [items, setItems] = useState<Manuscript[]>([]);
  const [readiness, setReadiness] = useState<Record<string, Readiness>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await apiFetch<Manuscript[]>("/api/v1/manuscripts", { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function check(id: string) {
    setBusyId(id);
    setError(null);
    try {
      const result = await apiFetch<Readiness>(`/api/v1/manuscripts/${id}/readiness`, { locale });
      setReadiness((prev) => ({ ...prev, [id]: result }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  async function approve(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/manuscripts/${id}/approve-g9`, { method: "POST", locale });
      await load();
      await check(id);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("manuscripts.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("manuscripts.subtitle")}</p>
      <p className="provenance-note">{t("manuscripts.gateNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {items.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("manuscripts.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {items.map((item) => {
          const state = readiness[item.id];
          return (
            <article className="card" key={item.id}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <strong>{item.title}</strong>
                <span className="metric-label">
                  {t("manuscripts.version")} {item.current_version_label ?? "—"}
                </span>
              </div>
              <p style={{ color: "var(--muted)", marginBlock: 4 }}>
                {t("manuscripts.status")}: {item.status} · {t("manuscripts.language")}:{" "}
                {item.language}
              </p>

              {item.g9_approved_at ? (
                <p className="badge-ok">{t("manuscripts.g9Approved")}</p>
              ) : (
                <p className="metric-label">{t("manuscripts.g9Pending")}</p>
              )}

              {state ? (
                <div style={{ marginBlockStart: 8 }}>
                  <p className="metric-label">
                    {t("manuscripts.sectionsChecked")}: {state.sections_checked}
                    {state.missing_sections.length > 0
                      ? ` · ${t("manuscripts.missingSections")}: ${state.missing_sections.join("، ")}`
                      : ""}
                  </p>
                  {state.issues.length > 0 ? (
                    <ul style={{ marginBlock: 4, paddingInlineStart: 20 }}>
                      {state.issues.map((issue, index) => (
                        <li key={`${issue.issue_key}-${index}`} className="error">
                          [{issue.section_key}] {issue.detail}
                          {issue.excerpt ? ` — «${issue.excerpt}»` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <p className="provenance-note">{state.note}</p>
                </div>
              ) : null}

              <div style={{ display: "flex", gap: 8, marginBlockStart: 8, flexWrap: "wrap" }}>
                <button type="button" disabled={busyId === item.id} onClick={() => void check(item.id)}>
                  {t("manuscripts.checkReadiness")}
                </button>
                <button
                  type="button"
                  disabled={busyId === item.id || !state?.can_pass_g9 || Boolean(item.g9_approved_at)}
                  onClick={() => void approve(item.id)}
                >
                  {t("manuscripts.approveG9")}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
