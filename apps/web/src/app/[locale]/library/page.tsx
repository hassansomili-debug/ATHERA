"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import {
  LIBRARY_MAX_FETCH,
  LIBRARY_PAGE,
  listLibraryFilePage,
  type LibraryFile,
} from "@/lib/library";
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
  // المعالجة» هنا يجعله ينتظر النظام — والنظام ينتظره هو، فلا يتحرك أحد.
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
  /**
   * **قائمةٌ لم تصل ليست مكتبةً خالية.**
   *
   * كانت الشاشة تعرض «لم ترفع ملفًا بعد» ما دامت `files` فارغة — وهي فارغة
   * قبل وصول أول ردّ. فباحثٌ يملك عشرين ملفًا يُقال له إنه لا يملك شيئًا،
   * لا لأن مكتبته خالية بل لأنها لم تُقرأ بعد. وهما حالان مختلفتان تمامًا،
   * وخلطهما كذبٌ يراه المستخدم كذبًا.
   */
  const [filesLoad, setFilesLoad] = useState<"loading" | "ready" | "failed">("loading");
  const [processing, setProcessing] = useState<string | null>(null);
  /**
   * **ما طُلبت معالجته يُراقَب حتى تتحرّك حاله.**
   *
   * كان الاستطلاع يدور ما دام في القائمة ملفٌ في حالٍ **جارية**. وطلبُ
   * المعالجة يُنشئ التشغيلة في مهمّةٍ خلفية، فالقراءة التي تلي الطلب قد
   * تسبقها فتعود بـ`not_processed` — وهي ليست حالًا جارية، فلا يدور
   * الاستطلاع، ولا تُقرأ الحال ثانيةً أبدًا. فتبقى البطاقة تقول «لم
   * تُعالَج بعد» وقد بدأت معالجتها فعلًا، إلى أن يعيد الباحث التحميل
   * بنفسه — وهو لا يعرف أن عليه ذلك. وهذا ما سقطت عليه رحلة القبول: حالٌ
   * ثابتة على `not_processed` ثلاث دقائق كاملة.
   *
   * فالطلب نفسه سببٌ للمراقبة، لا الحالُ المعروضة وحدها.
   */
  const requested = useRef<Set<string>>(new Set());
  const [sources, setSources] = useState<Source[]>([]);
  const [doi, setDoi] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  /**
   * **ما بعد الصفحة الأولى لا يضيع بتحديث.**
   *
   * القائمة صارت مرقَّمة، وكل قراءةٍ تُعيد ما طُلب لا أكثر. فلو استُبدلت
   * القائمة كلها بردّ الصفحة الأولى، لأُلغي ما حمّله الباحث بـ«حمّل المزيد»
   * كلّما دار الاستطلاع. فتُقرأ بقدر ما هو معروض (إلى سقف الخادم)، ويبقى
   * ذيلُ ما بعده كما هو. و`shown` مرآةُ آخر ما عُرض فعلًا — تُكتب بعد
   * التصيير لا داخله.
   */
  const shown = useRef<LibraryFile[]>([]);
  useEffect(() => {
    shown.current = files;
  }, [files]);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

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
    const take = Math.min(LIBRARY_MAX_FETCH, Math.max(LIBRARY_PAGE, shown.current.length));
    const tail = shown.current.slice(take);
    listLibraryFilePage(locale, { limit: take })
      .then((page) => {
        const next = page.length < take ? page : page.concat(tail);
        if (ticket === latest.current) setFiles(next);
        if (ticket === latest.current) setFilesLoad("ready");
        // ونهايةُ القائمة لا يقرّرها إلا من بلغها: قراءةٌ لا تشمل الذيل
        // لا تعرف ما بعده، فلا تُبطل زرًّا لم تسأل عنه.
        if (ticket === latest.current && tail.length === 0) setHasMore(page.length === take);
      })
      .catch((err) => {
        if (ticket === latest.current) setFilesLoad("failed");
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
      });
  }, [locale]);

  /**
   * «حمّل المزيد» — والمؤشّر معرّف آخر ملفٍ معروض.
   *
   * ويأخذ رقمه من الترتيب نفسه: لو وصل ردُّ صفحةٍ أولى بعده لكان يمحو ما
   * أُلحق للتوّ، فيضغط الباحث الزرّ ولا يرى شيئًا يزيد.
   */
  const loadMore = useCallback(() => {
    const after = shown.current[shown.current.length - 1]?.id;
    if (!after) return;
    const ticket = (latest.current += 1);
    const base = shown.current;
    setLoadingMore(true);
    listLibraryFilePage(locale, { limit: LIBRARY_PAGE, after })
      .then((page) => {
        if (ticket === latest.current) setFiles(base.concat(page));
        if (ticket === latest.current) setHasMore(page.length === LIBRARY_PAGE);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      .finally(() => setLoadingMore(false));
  }, [locale]);

  /**
   * **الملف الذي رُفع للتوّ يُعرض فورًا.**
   *
   * كان العرض ينتظر قراءةً كاملة للمكتبة بعد الرفع؛ وتلك القراءة هي بعينها
   * ما ثبت بطؤه على حساب فيه ملفات كثيرة. فيرى الباحث «تم الحفظ» ومكتبته
   * خالية من ملفه، ولا شيء يقول له أن ينتظر. وقد سقطت رحلة القبول على ذلك
   * ثلاث مرات: صفر بطاقة ملف بعد رفعٍ نجح.
   *
   * والقيم المعروضة ليست اختلاقًا: الخادم أنشأ صفّ الملف وحده — لا رسالة
   * ولا تشغيلة ولا مرشّح — وهي نفسها ما يردّه المسار لو سُئل عنه الآن.
   * والقراءة تُطلق بعدها فتحلّ الحقيقةُ محلّ التوقّع، ورقمُ الترتيب يُرفع
   * أولًا فلا يمحو الملفَ ردٌّ صدر قبل رفعه.
   */
  const fileUploaded = useCallback((stored: LibraryFile) => {
    latest.current += 1;
    setFiles((previous) => [stored, ...previous.filter((row) => row.id !== stored.id)]);
    setFilesLoad("ready");
    loadFiles();
  }, [loadFiles]);

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
    const watching = files.some(
      (file) => RUNNING.has(file.processing_status)
        || (requested.current.has(file.id) && file.processing_status === "not_processed"),
    );
    if (!watching) return;
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
        <FileUpload locale={locale} messages={getMessages(locale)} onUploaded={fileUploaded} />
      </div>

      {/* ── ملفاتي: ما يملكه الباحث فعلًا ── */}
      <section>
        <h2>{t("library.myFiles")}</h2>
        <p style={{ color: "var(--muted)" }}>{t("library.filesNote")}</p>
        {/*
          الحالات الثلاث تُقال منفصلة: «تُقرأ الآن» غير «لا ملفات» غير
          «تعذّرت القراءة». وجمعُها في نصٍّ واحد يجعل بطء الخادم يبدو
          مكتبةً خالية — وهو أسوأ ما تقوله شاشةٌ لمن يملك ملفاته.
        */}
        {filesLoad === "loading" ? (
          <p data-testid="library-files-loading" role="status" aria-live="polite">
            {t("library.loadingFiles")}
          </p>
        ) : filesLoad === "failed" ? (
          <p className="error" role="alert" data-testid="library-files-error">
            {t("library.filesFailed")}
          </p>
        ) : files.length === 0 ? (
          <p>{t("library.noFiles")}</p>
        ) : (
          <div className="cards">
            {files.map((file) => (
              // بطاقةُ ملفٍ تُميَّز عن بطاقةِ مرجع: `article.card` يطابق
              // الاثنتين، فعدُّها لا يفرّق بين مكتبةٍ بلا ملفات ومكتبةٍ لم
              // تُقرأ — والسمة لا تحمل اسمًا ولا سرًّا.
              <article className="card" data-testid="library-file-card" key={file.id}>
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
                          requested.current.add(file.id);
                          polls.current = 0;
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
        {/* ما عُرض لا يُستبدل بما يُضاف: الزرّ يُلحق ولا يعيد البناء. */}
        {filesLoad === "ready" && hasMore ? (
          <button
            type="button"
            data-testid="library-load-more"
            disabled={loadingMore}
            onClick={loadMore}
            style={{ marginBlockStart: 12 }}
          >
            {loadingMore ? t("library.loadingMore") : t("library.loadMore")}
          </button>
        ) : null}
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
