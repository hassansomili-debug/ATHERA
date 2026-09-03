"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * خريطة فرص النشر (§23.6، §23.7، §23.9).
 *
 * ثلاثة أشياء تُعرض معًا عمدًا: الجاهزية، والتداخل، وحالة بوابة GT1. عرض
 * الجاهزية وحدها يوحي بأن الفرصة جاهزة للتقدم — بينما التقدم يحتاج حقوقًا
 * وتأليفًا معتمدَين، وحسمًا لأي تنبيه تجزئة.
 */
interface Opportunity {
  id: string;
  opportunity_kind_label: string;
  paper_kind_label: string;
  working_title: string;
  readiness_score: number | null;
  readiness_outcome_label: string | null;
  salami_alert: boolean;
  status: string;
  rights_approved: boolean;
  authorship_approved: boolean;
}

interface Dimension {
  dimension: string;
  label: string;
  value: number | null;
  status: string;
  exceeds_threshold: boolean;
}

interface Pair {
  left_opportunity_id: string;
  right_opportunity_id: string;
  dimensions: Dimension[];
  exceeded: string[];
  salami_alert: boolean;
}

interface Gate {
  blockers: string[];
  blocker_labels: string[];
  can_be_ready_to_submit: boolean;
}

interface MapResponse {
  thesis_id: string;
  title: string;
  opportunities: Opportunity[];
  overlap: { pairs: Pair[]; alerts: number; note_ar: string; note_en: string };
  gate_summary: Record<string, number>;
}

interface Thesis {
  id: string;
  title: string;
}

export default function OpportunitiesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [theses, setTheses] = useState<Thesis[]>([]);
  const [thesisId, setThesisId] = useState<string | null>(null);
  const [data, setData] = useState<MapResponse | null>(null);
  const [gates, setGates] = useState<Record<string, Gate>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Thesis[]>("/api/v1/theses", { locale })
      .then((rows) => {
        setTheses(rows);
        if (rows.length > 0) setThesisId(rows[0]!.id);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale]);

  const load = useCallback(async () => {
    if (!thesisId) return;
    try {
      const map = await apiFetch<MapResponse>(
        `/api/v1/theses/${thesisId}/publication-map`,
        { locale },
      );
      setData(map);
      const entries = await Promise.all(
        map.opportunities.map(async (opportunity) => {
          const gate = await apiFetch<Gate>(
            `/api/v1/opportunities/${opportunity.id}/gate`,
            { locale },
          );
          return [opportunity.id, gate] as const;
        }),
      );
      setGates(Object.fromEntries(entries));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [locale, thesisId, t]);

  useDeferredLoad(load);

  return (
    <>
      <h1>{t("opportunities.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("opportunities.subtitle")}</p>
      <p className="provenance-note">{t("opportunities.analysisNote")}</p>

      {theses.length > 1 ? (
        <select
          value={thesisId ?? ""}
          onChange={(e) => setThesisId(e.target.value)}
          style={{
            padding: "8px 12px", border: "1px solid var(--border)",
            borderRadius: "var(--radius)", background: "var(--surface)",
            color: "inherit", font: "inherit", marginBlockEnd: "var(--space)",
          }}
        >
          {theses.map((thesis) => (
            <option key={thesis.id} value={thesis.id}>{thesis.title}</option>
          ))}
        </select>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
      {data && data.opportunities.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>{t("opportunities.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {data?.opportunities.map((opportunity) => {
          const gate = gates[opportunity.id];
          return (
            <article className="card" key={opportunity.id}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <strong>{opportunity.working_title}</strong>
                <span className="metric-label">
                  {t(`opportunities.status.${opportunity.status}`)}
                </span>
              </div>

              <div className="metric-label" style={{ marginBlockStart: 6 }}>
                {t("opportunities.kind")}: {opportunity.opportunity_kind_label} ·{" "}
                {t("opportunities.paperKind")}: {opportunity.paper_kind_label}
              </div>

              <div className="metric-label">
                {t("opportunities.readiness")}:{" "}
                {opportunity.readiness_score ?? t("opportunities.notScored")}
                {opportunity.readiness_outcome_label
                  ? ` · ${t("opportunities.outcome")}: ${opportunity.readiness_outcome_label}`
                  : ""}
              </div>

              {opportunity.salami_alert ? (
                <p
                  style={{
                    marginBlockStart: 8, paddingInlineStart: 12,
                    borderInlineStart: "3px solid #b3261e", fontSize: 13, color: "#b3261e",
                  }}
                >
                  {t("opportunities.salami")}
                </p>
              ) : null}

              {gate ? (
                <div
                  style={{
                    marginBlockStart: 8, paddingInlineStart: 12,
                    borderInlineStart: `3px solid ${
                      gate.can_be_ready_to_submit ? "var(--athera-teal)" : "var(--athera-gold)"
                    }`,
                    fontSize: 13,
                  }}
                >
                  {t("opportunities.gate")}:{" "}
                  {gate.can_be_ready_to_submit
                    ? t("opportunities.gateOpen")
                    : t("opportunities.gateBlocked")}
                  {gate.blocker_labels.length > 0 ? (
                    <ul style={{ margin: "6px 0 0", paddingInlineStart: 18, color: "var(--muted)" }}>
                      {gate.blocker_labels.map((label) => (
                        <li key={label}>{label}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      {data && data.overlap.pairs.length > 0 ? (
        <>
          <h2 style={{ marginBlockStart: "calc(var(--space) * 2)" }}>
            {t("opportunities.overlapTitle")}
          </h2>
          <p className="metric-label">
            {t("opportunities.overlapAlerts")}: {data.overlap.alerts}
          </p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", fontSize: 13, minInlineSize: "100%" }}>
              <tbody>
                {data.overlap.pairs.map((pair, index) => (
                  <tr
                    key={`${pair.left_opportunity_id}-${pair.right_opportunity_id}-${index}`}
                    style={{ borderBlockEnd: "1px solid var(--border)" }}
                  >
                    <td style={{ padding: "8px 12px", whiteSpace: "nowrap" }}>
                      {pair.salami_alert ? (
                        <span style={{ color: "#b3261e", fontWeight: 600 }}>
                          {t("opportunities.salami")}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    {pair.dimensions.map((dimension) => (
                      <td
                        key={dimension.dimension}
                        style={{
                          padding: "8px 12px",
                          color: dimension.exceeds_threshold ? "#b3261e" : "var(--muted)",
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {dimension.label}:{" "}
                        {dimension.status === "not_computed"
                          ? t("opportunities.notComputed")
                          : dimension.value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="provenance-note">{t("opportunities.overlapNote")}</p>
        </>
      ) : null}
    </>
  );
}
