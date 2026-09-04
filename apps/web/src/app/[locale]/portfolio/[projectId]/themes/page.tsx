"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  analyze,
  decideTheme,
  loadThemeTrace,
  loadThemes,
  type Decision,
  type Theme,
  type ThemeTrace,
  type ThemesView,
} from "@/lib/synthesis";

/**
 * الموضوعات — **وتجميعٌ موضوعي ليس موضوعًا علميًّا**.
 *
 * عناوينُ عشر دراساتٍ تشترك في كلمة تُجمَع في قائمة، وهذا ترتيبٌ نافع —
 * **ولا شيء فيه نتيجة**. والموضوع العلمي تركيبٌ من محتوًى قُرئ من الأوراق
 * نفسها. وطيُّ الأول في الثاني هو الطريق المباشر إلى «فجوات» من عناوين،
 * فلا يُطوى هنا: لكل بطاقةٍ شارةُ أساسها ونصُّ معناه، لا لونٌ يُستنتج منه.
 *
 * **ولا موضوع بلا أثر.** زرُّ «اعرض السند» يفتح المسار: موضوع ← مرجع ←
 * خلية ← شاهد. وموضوعٌ يقول الخادم إنه غير قابلٍ للتتبّع يُعلَن كذلك ولا
 * يُعرض كغيره.
 *
 * **وأربع حالات عرضٍ لا تُخلط**: قبل الجواب، وأثناءه، وجوابٌ فارغ، وفشل.
 * وأخطرها الأخيرة: طلبٌ فشل يُعرض «لا موضوعات» يجعل الباحث يظنّ مصفوفته
 * فارغة — والشبكة وحدها كانت معطوبة.
 */

type Load = "loading" | "ready" | "failed";

/** الأحكام الأربعة — و«لا أعرف» منها: امتناعٌ عن الحكم ليس حكمًا بالبطلان. */
const DECISIONS: Decision[] = ["approved", "needs_review", "unknown", "rejected"];

const DECISION_LABEL: Record<Decision, string> = {
  approved: "synthesis.decideApprove",
  needs_review: "synthesis.decideNeedsReview",
  unknown: "synthesis.decideUnknown",
  rejected: "synthesis.decideReject",
};

export default function ThemesPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<ThemesView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [trace, setTrace] = useState<ThemeTrace | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return loadThemes(locale, projectId)
      .then((view) => {
        setData(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, projectId, say]);

  /** **لا تُضبط حالةٌ داخل التأثير مباشرةً** — قاعدةٌ يفرضها المدقّق خطأً. */
  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  const runAnalysis = () => {
    setBusy("analyze");
    setError(null);
    void analyze(locale, projectId)
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const decide = (theme: Theme, status: Decision) => {
    setBusy(theme.id);
    setError(null);
    void decideTheme(locale, projectId, theme.id, status)
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const showTrace = (theme: Theme) => {
    setBusy(theme.id);
    setError(null);
    void loadThemeTrace(locale, projectId, theme.id)
      .then((found) => setTrace(found))
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const themes = data?.themes ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("synthesis.themesTitle")}</h1>
      <p className="metric-label">{t("synthesis.themesMeaning")}</p>

      <nav aria-label={t("synthesis.tabsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/contradictions`}>
              {t("synthesis.contradictionsTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/gaps`}>
              {t("synthesis.gapsTitle")}
            </Link>
          </li>
          <li>
            <Link
              className="chip chip-muted"
              href={`/${locale}/portfolio/${projectId}/research-opportunities`}
            >
              {t("synthesis.opportunitiesTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/matrix`}>
              {t("screening.matrixLink")}
            </Link>
          </li>
        </ul>
      </nav>

      {/* **زرٌّ لا يُعرف أثره يُضغط ثم يُندَم عليه.** فيُقال ما يفعله قبله. */}
      <p className="metric-label">{t("synthesis.analyzeNote")}</p>
      <button
        type="button"
        className="chip chip-stage"
        disabled={busy === "analyze"}
        onClick={runAnalysis}
      >
        {busy === "analyze" ? t("app.loading") : t("synthesis.analyze")}
      </button>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="themes-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="themes-failed" style={{ color: "var(--muted)" }}>
          {t("synthesis.loadFailedNote")}
        </p>
      ) : themes.length === 0 ? (
        <p data-testid="themes-empty" style={{ color: "var(--muted)" }}>
          {data?.note_ar || t("synthesis.themesEmpty")}
        </p>
      ) : (
        <>
          {data?.note_ar ? <p className="metric-label">{data.note_ar}</p> : null}
          <div style={{ display: "grid", gap: 10, marginBlockStart: "var(--space)" }}>
            {themes.map((theme) => (
              <article className="card" key={theme.id}>
                {/* **الأساس شارةٌ ونصّ، لا لونٌ يُستنتج منه.** */}
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                  <span
                    className={theme.basis === "content_synthesis" ? "chip chip-stage" : "chip chip-muted"}
                  >
                    {theme.basis_label_ar}
                  </span>
                  <span className="chip chip-muted">{theme.status_label_ar}</span>
                  {theme.is_traceable ? null : (
                    <span className="chip chip-muted">{t("synthesis.notTraceable")}</span>
                  )}
                </div>

                <strong style={{ display: "block", marginBlockStart: 6 }}>{theme.label_ar}</strong>
                <p className="metric-label" style={{ marginBlockStart: 4 }}>
                  {theme.basis_meaning_ar}
                </p>
                {theme.description_ar ? (
                  <p style={{ marginBlock: 6 }}>{theme.description_ar}</p>
                ) : null}

                <div className="metric-label">
                  {t("synthesis.supportingCount")}: {theme.supporting_count}
                  {" · "}
                  {t("synthesis.contradictingCount")}: {theme.contradicting_count}
                </div>
                <div className="metric-label">
                  {t("synthesis.scopeSummary")}:{" "}
                  {Object.entries(theme.source_scope_summary)
                    .map(([scope, count]) => `${t(`synthesis.scope_${scope}`)} ${count}`)
                    .join(" · ") || t("synthesis.scopeUnknown")}
                </div>

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
                  <button
                    type="button"
                    className="chip chip-muted"
                    aria-label={`${t("synthesis.showTrace")}: ${theme.label_ar}`}
                    disabled={busy === theme.id}
                    onClick={() => showTrace(theme)}
                  >
                    {t("synthesis.showTrace")}
                  </button>
                  {DECISIONS.map((status) => (
                    <button
                      key={status}
                      type="button"
                      className={theme.status === status ? "chip chip-stage" : "chip chip-muted"}
                      aria-label={`${t(DECISION_LABEL[status])}: ${theme.label_ar}`}
                      aria-pressed={theme.status === status}
                      disabled={busy === theme.id || theme.status === status}
                      onClick={() => decide(theme, status)}
                    >
                      {t(DECISION_LABEL[status])}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {trace ? (
        <div
          className="card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="trace-title"
          style={{ marginBlockStart: 16 }}
        >
          <strong id="trace-title">
            {t("synthesis.traceTitle")}: {trace.theme.label_ar}
          </strong>
          <p className="metric-label">{trace.note_ar}</p>
          <ul style={{ paddingInlineStart: 18 }}>
            {[...trace.supporting, ...trace.contradicting].map((link) => (
              <li key={`${link.source_id}-${link.basis_field_key ?? "-"}`}>
                <strong>{link.title}</strong>
                <div className="metric-label">
                  {link.basis_field_key ? t(`matrix.field_${link.basis_field_key}`) : "—"}
                  {" · "}
                  {t(`synthesis.scope_${link.evidence_scope}`)}
                  {link.cell_state ? ` · ${t(`synthesis.cellState_${link.cell_state}`)}` : ""}
                </div>
                {link.cell_value_ar ? <p style={{ marginBlock: 4 }}>{link.cell_value_ar}</p> : null}
                {link.evidence_quote ? (
                  <blockquote style={{ marginBlock: 4 }}>
                    «{link.evidence_quote}»
                    {link.evidence_locator ? ` — ${link.evidence_locator}` : ""}
                  </blockquote>
                ) : (
                  <p className="metric-label">{t("synthesis.noQuote")}</p>
                )}
              </li>
            ))}
          </ul>
          <button type="button" className="chip chip-muted" onClick={() => setTrace(null)}>
            {t("synthesis.close")}
          </button>
        </div>
      ) : null}
    </>
  );
}
