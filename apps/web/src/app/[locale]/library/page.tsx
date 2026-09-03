"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import type { LibraryFile } from "@/lib/library";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { FileUpload } from "@/components/FileUpload";

/**
 * مكتبة الباحث (§14).
 *
 * **وكانت لا تعرض ملفات صاحبها إطلاقًا.** تعرض المصادر المستوردة بـDOI
 * وحدها؛ فمن رفع رسالته لم يجد لها أثرًا، وكان عليه أن يحفظ معرّفها بنفسه.
 * والملفات الآن أولًا — وهي ما يملكه الباحث فعلًا — ثم المصادر بعدها.
 *
 * حالة الوصول تُعرض بجانب كل مصدر لأنها تحدد ما يجوز الاستشهاد به: مصدر
 * بيانات وصفية فقط لا يجوز اقتطاف نص منه (§14.5)، والواجهة تقول ذلك بدل
 * أن تتركه مفاجأة عند المحاولة.
 */
/** أنواع يقرؤها المفكِّك — والزرّ لا يُعرض على ما لا يُقرأ. */
const PARSEABLE = /\.(pdf|docx|txt|md)$/i;


/** حال المعالجة نصًّا — **لا لونًا وحده**، ولا وعدًا بما لم يقع. */
const PROCESSING_LABEL: Record<string, string> = {
  not_processed: "library.notProcessed",
  parsing: "library.processing",
  extracting: "library.processing",
  awaiting_consent: "library.processing",
  awaiting_review: "library.needsReview",
  completed: "library.processed",
  extract_failed: "library.failedState",
  parse_failed: "library.failedState",
};

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

  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [processing, setProcessing] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [doi, setDoi] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadFiles = useCallback(() => {
    apiFetch<LibraryFile[]>("/api/v1/files", { locale })
      .then(setFiles)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale]);

  useEffect(() => {
    loadFiles();
    apiFetch<Source[]>("/api/v1/sources", { locale })
      .then(setSources)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale, loadFiles]);

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
      <div style={{ marginBlock: "18px 24px" }}>
        <FileUpload locale={locale} messages={getMessages(locale)} onUploaded={loadFiles} />
      </div>

      {/* ── ملفاتي: ما يملكه الباحث فعلًا ── */}
      <section>
        <h2>{t("library.myFiles")}</h2>
        <p style={{ color: "var(--muted)" }}>{t("library.filesNote")}</p>
        {files.length === 0 ? (
          <p>{t("library.noFiles")}</p>
        ) : (
          <div className="cards">
            {files.map((file) => (
              <article className="card" key={file.id}>
                <h3>{file.original_filename}</h3>
                <div className="metric-label">
                  {file.content_type} · {Math.max(1, Math.round(file.size_bytes / 1024))} KB ·{" "}
                  {new Date(file.created_at).toLocaleDateString(locale)}
                </div>
                {/* الحالة نصًّا صريحًا — ولا يُقال «حُلِّل» لملفٍ لم يُقرأ. */}
                <div className="metric-label">
                  {t(PROCESSING_LABEL[file.processing_status] ?? "library.notProcessed")}
                  {file.candidates > 0
                    ? ` · ${file.candidates} ${t("library.candidatesCount")} · ${file.reviewed} ${t("library.reviewedCount")}`
                    : ""}
                </div>
                <div style={{ display: "flex", gap: 12, marginBlockStart: 8 }}>
                  {/* المعالجة تُعرض لما يمكن قراءته وحده — ووعدٌ لا يُنجَز
                      أسوأ من غياب الزرّ. */}
                  {file.processing_status === "not_processed" ? (
                    PARSEABLE.test(file.original_filename) ? (
                      <button
                        type="button"
                        disabled={processing === file.id}
                        onClick={() => {
                          setProcessing(file.id);
                          setError(null);
                          void apiFetch(`/api/v1/theses/process-file/${file.id}`, {
                            method: "POST", locale,
                          })
                            .then(() => loadFiles())
                            .catch((err) => setError(
                              err instanceof AtheraApiError
                                ? err.localized(locale) : t("common.loadFailed")))
                            .finally(() => setProcessing(null));
                        }}
                      >
                        {processing === file.id
                          ? t("library.processing2") : t("library.processDoc")}
                      </button>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>{t("library.cannotProcess")}</span>
                    )
                  ) : null}
                  {file.thesis_id ? (
                    <a href={`/${locale}/theses`}>{t("library.openReview")}</a>
                  ) : null}
                  <a href={`/${locale}/library`} onClick={(event) => {
                    event.preventDefault();
                    void apiFetch<{ url: string }>(`/api/v1/files/${file.id}/download`, { locale })
                      .then((r) => window.open(r.url, "_blank", "noopener"))
                      .catch((err) => setError(
                        err instanceof AtheraApiError
                          ? err.localized(locale) : t("common.loadFailed")));
                  }}>{t("library.downloadFile")}</a>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <h2>{t("library.sourcesTab")}</h2>

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
