"use client";

import Link from "next/link";
import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad, type Commit } from "@/lib/useDeferredLoad";
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
  // «لا مخطوطات» كانت تُعرض قبل عودة الطلب — والفرق بين «لم يصل الجواب»
  // و«لا مخطوطة لك» هو الفرق بين انتظارٍ وبدايةٍ من الصفر.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async (commit: Commit) => {
    try {
      const rows = await apiFetch<Manuscript[]>("/api/v1/manuscripts", { locale });
      commit(() => setItems(rows));
    } catch (err) {
      const message = err instanceof AtheraApiError
        ? err.localized(locale) : t("common.loadFailed");
      commit(() => setError(message));
    } finally {
      commit(() => setLoaded(true));
    }
  }, [locale, t]);

  const refresh = useDeferredLoad(load);

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
      await refresh();
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
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : items.length === 0 && !error ? (
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

              {/* ── **المدخلُ الرئيس: استوديو الورقة** ──
                  وكانت هذه الشاشةُ تعرض بوّابةَ G9 وحدها: «افحص الجاهزية»
                  و«اعتمد G9» — فيقف من بنى ورقته أمام فحصِ جاهزيةٍ لا
                  أمام ورقته. والاستوديو قائمٌ في `/{id}/studio` منذ حين،
                  ولا رابطَ إليه من هنا. */}
              <div style={{ marginBlockStart: 8 }}>
                <Link
                  href={`/${locale}/manuscripts/${item.id}/studio`}
                  data-testid={`manuscript-open-studio-${item.id}`}
                  style={{
                    display: "inline-block",
                    padding: "8px 16px", borderRadius: "var(--radius)",
                    background: "var(--athera-aqua, var(--athera-teal))",
                    color: "#04302c", fontWeight: 600, textDecoration: "none",
                  }}
                >
                  {t("manuscripts.openStudio")}
                </Link>
              </div>

              {/* ── وجاهزيةُ النشر تُطوى ولا تُحذف ──
                  **وG9 حدٌّ قائم**: منطقُه ونقاطُ نهايته لم تُمسّ. وموضعُه
                  هنا: بعد أن تُكتب الورقة، لا قبل أن تُفتح. */}
              <details data-testid={`manuscript-advanced-${item.id}`}
                       style={{ marginBlockStart: 8 }}>
                <summary className="metric-label" style={{ cursor: "pointer" }}>
                  {t("manuscripts.advancedReadiness")}
                </summary>

                <p className="provenance-note" style={{ marginBlockStart: 6 }}>
                  {t("manuscripts.gateNote")}
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
                  <button type="button" data-testid={`manuscript-check-${item.id}`}
                          disabled={busyId === item.id}
                          onClick={() => void check(item.id)}>
                    {t("manuscripts.checkReadiness")}
                  </button>
                  <button
                    type="button"
                    data-testid={`manuscript-approve-g9-${item.id}`}
                    disabled={busyId === item.id || !state?.can_pass_g9
                              || Boolean(item.g9_approved_at)}
                    onClick={() => void approve(item.id)}
                  >
                    {t("manuscripts.approveG9")}
                  </button>
                </div>
              </details>
            </article>
          );
        })}
      </div>
    </>
  );
}
