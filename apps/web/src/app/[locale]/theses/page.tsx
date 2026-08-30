"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مكتبة الرسائل (§23).
 *
 * «أساس حق الاستخدام» يُعرض بوصفه ادعاءً سجّله الباحث، لا اعتمادًا: الاعتماد
 * قرار مستقل عند بوابة GT1 (§23.2 مقابل §23.9). الخلط بينهما هو ما يجعل
 * منصةً تظن أنها حصلت على الحقوق لأن أحدهم كتب أنه يملكها.
 */
interface Thesis {
  id: string;
  title: string;
  degree: string;
  defended_on: string | null;
  data_collected_on: string | null;
  rights_basis: string | null;
  parsed_at: string | null;
  sections_extracted: number;
  opportunities_found: number;
}

export default function ThesesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [theses, setTheses] = useState<Thesis[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTheses(await apiFetch<Thesis[]>("/api/v1/theses", { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [locale, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(id: string, action: "parse" | "mine-opportunities") {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/theses/${id}/${action}`, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("theses.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("theses.subtitle")}</p>
      <p className="provenance-note">{t("theses.rightsNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {theses.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("theses.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {theses.map((thesis) => (
          <article className="card" key={thesis.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{thesis.title}</strong>
              <span className="metric-label">
                {t("theses.degree")}: {t(`theses.${thesis.degree === "phd" ? "phd" : "masters"}`)}
              </span>
            </div>

            <div className="metric-label" style={{ marginBlockStart: 6 }}>
              {t("theses.rightsBasis")}:{" "}
              {thesis.rights_basis ? t(`theses.basis.${thesis.rights_basis}`) : t("theses.noRights")}
              {thesis.defended_on ? ` · ${t("theses.defended")}: ${thesis.defended_on}` : ""}
            </div>

            <div className="metric-label">
              {t("theses.sections")}: {thesis.sections_extracted} ·{" "}
              {t("theses.opportunities")}: {thesis.opportunities_found}
            </div>

            <div style={{ display: "flex", gap: 8, marginBlockStart: 12, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => run(thesis.id, "parse")}
                disabled={busyId === thesis.id}
                style={{
                  padding: "8px 16px", border: "1px solid var(--border)",
                  borderRadius: "var(--radius)", background: "transparent",
                  color: "inherit", font: "inherit", cursor: "pointer",
                }}
              >
                {t("theses.parse")}
              </button>
              <button
                type="button"
                onClick={() => run(thesis.id, "mine-opportunities")}
                disabled={busyId === thesis.id || !thesis.parsed_at}
                style={{
                  padding: "8px 16px", border: "none", borderRadius: "var(--radius)",
                  background: "var(--athera-teal)", color: "#fff", font: "inherit",
                  cursor: thesis.parsed_at ? "pointer" : "not-allowed",
                  opacity: thesis.parsed_at ? 1 : 0.5,
                }}
              >
                {t("theses.mine")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
