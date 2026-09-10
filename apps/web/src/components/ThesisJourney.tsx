"use client";

import { useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { type Commit, useDeferredLoad } from "@/lib/useDeferredLoad";

/**
 * رحلةُ الرسالة إلى ورقة | The thesis-to-paper journey.
 *
 * **ولا نسبةَ مئوية هنا إطلاقًا.** «٦٠٪ مكتمل» رقمٌ بلا قياسٍ خلفه يقرؤه
 * الباحثُ وعدًا. فالشاشةُ تعرض الحالَ التي يقولها الخادم، والخطوةَ التي
 * تقابلها — لا أكثر. والخريطةُ أدناه صريحةٌ ومقروءة، لا حسابَ تقدّمٍ فيها.
 *
 * **ولا مفرداتِ نظامٍ في وجه الباحث**: لا «مرشّح واقعة» ولا «تنقيب» ولا
 * «استخراج» ولا «كنسيّ». الباحثُ يقرأ عن رسالته وورقته وحدهما.
 */

const STEP_KEYS = [
  "analysis",
  "opportunities",
  "rights",
  "build",
  "literature",
  "studio",
] as const;

/**
 * أيُّ خطوةٍ تقابل كلَّ حال — **خريطةٌ صريحة لا حسابُ نسبة**.
 *
 * والحالُ مصدرُها الخادم. وحالٌ لا تُعرف هنا تُعرض عند الخطوة الأولى ولا
 * تكسر الشاشة: العقدُ قد يسبق الواجهة، وسقوطُ الشاشة على حالٍ جديدة أسوأ
 * من عرضها في غير موضعها.
 */
const STEP_OF_STATE: Record<string, number> = {
  uploaded: 0,
  extracting: 0,
  analysed: 0,
  failed: 0,
  opportunities_ready: 1,
  researcher_decision_required: 1,
  overlap_review_required: 2,
  rights_required: 2,
  awaiting_ai_consent: 3,
  project_created: 3,
  thread_ready: 3,
  outline_ready: 3,
  manuscript_created: 3,
  drafting: 3,
  literature_pending: 4,
  draft_ready: 5,
  ready_for_paper_studio: 5,
};

interface Journey {
  thesis_id: string;
  state: string;
  blocking_reasons: string[];
  can_build_paper: boolean;
  opportunities: number;
  states: string[];
}

interface Opportunity {
  id: string;
  working_title: string;
  paper_kind_label: string;
  research_question_ar: string | null;
  readiness_outcome_label: string | null;
  salami_alert: boolean;
  provenance_count: number;
}

interface BuildResult {
  manuscript_id: string;
  state: string;
}

export function ThesisJourney({
  thesisId,
  locale,
  messages,
}: {
  thesisId: string;
  locale: Locale;
  messages: Messages;
}) {
  const t = translator(messages);

  const [journey, setJourney] = useState<Journey | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [manuscriptId, setManuscriptId] = useState<string | null>(null);

  const load = useCallback(async (commit: Commit) => {
    try {
      const state = await apiFetch<Journey>(
        `/api/v1/theses/${thesisId}/journey`, { locale });
      commit(() => setJourney(state));
      if (state.opportunities > 0) {
        const map = await apiFetch<{ opportunities: Opportunity[] }>(
          `/api/v1/theses/${thesisId}/publication-map`, { locale });
        commit(() => setOpportunities(map.opportunities ?? []));
      }
    } catch (err) {
      commit(() => setError(
        err instanceof AtheraApiError
          ? err.localized(locale)
          : t("common.loadFailed")));
    }
  }, [locale, thesisId, t]);

  const refresh = useDeferredLoad(load);

  async function build(opportunityId: string) {
    setBusy(opportunityId);
    setError(null);
    try {
      const result = await apiFetch<BuildResult>(
        `/api/v1/theses/${thesisId}/opportunities/${opportunityId}/build-paper`,
        { method: "POST", locale });
      setManuscriptId(result.manuscript_id);
      await refresh();
    } catch (err) {
      setError(err instanceof AtheraApiError
        ? err.localized(locale)
        : t("common.loadFailed"));
    } finally {
      setBusy(null);
    }
  }

  const current = journey ? (STEP_OF_STATE[journey.state] ?? 0) : 0;
  const canBuild = journey?.can_build_paper === true;

  return (
    <section
      className="card"
      data-testid="thesis-journey"
      style={{ display: "grid", gap: 12 }}
    >
      <div>
        <strong style={{ fontSize: 17 }}>{t("journey.title")}</strong>
        <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>
          {t("journey.subtitle")}
        </p>
      </div>

      {/* ── الخطواتُ الست: موضعٌ يُقال، لا شريطُ تقدّمٍ يُحسب ── */}
      <ol
        data-testid="journey-steps"
        style={{
          display: "flex", gap: 8, flexWrap: "wrap", listStyle: "none",
          padding: 0, margin: 0,
        }}
      >
        {STEP_KEYS.map((key, index) => {
          const status =
            index < current ? "done" : index === current ? "current" : "waiting";
          return (
            <li
              key={key}
              data-testid={`journey-step-${key}`}
              data-status={status}
              style={{
                padding: "6px 12px",
                borderRadius: "var(--radius)",
                border: "1px solid var(--border, #ddd)",
                fontWeight: status === "current" ? 600 : 400,
                opacity: status === "waiting" ? 0.55 : 1,
              }}
            >
              {t(`journey.steps.${key}`)}
              <span className="metric-label" style={{ display: "block", fontSize: 12 }}>
                {t(`journey.${status}`)}
              </span>
            </li>
          );
        })}
      </ol>

      {/* ── ما ينتظر الآن: رمزُ الخادم يُترجَم إلى لغة الباحث ── */}
      {journey && journey.blocking_reasons.length > 0 ? (
        <ul
          data-testid="journey-blocked"
          className="metric-label"
          style={{ margin: 0, paddingInlineStart: 18 }}
        >
          {journey.blocking_reasons.map((reason) => (
            <li key={reason}>{t(`journey.blocked.${reason}`)}</li>
          ))}
        </ul>
      ) : null}

      {error ? (
        <p data-testid="journey-error" className="metric-label">{error}</p>
      ) : null}

      {opportunities.length === 0 ? (
        <p data-testid="journey-empty" className="metric-label">
          {t("journey.empty")}
        </p>
      ) : null}

      {/* ── بطاقاتُ الأوراق المقترحة ── */}
      {opportunities.map((opportunity) => (
        <article
          key={opportunity.id}
          className="card"
          data-testid={`opportunity-card-${opportunity.id}`}
          style={{ display: "grid", gap: 6 }}
        >
          <strong>{opportunity.working_title}</strong>

          <span className="metric-label">
            {t("journey.paperType")}: {opportunity.paper_kind_label}
          </span>

          <span className="metric-label" data-testid="opportunity-contribution">
            {t("journey.contribution")}:{" "}
            {opportunity.research_question_ar ?? t("journey.noContribution")}
          </span>

          <span className="metric-label">
            {t("journey.evidenceReadiness")}:{" "}
            {opportunity.readiness_outcome_label ?? t("journey.notScored")}
          </span>

          {/* **عددُ ما هو مُسنَد فعلًا** — لا درجةً ولا نسبة. */}
          <span className="metric-label" data-testid="opportunity-provenance">
            {opportunity.provenance_count} {t("journey.provenance")}
          </span>

          {opportunity.salami_alert ? (
            <span className="metric-label" data-testid="opportunity-overlap">
              {t("journey.overlapWarning")}
            </span>
          ) : null}

          {/* **والمقترحُ يُعلن أنّه مقترحُ آلة** — لا يُقرأ حكمًا علميًّا. */}
          <p
            className="provenance-note"
            data-testid="opportunity-ai-notice"
            style={{ margin: 0 }}
          >
            {t("journey.aiNotice")}
          </p>

          <div
            style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 6 }}
          >
            {manuscriptId ? (
              <a
                data-testid="journey-open-studio"
                href={`/${locale}/manuscripts/${manuscriptId}`}
                style={{
                  padding: "8px 16px", borderRadius: "var(--radius)",
                  background: "var(--athera-teal)", color: "#fff",
                  textDecoration: "none",
                }}
              >
                {t("journey.openStudio")}
              </a>
            ) : (
              <button
                type="button"
                data-testid="journey-build-paper"
                disabled={!canBuild || busy === opportunity.id}
                onClick={() => void build(opportunity.id)}
                style={{
                  padding: "8px 16px", borderRadius: "var(--radius)", border: "none",
                  background: "var(--athera-aqua, var(--athera-teal))",
                  color: "#04302c", font: "inherit", fontWeight: 600,
                  cursor: canBuild ? "pointer" : "not-allowed",
                  opacity: canBuild ? 1 : 0.5,
                }}
              >
                {busy === opportunity.id
                  ? t("journey.building")
                  : t("journey.buildCta")}
              </button>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}
