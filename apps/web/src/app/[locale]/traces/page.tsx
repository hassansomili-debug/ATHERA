"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/** §38.5 — الأثر: تشغيلة، أدواتها، نماذجها، حواجزها، تكلفتها. */
interface TraceSummary {
  trace_id: string | null;
  agent_key: string;
  status: string;
  started_at: string;
  blocked_reason: string | null;
}

const STATUS_KEY: Record<string, string> = {
  completed: "traces.completed",
  blocked: "traces.blocked",
  failed: "traces.failed",
  running: "traces.running",
};

export default function TracesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [rows, setRows] = useState<TraceSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TraceSummary[]>("/api/v1/traces", { locale })
      .then(setRows)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale, t]);

  return (
    <>
      <h1>{t("traces.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("traces.subtitle")}</p>
      {error ? <p className="error">{error}</p> : null}
      {rows.length === 0 ? <p style={{ color: "var(--muted)" }}>{t("traces.empty")}</p> : null}

      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((row, index) => (
          <article className="card" key={`${row.trace_id ?? "none"}-${index}`}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{row.agent_key}</strong>
              <span
                style={{
                  fontSize: 13,
                  color: row.status === "blocked" ? "#b3261e" : "var(--muted)",
                  fontWeight: row.status === "blocked" ? 600 : 400,
                }}
              >
                {t(STATUS_KEY[row.status] ?? "traces.status")}
              </span>
            </div>
            <div className="metric-label">
              {t("traces.started")}: {new Date(row.started_at).toLocaleString(locale)}
            </div>
            {row.blocked_reason ? (
              <p
                style={{
                  marginBlockStart: 8,
                  paddingInlineStart: 12,
                  borderInlineStart: "3px solid #b3261e",
                  fontSize: 13,
                }}
              >
                {t("traces.blockedNote")} — {row.blocked_reason}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}
