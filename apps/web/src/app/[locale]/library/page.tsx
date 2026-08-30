"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مكتبة الأدلة (§14).
 *
 * حالة الوصول تُعرض بجانب كل مصدر لأنها تحدد ما يجوز الاستشهاد به: مصدر
 * بيانات وصفية فقط لا يجوز اقتطاف نص منه (§14.5)، والواجهة تقول ذلك بدل
 * أن تتركه مفاجأة عند المحاولة.
 */
interface Source {
  id: string;
  doi: string | null;
  title: string;
  publication_year: number | null;
  journal_name: string | null;
  retraction_status: string;
  access_state: string;
  last_verified_at: string | null;
  registry: string | null;
  can_carry_excerpt: boolean;
}

const RETRACTION_COLOR: Record<string, string> = {
  retracted: "#b3261e",
  expression_of_concern: "#b3261e",
  correction: "var(--athera-gold)",
  unknown: "var(--muted)",
  none: "var(--athera-teal)",
};

export default function LibraryPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [sources, setSources] = useState<Source[]>([]);
  const [doi, setDoi] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<Source[]>("/api/v1/sources", { locale })
      .then(setSources)
      .catch(() => setSources([]));
  }, [locale]);

  async function importDoi(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const source = await apiFetch<Source>("/api/v1/sources/import", {
        method: "POST",
        locale,
        body: JSON.stringify({ doi }),
      });
      setSources([source, ...sources]);
      setDoi("");
    } catch (err) {
      // §14.5 / TC-02 — الرسالة تشرح أنه لن يُنشأ بديل، لا مجرد «فشل».
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("library.notFound"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>{t("library.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("library.subtitle")}</p>

      <form className="form" onSubmit={importDoi} style={{ maxInlineSize: 480 }}>
        <label>
          {t("library.importByDoi")}
          <input
            value={doi}
            onChange={(e) => setDoi(e.target.value)}
            placeholder={t("library.doiPlaceholder")}
            dir="ltr"
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={busy}>
          {busy ? t("app.loading") : t("library.import")}
        </button>
      </form>

      {sources.length === 0 ? (
        <p style={{ color: "var(--muted)", marginBlockStart: "var(--space)" }}>{t("library.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8, marginBlockStart: "var(--space)" }}>
        {sources.map((source) => (
          <article className="card" key={source.id}>
            <strong>{source.title}</strong>
            <div className="metric-label" style={{ marginBlockStart: 4 }} dir="ltr">
              {source.doi ?? "—"} · {source.publication_year ?? "—"} · {source.journal_name ?? "—"}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBlockStart: 8, fontSize: 13 }}>
              <span>
                {t("library.accessState")}: {t(`library.access.${source.access_state}`)}
              </span>
              <span style={{ color: RETRACTION_COLOR[source.retraction_status] }}>
                {t("library.retraction")}: {t(`library.retractionState.${source.retraction_status}`)}
              </span>
              <span style={{ color: source.can_carry_excerpt ? "var(--athera-teal)" : "var(--muted)" }}>
                {source.can_carry_excerpt ? t("library.canQuote") : t("library.cannotQuote")}
              </span>
            </div>
            {source.last_verified_at ? (
              <div className="metric-label">
                {t("library.lastVerified")}: {new Date(source.last_verified_at).toLocaleString(locale)}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}
