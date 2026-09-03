"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";

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
/** الحالات التي ما زال فيها عملٌ يجري — وما عداها مستقرّ يُنتظر عنده الباحث. */
const RUNNING: ReadonlySet<string> = new Set(["parsing", "extracting"]);
/** ومئتا استطلاع (نحو ثماني دقائق) حدُّ الانتظار — لا انتظارٌ مفتوح. */
const MAX_POLLS = 200;

const PROCESSING_LABEL: Record<string, string> = {
  not_processed: "library.notProcessed",
  parsing: "library.processing",
  extracting: "library.processing",
  // **انتظارُ الباحث ليس معالجةً جارية.** والقراءة المحلية والاستخراج
  // الحتمي تمّا؛ وما يتوقف الآن هو أن يأذن صاحب المستند. فقولُ «قيد
  // المعالجة» هنا يجعله ينتظر النظام — والنظام ينتظره هو، فلا يتحرّك أحد.
  awaiting_consent: "library.awaitingConsent",
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

  /**
   * **جوابٌ متأخّر لا يمحو جوابًا أحدث منه.**
   *
   * صار للشاشة استطلاعٌ دوري، فصارت قراءتان تجريان معًا: واحدة يطلقها
   * الاستطلاع، وأخرى يطلقها رفعُ ملفٍ للتوّ. ولا ترتيب بين ردَّيهما. فإن
   * وصل ردُّ الاستطلاع — وقد صدر قبل الرفع ولا يعرف بالملف — **بعد** ردّ
   * الرفع، حلّت القائمة الأقدم محلّ الأحدث: يرفع الباحث ملفه، يرى «تم
   * الحفظ»، ثم لا يجد الملف في مكتبته. وإن كان في المكتبة ملفٌ عالق في
   * حالٍ جارية بقي الاستطلاع دائرًا فتكرّر الأمر بلا انقطاع.
   *
   * فلكلّ قراءة رقمُها، ولا يُعرض إلا ردّ أحدثها. والقراءة الأحدث تصدر بعد
   * الرفع دائمًا، فترى ما رُفع.
   */
  const latest = useRef(0);
  const loadFiles = useCallback(() => {
    const ticket = (latest.current += 1);
    apiFetch<LibraryFile[]>("/api/v1/files", { locale })
      .then((next) => { if (ticket === latest.current) setFiles(next); })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale]);

  /**
   * **المعالجة تجري، والبطاقة واقفة.**
   *
   * الحال تُقرأ مرّة واحدة عند فتح الشاشة ومرّة بعد ضغط «معالجة المستند»،
   * ثم لا تُقرأ أبدًا. فالخادم يمضي: يقرأ، يستخرج، ثم يقف عند حدّ الإذن —
   * والشاشة تبقى تقول «قيد المعالجة» إلى أن يعيد الباحث تحميلها بنفسه.
   * وهو لا يعرف أن عليه ذلك، ولا شيء في الشاشة يقوله له. فيظن أن مستنده
   * عالق، أو ينتظر شيئًا لا يأتي — بينما المنتج ينتظره هو.
   *
   * **والاستطلاع يقف عند حالٍ مستقرّة.** ما دام في المكتبة ملفٌ يُقرأ أو
   * يُستخرَج منه، تُعاد القراءة؛ فإذا لم يبقَ شيءٌ جارٍ توقّفت — فلا قصفٌ
   * للـAPI بعد انتهاء العمل.
   */
  const polls = useRef(0);
  useEffect(() => {
    if (!files.some((file) => RUNNING.has(file.processing_status))) return;
    // **وحدٌّ للانتظار.** تشغيلةٌ ماتت في منتصفها تترك حالًا «جارية» لا
    // تنتهي أبدًا — ولولا حدٌّ لظلّت الشاشة تسأل عنها ما دامت مفتوحة.
    if (polls.current >= MAX_POLLS) return;
    const timer = window.setTimeout(() => {
      polls.current += 1;
      loadFiles();
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [files, loadFiles]);

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
                {/*
                  الحال القانونية بجانب نصّها المترجَم.

                  والنصّ للإنسان، والسمة للآلة: فحصٌ يطابق نصًّا مترجَمًا
                  يسقط بأول تحسينٍ للصياغة، أو يقرأ نصَّ شاشةٍ أخرى ويظنّه
                  هذه. وليس فيها سرٌّ ولا معرّف — الحال نفسها لا غير.
                */}
                <div className="metric-label" data-processing-state={file.processing_status}>
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
                  {/* **إلى رسالته هو، لا إلى قائمةٍ يبحث فيها.** المعرّف
                      معروفٌ هنا، فالرابط يقصده — ولا يُطلب من الباحث أن
                      يتعرّف على مستنده بين بطاقاتٍ متشابهة. */}
                  {file.thesis_id ? (
                    <a href={`/${locale}/theses/${file.thesis_id}/review`}>
                      {t("library.openReview")}
                    </a>
                  ) : null}
                  {/* **المعرفة المعتمَدة كان لا يُسأل عنها.** الباحث يعالج
                      مستنده ويعتمد منه معلومات، ثم يفتح بُبريفا AI فلا يجد
                      طريقًا إليه: المرفق يقبل رفعًا جديدًا وحده، والنسخة
                      الجديدة غير مقروءة — فما اعتُمد لا يُبلَغ إليه أبدًا.
                      فمن هنا يُسأل عن هذا المستند بعينه. */}
                  {file.processing_status === "awaiting_review"
                    || file.processing_status === "completed" ? (
                    <a href={`/${locale}/ai?file=${file.id}`}>{t("library.askAi")}</a>
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
        {error ? (
          <p className="error" role="alert" data-testid="library-source-error">
            {error}
          </p>
        ) : null}
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
