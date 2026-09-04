"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  decideContradiction,
  loadContradictions,
  type Contradiction,
  type ContradictionSide,
  type ContradictionsView,
  type Decision,
} from "@/lib/synthesis";

/**
 * التعارضات — **والسياق يُعرض قبل الحكم**.
 *
 * «الدراستان تتعارضان» جملةٌ تُغلق التفكير. و«إحداهما درست المستهلكين في
 * السعودية والأخرى موظفي شركات في الولايات المتحدة» تعيد الباحث إليه.
 * فالبطاقة هنا تعرض **الطرفين معًا** جنبًا إلى جنب، وتحتهما أبعادُ
 * اختلافهما مسمّاة — ولا تُوصف أيّ دراسة بالخطأ.
 *
 * **وغيابُ التسجيل ليس غيابًا للاختلاف.** فحقلٌ لم يُملأ في المصفوفة يُعرض
 * «غير مذكور» صريحةً، لا خانةً بيضاء تُقرأ «الظروف واحدة».
 */

type Load = "loading" | "ready" | "failed";

const DECISIONS: Decision[] = ["approved", "needs_review", "unknown", "rejected"];

const DECISION_LABEL: Record<Decision, string> = {
  approved: "synthesis.decideApprove",
  needs_review: "synthesis.decideNeedsReview",
  unknown: "synthesis.decideUnknown",
  rejected: "synthesis.decideReject",
};

export default function ContradictionsPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<ContradictionsView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return loadContradictions(locale, projectId)
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

  const decide = (item: Contradiction, status: Decision) => {
    setBusy(item.id);
    setError(null);
    void decideContradiction(locale, projectId, item.id, status)
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /** خانةٌ من سياق الطرف — **و«غير مذكور» تُقال ولا تُترك فراغًا**. */
  const line = (label: string, value: string | number | null) => (
    <div className="metric-label">
      {label}: {value === null || value === "" ? t("synthesis.notRecorded") : value}
    </div>
  );

  const sideCard = (side: ContradictionSide, item: Contradiction) => (
    <div className="card" key={`${item.id}-${side.side}`} style={{ flex: "1 1 260px" }}>
      <strong>{side.title}</strong>
      <p style={{ marginBlock: 6 }}>{side.result_ar}</p>
      <div className="metric-label">
        {side.direction_label_ar} · {side.significance_label_ar}
      </div>
      {line(t("synthesis.dimCountry"), side.country_ar)}
      {line(t("synthesis.dimPopulation"), side.population_ar)}
      {line(t("synthesis.dimMethod"), side.method_ar)}
      {line(t("synthesis.dimMeasurement"), side.measurement_ar)}
      {line(t("synthesis.dimPeriod"), side.period_year)}
      <div className="metric-label">{t(`synthesis.scope_${side.evidence_scope}`)}</div>
    </div>
  );

  const items = data?.contradictions ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("synthesis.contradictionsTitle")}</h1>
      <p className="metric-label">{t("synthesis.contradictionsMeaning")}</p>

      <nav aria-label={t("synthesis.tabsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/themes`}>
              {t("synthesis.themesTitle")}
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
        <p data-testid="contradictions-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="contradictions-failed" style={{ color: "var(--muted)" }}>
          {t("synthesis.loadFailedNote")}
        </p>
      ) : items.length === 0 ? (
        <p data-testid="contradictions-empty" style={{ color: "var(--muted)" }}>
          {t("synthesis.contradictionsEmpty")}
        </p>
      ) : (
        <>
          <p className="metric-label">{data?.note_ar}</p>
          <div style={{ display: "grid", gap: 12, marginBlockStart: "var(--space)" }}>
            {items.map((item) => (
              <article className="card" key={item.id}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span className="chip chip-stage">{item.conflict_label_ar}</span>
                  <span className="chip chip-muted">{item.status_label_ar}</span>
                  {item.context_divergence_labels_ar.map((name) => (
                    <span className="chip chip-muted" key={name}>
                      {name}
                    </span>
                  ))}
                </div>

                <strong style={{ display: "block", marginBlockStart: 6 }}>
                  {item.construct_a_ar}
                </strong>
                <p style={{ marginBlock: 6 }}>{item.relationship_ar}</p>

                {/* **الطرفان جنبًا إلى جنب** — تعارضٌ يُعرض بطرفٍ واحد يجعل
                    الثاني باطلًا بالسكوت عنه. */}
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  {item.sides.map((side) => sideCard(side, item))}
                </div>

                {/* **السياق أنفع من كلمة «تتعارضان».** */}
                {item.context_explanation_ar ? (
                  <p style={{ marginBlockStart: 8 }}>{item.context_explanation_ar}</p>
                ) : null}

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
                  {DECISIONS.map((status) => (
                    <button
                      key={status}
                      type="button"
                      className={item.status === status ? "chip chip-stage" : "chip chip-muted"}
                      aria-label={`${t(DECISION_LABEL[status])}: ${item.construct_a_ar}`}
                      aria-pressed={item.status === status}
                      disabled={busy === item.id || item.status === status}
                      onClick={() => decide(item, status)}
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
    </>
  );
}
