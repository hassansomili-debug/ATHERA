"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * الذكاء الاستباقي (§51).
 *
 * الشاشة تعرض درجتين ولا تجمعهما: قوة الاتجاه تقيس هل الظاهرة حقيقية، وملاءمة
 * الفرصة تقيس هل تستحق أن تُنفَّذ هنا والآن. جمعهما في رقم واحد يخفي الحالة
 * الأخطر — اتجاه قوي جدًّا وفرصة لا تصلح لهذا الباحث.
 *
 * وزرّ «صرّح بالتقديم» يبقى معطّلًا ما دام شرط جاهزية واحد غير محقق؛ ولا
 * يُقدّم شيئًا بنفسه، بل يسجّل فعلًا بشريًّا يصرّح به (§51.5 P14).
 */
interface Condition {
  key: string;
  satisfied: boolean;
  actual: number;
  required: number;
  detail: string;
}

interface TrendStrength {
  trend_id: string;
  trend_key: string;
  status: string;
  evidence_weight: number;
  signal_count: number;
  distinct_sources: number;
  span_days: number;
  ignored_signals: string[];
  conditions: Condition[];
  unmet_conditions: string[];
  is_validated: boolean;
}

interface Card {
  id: string;
  trend_id: string;
  working_title_ar: string;
  central_question_ar: string;
  gap_ar: string;
  gap_confidence: number;
  fit_score: number | null;
  blocking_reasons: string[];
  is_actionable: boolean;
  approved_at: string | null;
  evidence_count: number;
}

interface Pipeline {
  card_id: string;
  current_stage: string;
  stages: { stage: string; label: string; completed: boolean }[];
  unmet_conditions: string[];
  unmet_labels: string[];
  is_ready_for_submission: boolean;
}

export default function TrendsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [cards, setCards] = useState<Card[]>([]);
  const [trends, setTrends] = useState<TrendStrength[]>([]);
  const [pipelines, setPipelines] = useState<Record<string, Pipeline>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  // «لا اتجاهات» و«لا بطاقات» كانتا تُعرضان قبل عودة الطلبين — وشاشةُ رصدٍ
  // تقول «لم أجد شيئًا» وهي لم تسأل بعد تُفهَم حكمًا على الرصد نفسه.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const [cardRows, trendRows] = await Promise.all([
        apiFetch<Card[]>("/api/v1/opportunity-cards", { locale }),
        apiFetch<TrendStrength[]>("/api/v1/trends", { locale }),
      ]);
      setCards(cardRows);
      setTrends(trendRows);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function loadPipeline(cardId: string) {
    setBusyId(cardId);
    setError(null);
    try {
      const result = await apiFetch<Pipeline>(`/api/v1/opportunity-cards/${cardId}/pipeline`, {
        locale,
      });
      setPipelines((prev) => ({ ...prev, [cardId]: result }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  async function approve(cardId: string) {
    setBusyId(cardId);
    setError(null);
    try {
      await apiFetch(`/api/v1/opportunity-cards/${cardId}/approve`, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  async function authorize(cardId: string) {
    setBusyId(cardId);
    setError(null);
    try {
      await apiFetch(`/api/v1/opportunity-cards/${cardId}/authorize-submission`, {
        method: "POST",
        locale,
        body: JSON.stringify({ human_act: true }),
      });
      await loadPipeline(cardId);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("trends.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("trends.subtitle")}</p>
      <p className="provenance-note">{t("trends.evidenceNote")}</p>
      {error ? <p className="error">{error}</p> : null}

      <h2>{t("trends.validatedTrends")}</h2>
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : trends.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("trends.emptyTrends")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {trends.map((trend) => (
          <article className="card" key={trend.trend_id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{trend.trend_key}</strong>
              <span className={trend.is_validated ? "badge-ok" : "metric-label"}>
                {trend.is_validated ? t("trends.validated") : t("trends.candidate")}
              </span>
            </div>
            <p className="metric-label">
              {t("trends.strength")}: {trend.evidence_weight.toFixed(1)} ·{" "}
              {t("trends.signals")}: {trend.signal_count} · {t("trends.sources")}:{" "}
              {trend.distinct_sources} · {t("trends.span")}: {trend.span_days}
            </p>
            <ul style={{ marginBlock: 4, paddingInlineStart: 20 }}>
              {trend.conditions.map((condition) => (
                <li key={condition.key} className={condition.satisfied ? undefined : "error"}>
                  {condition.detail}
                </li>
              ))}
            </ul>
            {trend.ignored_signals.length > 0 ? (
              <p className="provenance-note">
                {t("trends.ignoredSignals")}: {trend.ignored_signals.length}
              </p>
            ) : null}
          </article>
        ))}
      </div>

      <h2>{t("trends.cards")}</h2>
      <p className="provenance-note">{t("trends.twoScoresNote")}</p>
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : cards.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("trends.emptyCards")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {cards.map((card) => {
          const pipeline = pipelines[card.id];
          return (
            <article className="card" key={card.id}>
              <strong>{card.working_title_ar}</strong>
              <p style={{ marginBlock: 4 }}>{card.central_question_ar}</p>
              <p className="metric-label">
                {t("trends.gap")}: {card.gap_ar} ({t("trends.gapConfidence")}:{" "}
                {card.gap_confidence.toFixed(2)}) · {t("trends.evidenceCount")}: {card.evidence_count}
              </p>
              <p className="metric-label">
                {t("trends.fitScore")}:{" "}
                {card.fit_score === null ? t("trends.notComputed") : card.fit_score.toFixed(1)}
              </p>
              {card.blocking_reasons.length > 0 ? (
                <ul style={{ marginBlock: 4, paddingInlineStart: 20 }}>
                  {card.blocking_reasons.map((reason) => (
                    <li key={reason} className="error">
                      {reason}
                    </li>
                  ))}
                </ul>
              ) : null}

              {pipeline ? (
                <div style={{ marginBlockStart: 8 }}>
                  <p className="metric-label">
                    {t("trends.currentStage")}: {pipeline.current_stage}
                  </p>
                  <ol style={{ marginBlock: 4, paddingInlineStart: 20 }}>
                    {pipeline.stages.map((stage) => (
                      <li key={stage.stage} className={stage.completed ? "badge-ok" : undefined}>
                        {stage.stage} — {stage.label}
                      </li>
                    ))}
                  </ol>
                  {pipeline.unmet_labels.length > 0 ? (
                    <ul style={{ marginBlock: 4, paddingInlineStart: 20 }}>
                      {pipeline.unmet_labels.map((label) => (
                        <li key={label} className="error">
                          {label}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              <div style={{ display: "flex", gap: 8, marginBlockStart: 8, flexWrap: "wrap" }}>
                <button type="button" disabled={busyId === card.id} onClick={() => void loadPipeline(card.id)}>
                  {t("trends.showPipeline")}
                </button>
                <button
                  type="button"
                  disabled={busyId === card.id || Boolean(card.approved_at) || !card.is_actionable}
                  onClick={() => void approve(card.id)}
                >
                  {t("trends.approveCard")}
                </button>
                <button
                  type="button"
                  disabled={busyId === card.id || !pipeline?.is_ready_for_submission}
                  onClick={() => void authorize(card.id)}
                >
                  {t("trends.authorizeSubmission")}
                </button>
              </div>
            </article>
          );
        })}
      </div>
      <p className="provenance-note">{t("trends.p14Note")}</p>
    </>
  );
}
