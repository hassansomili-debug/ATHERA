"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  decideGap,
  loadGaps,
  type Decision,
  type Gap,
  type GapsView,
  type SearchScope,
} from "@/lib/synthesis";

/**
 * الفجوات المحتملة — **وأخطر شاشةٍ في المنتج**.
 *
 * قائمةٌ من «فجوات» جاهزة تُقرأ نتائجَ ثم تُكتب في أوراق. فكلُّ بطاقةٍ هنا
 * تحمل حدَّها معها لا في صفحةٍ أخرى: **كم مرجعًا نُظر فيه**، ومن أيّ
 * فهارس، وكم قُرئ منها محتوًى، وما الحدود المعلومة لهذه الملاحظة. ولا
 * تُعرض بطاقةٌ بلا هذه الأربعة.
 *
 * **والقوّة توصف ولا تُرقَّم.** «إشارة ضعيفة» ومعناها مكتوبٌ تحتها — و«٧٣٪
 * ثقة» رقمٌ لا يقابله قياس، ويُقرأ يقينًا لم يقع.
 *
 * **وما تعذّر الحكم فيه يُعرض بقدر ما وُجد.** قائمةٌ تذكر ما وجدته وتصمت
 * عمّا عجزت عنه يقرأها الباحث «لا شيء آخر» — وهو جوابٌ لم يُفحص. فقسمٌ
 * كاملٌ في هذه الشاشة لِما لم يُحكم فيه، ولكلٍّ سببه.
 *
 * **و«اعتماد» تعني «قرّرت متابعتها» لا «ثبتت».** والنصّ يقول ذلك قبل الزرّ.
 */

type Load = "loading" | "ready" | "failed";

const DECISIONS: Decision[] = ["approved", "needs_review", "unknown", "rejected"];

const DECISION_LABEL: Record<Decision, string> = {
  approved: "synthesis.decideApprove",
  needs_review: "synthesis.decideNeedsReview",
  unknown: "synthesis.decideUnknown",
  rejected: "synthesis.decideReject",
};

export default function GapsPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<GapsView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return loadGaps(locale, projectId)
      .then((view) => {
        setData(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, projectId, say]);

  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  const decide = (gap: Gap, status: Decision) => {
    setBusy(gap.id);
    setError(null);
    void decideGap(locale, projectId, gap.id, status)
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /** **مدى البحث يُعرض مع الدعوى** — ولا يُترك في صفحةٍ أخرى لا تُفتح. */
  const scopeLine = (scope: SearchScope) => (
    <div className="metric-label">
      {t("synthesis.consideredLabel")}: {scope.corpus_size}
      {" · "}
      {t("synthesis.indexesLabel")}:{" "}
      {scope.indexes_searched.length > 0
        ? scope.indexes_searched.join("، ")
        : t("synthesis.notRecorded")}
      {" · "}
      {t("synthesis.contentReadLabel")}: {scope.content_read}
      {" · "}
      {t("synthesis.fullTextReadLabel")}: {scope.full_text_read}
      {scope.saved_not_screened > 0
        ? ` · ${t("synthesis.savedNotScreenedLabel")}: ${scope.saved_not_screened}`
        : ""}
    </div>
  );

  const gaps = data?.gaps ?? [];
  const unassessed = data?.not_assessed ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("synthesis.gapsTitle")}</h1>
      <p className="metric-label">{t("synthesis.gapsMeaning")}</p>

      <nav aria-label={t("synthesis.tabsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/themes`}>
              {t("synthesis.themesTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/contradictions`}>
              {t("synthesis.contradictionsTitle")}
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
        </ul>
      </nav>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="gaps-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="gaps-failed" style={{ color: "var(--muted)" }}>
          {t("synthesis.loadFailedNote")}
        </p>
      ) : (
        <>
          {data?.note_ar ? <p className="metric-label">{data.note_ar}</p> : null}
          {data?.search_scope ? scopeLine(data.search_scope) : null}

          {gaps.length === 0 ? (
            <p data-testid="gaps-empty" style={{ color: "var(--muted)" }}>
              {t("synthesis.gapsEmpty")}
            </p>
          ) : (
            <div style={{ display: "grid", gap: 12, marginBlockStart: "var(--space)" }}>
              {gaps.map((gap) => (
                <article className="card" key={gap.id}>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <span className="chip chip-stage">{gap.gap_type_label_ar}</span>
                    <span className="chip chip-muted">{gap.strength_label_ar}</span>
                    <span className="chip chip-muted">{gap.status_label_ar}</span>
                  </div>

                  {/* ما لوحظ — بحدّه في الجملة نفسها. */}
                  <p style={{ marginBlock: 8 }}>{gap.description_ar}</p>

                  <div className="metric-label">
                    {t("synthesis.strengthMeans")}: {gap.strength_meaning_ar}
                  </div>

                  <p style={{ marginBlock: 6 }}>
                    <strong>{t("synthesis.whyLabel")}: </strong>
                    {gap.why_suggested_ar}
                  </p>

                  {/* **الحدود ركنٌ لا حاشية.** */}
                  <p style={{ marginBlock: 6 }}>
                    <strong>{t("synthesis.limitsLabel")}: </strong>
                    {gap.known_limitations_ar}
                  </p>

                  <div className="metric-label">
                    {t("synthesis.consideredLabel")}: {gap.sources_considered}
                    {" · "}
                    {Object.entries(gap.source_scope_distribution)
                      .map(([scope, count]) => `${t(`synthesis.scope_${scope}`)} ${count}`)
                      .join(" · ") || t("synthesis.notRecorded")}
                  </div>
                  {scopeLine(gap.search_scope)}

                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
                    <button
                      type="button"
                      className="chip chip-muted"
                      aria-expanded={openId === gap.id}
                      aria-label={`${t("synthesis.showSources")}: ${gap.gap_type_label_ar}`}
                      onClick={() => setOpenId(openId === gap.id ? null : gap.id)}
                    >
                      {t("synthesis.showSources")}
                    </button>
                    {DECISIONS.map((status) => (
                      <button
                        key={status}
                        type="button"
                        className={gap.status === status ? "chip chip-stage" : "chip chip-muted"}
                        aria-label={`${t(DECISION_LABEL[status])}: ${gap.gap_type_label_ar}`}
                        aria-pressed={gap.status === status}
                        disabled={busy === gap.id || gap.status === status}
                        onClick={() => decide(gap, status)}
                      >
                        {t(DECISION_LABEL[status])}
                      </button>
                    ))}
                  </div>
                  <p className="metric-label">{t("synthesis.approveMeans")}</p>

                  {gap.may_become_opportunity ? (
                    <Link
                      className="chip chip-stage"
                      href={`/${locale}/portfolio/${projectId}/research-opportunities?gap=${gap.id}`}
                    >
                      {t("synthesis.buildOpportunity")}
                    </Link>
                  ) : null}

                  {openId === gap.id ? (
                    <div style={{ marginBlockStart: 8 }}>
                      {(
                        [
                          ["synthesis.rolesSupporting", gap.supporting],
                          ["synthesis.rolesContradicting", gap.contradicting],
                          ["synthesis.rolesConsidered", gap.considered],
                        ] as const
                      ).map(([label, links]) => (
                        <div key={label} style={{ marginBlockStart: 6 }}>
                          <strong>
                            {t(label)} ({links.length})
                          </strong>
                          <ul style={{ paddingInlineStart: 18, marginBlock: 4 }}>
                            {links.map((link) => (
                              <li key={`${label}-${link.source_id}`}>
                                {link.title}
                                <span className="metric-label">
                                  {" · "}
                                  {t(`synthesis.scope_${link.evidence_scope}`)}
                                  {link.matrix_cell_id
                                    ? ""
                                    : ` · ${t("synthesis.noCellBehindIt")}`}
                                </span>
                                {link.evidence_quote ? (
                                  <blockquote style={{ marginBlock: 4 }}>
                                    «{link.evidence_quote}»
                                  </blockquote>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}

          {/* **العجز يُعلَن باسمه** — ولا يُترك الصمت يُقرأ «لا شيء آخر». */}
          <section style={{ marginBlockStart: "var(--space)" }}>
            <h2>{t("synthesis.notAssessedTitle")}</h2>
            <p className="metric-label">{t("synthesis.notAssessedMeaning")}</p>
            {unassessed.length === 0 ? (
              <p className="metric-label">{t("synthesis.notAssessedNone")}</p>
            ) : (
              <ul style={{ paddingInlineStart: 18 }}>
                {unassessed.map((item) => (
                  <li key={item.gap_type}>
                    <strong>{item.gap_type_label_ar}</strong> — {item.reason_ar}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  );
}
