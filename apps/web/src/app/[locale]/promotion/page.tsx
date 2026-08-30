"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مركز الترقية (§11، §27.2).
 *
 * لا نسبة جاهزية واحدة: نسبة 90٪ تخفي شرطًا حاجبًا واحدًا يوقف الملف كله.
 * المعروض عدّادات صريحة وتفصيل كل شرط بحالته ومصدره.
 */
interface RuleEvaluation {
  rule_id: string;
  rule_type: string;
  rule_key: string;
  status: string;
  required: unknown;
  actual: unknown;
  is_blocking: boolean;
  explanation: string;
}

interface Case {
  units_total: number | null;
  units_computable: boolean;
  rules_met: number;
  rules_blocking: number;
  rules_needing_verification: number;
  is_ready: boolean;
  evaluations: RuleEvaluation[];
}

const STATUS_COLOR: Record<string, string> = {
  met: "var(--athera-teal)",
  not_met: "#b3261e",
  needs_institutional_verification: "var(--athera-gold)",
  not_applicable: "var(--muted)",
};

export default function PromotionPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<Case | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Case>("/api/v1/promotion/case", { locale })
      .then(setData)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale, t]);

  return (
    <>
      <h1>{t("promotion.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("promotion.subtitle")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!data && !error ? <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p> : null}

      {data ? (
        <>
          <section className="grid">
            <article className="card">
              <div className="metric-label">{t("promotion.unitsTotal")}</div>
              <div className="metric-value">
                {data.units_computable && data.units_total !== null
                  ? data.units_total
                  : t("promotion.unitsUnknown")}
              </div>
            </article>
            <article className="card">
              <div className="metric-label">{t("promotion.rulesMet")}</div>
              <div className="metric-value">{data.rules_met}</div>
            </article>
            <article className="card">
              <div className="metric-label">{t("promotion.rulesBlocking")}</div>
              <div className="metric-value" style={{ color: data.rules_blocking ? "#b3261e" : undefined }}>
                {data.rules_blocking}
              </div>
            </article>
            <article className="card">
              <div className="metric-label">{t("promotion.rulesNeedingVerification")}</div>
              <div
                className="metric-value"
                style={{ color: data.rules_needing_verification ? "var(--athera-gold)" : undefined }}
              >
                {data.rules_needing_verification}
              </div>
            </article>
          </section>

          <p className="provenance-note">
            {data.is_ready ? t("promotion.ready") : t("promotion.notReady")} — {t("promotion.blockingNote")}
          </p>

          <div style={{ display: "grid", gap: 8, marginBlockStart: "var(--space)" }}>
            {data.evaluations.map((evaluation) => (
              <article className="card" key={evaluation.rule_id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{evaluation.rule_key}</strong>
                  <span style={{ color: STATUS_COLOR[evaluation.status], fontSize: 13, fontWeight: 600 }}>
                    {t(`promotion.status.${evaluation.status}`)}
                  </span>
                </div>
                <p style={{ marginBlock: 6, fontSize: 14 }}>{evaluation.explanation}</p>
                {evaluation.required !== null && evaluation.required !== undefined ? (
                  <div className="metric-label">
                    {t("promotion.required")}: {String(evaluation.required)} · {t("promotion.actual")}:{" "}
                    {String(evaluation.actual)}
                  </div>
                ) : null}
              </article>
            ))}
          </div>

          <p className="provenance-note">{t("promotion.verificationNote")}</p>
        </>
      ) : null}
    </>
  );
}
