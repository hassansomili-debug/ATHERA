"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * سجل الادعاءات (§14.4).
 *
 * الفجوة والدليل المناقض معروضان في المقدمة لا في الحواشي: سجل يخفي
 * المناقض أسوأ من سجل بلا أدلة.
 */
interface ClaimEvidence {
  status: string;
  direct: number;
  partial: number;
  contextual: number;
  contradictory: number;
  unresolved_contradictions: number;
  retracted_sources: number;
  has_evidence_gap: boolean;
  can_be_final: boolean;
}

interface ClaimRow {
  id: string;
  text: string;
  claim_type: string;
  section: string | null;
  status: string;
  evidence: ClaimEvidence;
}

const STATUS_COLOR: Record<string, string> = {
  evidence_gap: "#b3261e",
  contradicted: "#b3261e",
  supported: "var(--athera-teal)",
  final: "var(--athera-teal)",
  draft: "var(--muted)",
};

export default function ClaimsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  // «لا ادعاءات مسجّلة» كانت تُعرض قبل عودة الطلب — وسجلٌّ يُقال عنه فارغٌ
  // وهو لم يُقرأ بعدُ دعوى لم تُفحص، لا حالٌ للسجل.
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiFetch<ClaimRow[]>("/api/v1/claims", { locale })
      .then(setClaims)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      // في دالّة رد نداء لا في جسم التأثير — `react-hooks/set-state-in-effect`.
      .finally(() => setLoaded(true));
  }, [locale, t]);

  return (
    <>
      <h1>{t("claims.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("claims.subtitle")}</p>
      <p className="provenance-note">{t("claims.gapNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : claims.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("claims.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {claims.map((claim) => (
          <article className="card" key={claim.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{claim.text}</strong>
              <span style={{ color: STATUS_COLOR[claim.status], fontSize: 13, fontWeight: 600 }}>
                {t(`claims.${claim.status === "evidence_gap" ? "gap" : claim.status}`)}
              </span>
            </div>
            <div className="metric-label" style={{ marginBlockStart: 6 }}>
              {t("claims.type")}: {claim.claim_type}
              {claim.section ? ` · ${claim.section}` : ""}
            </div>
            <div className="metric-label">
              {t("claims.support")}: {t("claims.level.direct")} {claim.evidence.direct} ·{" "}
              {t("claims.level.partial")} {claim.evidence.partial} ·{" "}
              {t("claims.level.contextual")} {claim.evidence.contextual} ·{" "}
              <span style={{ color: claim.evidence.contradictory ? "#b3261e" : undefined }}>
                {t("claims.level.contradictory")} {claim.evidence.contradictory}
              </span>
            </div>
            {claim.evidence.unresolved_contradictions > 0 ? (
              <p
                style={{
                  marginBlockStart: 8,
                  paddingInlineStart: 12,
                  borderInlineStart: "3px solid #b3261e",
                  fontSize: 13,
                }}
              >
                {t("claims.contradictionNote")}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}
