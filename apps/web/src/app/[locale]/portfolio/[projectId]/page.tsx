"use client";

import { use, useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  type Impact,
  type ProjectFile,
  type ProjectOverview,
  type LibrarySource,
  type ProjectSource,
  fileImpact,
  linkFile,
  linkSource,
  listLibrarySources,
  projectFiles,
  projectOverview,
  projectSources,
  unlinkFile,
} from "@/lib/workspace";
import { listLibraryFiles, type LibraryFile } from "@/lib/library";

/**
 * مساحة عمل البحث — **البحث هو الشيء المركزي، لا الوحدة**.
 *
 * كان الباحث يفتح «مكتبتي» فيرى ملفاتٍ لا يعرف أيّها لأيّ بحث، ثم
 * «استوديو الورقة» فيرى مخطوطاتٍ لا يعرف على أيّ دليلٍ بُنيت — والربطُ في
 * رأسه وحده. فيُجمع هنا ما يخدم بحثًا واحدًا تحت البحث نفسه.
 *
 * ولا معرّفات تُنسخ: يفتح الباحث بحثه بالضغط على عنوانه، ويربط ملفًّا
 * باختياره من قائمة مكتبته — **والباحث لا ينسخ UUID أبدًا**.
 */
const SECTIONS = [
  "overview",
  "files",
  "literature",
  "data",
  "outputs",
  "manuscript",
  "publishing",
  "activity",
] as const;

type Section = (typeof SECTIONS)[number];

/**
 * أقسامٌ لها أدواتها الكاملة بعدُ خارج مساحة العمل — **تُفتح ولا تُقلَّد**.
 *
 * وبناءُ واجهةٍ ثانية لأداةٍ عاملة يُنتج شاشتين تفترقان؛ فيُفتح الأصل.
 * و«النشر» وحده مربوطٌ بمساره داخل هذا البحث لا بقائمةٍ عامة.
 */
function toolPath(section: Section, locale: Locale, projectId: string): string | null {
  switch (section) {
    case "data":
    case "outputs":
      return `/${locale}/analysis`;
    case "manuscript":
      return `/${locale}/manuscripts`;
    case "publishing":
      return `/${locale}/portfolio/${projectId}/publication-opportunities`;
    case "activity":
      return `/${locale}/audit`;
    default:
      return null;
  }
}

const TOOL_LABEL: Partial<Record<Section, string>> = {
  data: "nav.analysis",
  outputs: "nav.analysis",
  manuscript: "nav.manuscripts",
  publishing: "publicationPlanning.title",
  activity: "nav.audit",
};

const STATE_LABEL: Record<string, string> = {
  known: "project.stateKnown",
  needs_review: "project.stateNeedsReview",
  missing: "project.stateMissing",
  conflicting: "project.stateConflicting",
};

const USE_LABEL: Record<ProjectSource["use_state"], string> = {
  included: "project.useIncluded",
  saved_only: "project.useSavedOnly",
  excluded: "project.useExcluded",
};

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [section, setSection] = useState<Section>("overview");
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [sources, setSources] = useState<ProjectSource[]>([]);
  const [library, setLibrary] = useState<LibraryFile[]>([]);
  const [librarySources, setLibrarySources] = useState<LibrarySource[]>([]);
  const [sourcesLoad, setSourcesLoad] = useState<"loading" | "ready" | "failed">("loading");
  const [pendingRemoval, setPendingRemoval] = useState<
    { fileId: string; impact: Impact } | null
  >(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // **التحميل ليس فراغًا.** القائمتان تبدآن `[]` وتُملآن بعد رحلةٍ إلى
  // الخادم، فكانت الشاشة تقول «لا ملف مرتبط» و«لا ملفات لإضافتها» قبل أن
  // يصل الجواب — وهي دعوى عن حال البحث لم تُفحص بعد. والباحث يقرؤها حكمًا،
  // فيذهب يبحث عن ملفاته في مكانٍ آخر وهي في طريقها إليه.
  const [filesLoad, setFilesLoad] = useState<"loading" | "ready" | "failed">("loading");
  const [libraryLoad, setLibraryLoad] = useState<"loading" | "ready" | "failed">("loading");
  // **والمراجع المرتبطة سقطت من ذلك الإصلاح.** الملفات ومرشّحو الإضافة
  // ومرشّحو المراجع صار لكلٍّ منها حالُ تحميلها، وبقيت `sources` وحدها
  // تُقرأ في `reload` بلا رايةٍ — فتقول الشاشة «لا مراجع مرتبطة» قبل أن
  // يعود الجواب، وهو العطب نفسه في الموضع الرابع.
  const [linkedSourcesLoad, setLinkedSourcesLoad] =
    useState<"loading" | "ready" | "failed">("loading");

  const say = useCallback(
    (err: unknown) =>
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      ),
    [locale, t],
  );

  const reload = useCallback(() => {
    projectOverview(locale, projectId).then(setOverview).catch(say);
    projectFiles(locale, projectId)
      .then((rows) => {
        setFiles(rows);
        setFilesLoad("ready");
      })
      .catch((err) => {
        setFilesLoad("failed");
        say(err);
      });
    projectSources(locale, projectId)
      .then((rows) => {
        setSources(rows);
        setLinkedSourcesLoad("ready");
      })
      .catch((err) => {
        setLinkedSourcesLoad("failed");
        say(err);
      });
  }, [locale, projectId, say]);

  useEffect(reload, [reload]);

  // مكتبة الباحث تُجلب لتقديم قائمة اختيار — لا ليكتب معرّفًا بيده.
  useEffect(() => {
    if (section === "files") {
      listLibraryFiles(locale)
        .then((rows) => {
          setLibrary(rows);
          setLibraryLoad("ready");
        })
        .catch((err) => {
          setLibraryLoad("failed");
          say(err);
        });
    }
  }, [section, locale, say]);

  // مراجع المكتبة تُجلب لتقديم قائمة اختيار — لا ليكتب الباحث معرّفًا.
  useEffect(() => {
    if (section === "literature") {
      listLibrarySources(locale)
        .then((rows) => {
          setLibrarySources(rows);
          setSourcesLoad("ready");
        })
        .catch((err) => {
          setSourcesLoad("failed");
          say(err);
        });
    }
  }, [section, locale, say]);

  const attach = async (fileId: string) => {
    setBusy(true);
    try {
      await linkFile(locale, projectId, fileId);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  };

  /**
   * الإزالة تسأل أولًا.
   *
   * فيُقرأ ما يترتب قبل الفعل: إن لم يعتمد عليه شيء أُزيل مباشرة، وإن قطع
   * سندًا عن عملٍ اعتمده الباحث عُرض ما ينكسر وانتُظر إقراره — **والتحذير
   * الذي يُعرض بعد الفعل ليس تحذيرًا**.
   */
  const requestRemoval = async (fileId: string) => {
    setBusy(true);
    try {
      const impact = await fileImpact(locale, projectId, fileId);
      if (impact.breaks_approved_work) {
        setPendingRemoval({ fileId, impact });
        return;
      }
      await unlinkFile(locale, projectId, fileId);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  };

  const confirmRemoval = async () => {
    if (!pendingRemoval) return;
    setBusy(true);
    try {
      await unlinkFile(locale, projectId, pendingRemoval.fileId, true);
      setPendingRemoval(null);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  };

  /**
   * اربط مرجعًا بهذا البحث — **ويأتي «محفوظًا فقط» من الخادم**.
   *
   * ولا تُفترض الحال هنا: الخادم هو من يقرّرها، والواجهة تعرض ما أعاده.
   * فلو تغيّر الافتراض يومًا ظهر التغيير، ولم تُخفِه واجهةٌ تكتبه من عندها.
   */
  const addSource = async (sourceId: string) => {
    setBusy(true);
    try {
      await linkSource(locale, projectId, sourceId);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  };

  const tool = toolPath(section, locale, projectId);
  const linkedIds = new Set(files.filter((f) => f.state === "active").map((f) => f.file_id));
  // المرشّحون: مراجع المكتبة التي لم تُربط بهذا البحث بعد.
  const linkedSourceIds = new Set(sources.map((s) => s.source_id));
  const availableSources = librarySources.filter((s) => !linkedSourceIds.has(s.id));
  const unlinked = library.filter((file) => !linkedIds.has(file.id));

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>
        {overview?.project.title_ar ?? t("app.loading")}
      </h1>
      {overview?.project.archived_at ? (
        <span className="chip chip-muted">{t("project.archivedBadge")}</span>
      ) : null}
      {error ? <p className="error">{error}</p> : null}

      <nav aria-label={t("project.sectionsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
            listStyle: "none",
            padding: 0,
            margin: 0,
          }}
        >
          {SECTIONS.map((key) => (
            <li key={key}>
              <button
                type="button"
                className={section === key ? "chip chip-stage" : "chip chip-muted"}
                aria-current={section === key ? "page" : undefined}
                onClick={() => setSection(key)}
              >
                {t(`project.${key}`)}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {section === "overview" && overview ? (
        <>
          <article className="card">
            <div className="metric-label">{t("project.nextTitle")}</div>
            <div style={{ fontSize: 15, marginBlock: 6 }}>
              {overview.recommended_next?.label ?? t("project.nextNone")}
            </div>
          </article>

          {overview.blockers.length > 0 ? (
            <article className="card" style={{ marginBlockStart: 8 }}>
              <div className="metric-label">{t("project.blockersTitle")}</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 6 }}>
                {overview.blockers.map((label) => (
                  <span className="chip chip-muted" key={label}>
                    {label}
                  </span>
                ))}
              </div>
            </article>
          ) : null}

          <h2 style={{ marginBlockEnd: 4 }}>{t("project.brainTitle")}</h2>
          <p className="metric-label" style={{ marginBlockStart: 0 }}>
            {t("project.brainNote")}
          </p>
          <div style={{ display: "grid", gap: 6 }}>
            {overview.brain.map((entry) => (
              <article className="card" key={entry.key}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <strong>{entry.label}</strong>
                  <span
                    className={entry.state === "known" ? "chip chip-stage" : "chip chip-muted"}
                  >
                    {t(STATE_LABEL[entry.state] ?? "project.stateMissing")}
                  </span>
                </div>
                {entry.value ? (
                  <p style={{ marginBlockEnd: 0, fontSize: 14 }}>{entry.value}</p>
                ) : null}
              </article>
            ))}
          </div>
        </>
      ) : null}

      {section === "files" ? (
        <>
          <p className="metric-label">{t("project.removeKeepsFile")}</p>
          {/* **والإخفاق كان يُقرأ خلوًّا.** الحالُ ثلاثية منذ أُصلح انتظارُ
              التحميل، ثم لم يُستعمل منها إلا طرفان: «جارٍ» وما عداه. فسقوطُ
              القراءة يترك القائمة فارغة، فتقول الشاشة «لا ملف مرتبط» وهي لم
              تعرف — والخطأ معلَنٌ فوقها في الوقت نفسه. */}
          {filesLoad === "loading" ? (
            <p data-testid="files-loading" style={{ color: "var(--muted)" }}>
              {t("app.loading")}
            </p>
          ) : filesLoad === "failed" ? null : files.filter(
              (file) => file.state === "active",
            ).length === 0 ? (
            <p data-testid="files-empty" style={{ color: "var(--muted)" }}>
              {t("project.noFiles")}
            </p>
          ) : null}
          <div style={{ display: "grid", gap: 6 }}>
            {files
              .filter((file) => file.state === "active")
              .map((file) => (
                <article className="card" key={file.file_id}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      flexWrap: "wrap",
                    }}
                  >
                    <strong>{file.filename}</strong>
                    <span className="chip chip-muted">{file.processing_status}</span>
                  </div>
                  <button
                    type="button"
                    className="chip chip-muted"
                    disabled={busy}
                    style={{ marginBlockStart: 8 }}
                    onClick={() => requestRemoval(file.file_id)}
                  >
                    {t("project.removeFromProject")}
                  </button>
                </article>
              ))}
          </div>

          <h2>{t("project.addFile")}</h2>
          {libraryLoad === "loading" ? (
            <p data-testid="library-loading" style={{ color: "var(--muted)" }}>
              {t("app.loading")}
            </p>
          ) : libraryLoad === "failed" ? null : unlinked.length === 0 ? (
            <p data-testid="library-empty" style={{ color: "var(--muted)" }}>
              {t("project.noCandidates")}{" "}
              <Link href={`/${locale}/library`}>{t("nav.library")}</Link>
            </p>
          ) : null}
          <div style={{ display: "grid", gap: 6 }}>
            {unlinked.map((file) => (
              <article className="card" key={file.id}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <span>{file.original_filename}</span>
                  {/* A11Y-1 — **زرٌّ اسمه «+» لا يقول لأعمى ما يفعل.** ولا على
                      أيّ ملفٍ يقع: في القسم زرٌّ لكل ملف، وكلّها متطابقة
                      الاسم، فلا يُميَّز بينها بالسمع إطلاقًا. والصواب كان
                      بجانبه: زرُّ إضافة المرجع في القسم نفسه يحمل اسم مرجعه.
                      والعلامة تبقى «+» بالعين — الاسم المُعلَن وحده ما تغيّر. */}
                  <button
                    type="button"
                    className="chip chip-stage"
                    disabled={busy}
                    aria-label={`${t("project.addFile")}: ${file.original_filename}`}
                    onClick={() => attach(file.id)}
                  >
                    +
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : null}

      {section === "literature" ? (
        <>
          <p className="metric-label">{t("project.useHint")}</p>
          {linkedSourcesLoad === "loading" ? (
            <p data-testid="sources-loading" style={{ color: "var(--muted)" }}>
              {t("app.loading")}
            </p>
          ) : linkedSourcesLoad === "failed" ? null : sources.length === 0 ? (
            <p data-testid="sources-empty" style={{ color: "var(--muted)" }}>
              {t("project.noSources")}
            </p>
          ) : null}
          <div style={{ display: "grid", gap: 6 }}>
            {sources.map((source) => (
              <article className="card" key={source.source_id}>
                <strong>{source.title}</strong>
                {/* بياناته تُعرض معه: بها يعرفه الباحث، لا بمعرّفٍ داخلي. */}
                <div className="metric-label" style={{ marginBlockStart: 4 }} dir="ltr">
                  {[source.doi, source.publication_year].filter(Boolean).join(" · ") || "—"}
                </div>
                {/* **القرار موضعه شاشة الفرز، لا هنا.**
                    كانت في هذا الموضع ثلاثة أزرار بأسماءٍ مجرَّدة — «إدراج»
                    بجانب «إدراج» بجانب «إدراج» في كل بطاقة — لا يميّز بينها
                    من يسمع الشاشة. والأسوأ أن «استبعاد» كانت تقع بلا سبب،
                    فتبقى الدراسة مستبعَدة ولا يعرف أحدٌ لماذا بعد شهر.

                    ولم تُبنَ نسخةٌ ثانية من الفرز هنا: القائمة تعرض الحال
                    وتفتح الشاشة التي تملك القرار وسببه. */}
                {/* الحال القانونية بجانب نصّها المترجَم — كما في بطاقة
                    المكتبة وخلايا المصفوفة. والنصّ للإنسان، والسمة للآلة:
                    فحصٌ يطابق نصًّا مترجَمًا يسقط بأول تحسينٍ للصياغة. */}
                <div
                  className="metric-label"
                  data-use-state={source.use_state}
                  style={{ marginBlockStart: 8 }}
                >
                  {t("screening.currentState")}: {t(USE_LABEL[source.use_state])}
                  {source.use_state === "excluded" && source.exclusion_reason_code ? (
                    <> — {t(`screening.reason_${source.exclusion_reason_code}`)}</>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
          <p style={{ marginBlockStart: 12 }}>
            <Link className="action" href={`/${locale}/portfolio/${projectId}/screening`}>
              <strong>{t("project.screeningCta")}</strong>
              <span>{t("project.screeningHint")}</span>
            </Link>
          </p>
        </>
      ) : null}

      {section === "literature" ? (
        <section aria-label={t("project.addSource")} style={{ marginBlockStart: 26 }}>
          <h2>{t("project.addSource")}</h2>

          {sourcesLoad === "loading" ? (
            <p data-testid="sources-candidates-loading" style={{ color: "var(--muted)" }}>
              {t("app.loading")}
            </p>
          ) : sourcesLoad === "failed" ? null : availableSources.length === 0 ? (
            // **ولا يُمرَّر الفراغ صامتًا.** إن لم يكن في المكتبة مرجعٌ بعد
            // فللباحث طريقٌ معلَن إلى استيراد واحد — لا شاشةٌ فارغة تسكت.
            <p data-testid="no-candidate-sources" style={{ color: "var(--muted)" }}>
              {t("project.noCandidateSources")}{" "}
              <Link href={`/${locale}/library`}>{t("project.importSourceCta")}</Link>
            </p>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {availableSources.map((source) => (
                <article className="card" key={source.id}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      flexWrap: "wrap",
                    }}
                  >
                    {/* يُعرَّف المرجع بعنوانه وبياناته — **ولا معرّف يُنسخ**. */}
                    <span>
                      <strong>{source.title}</strong>
                      {source.publication_year || source.journal_name ? (
                        <span style={{ color: "var(--muted)" }}>
                          {" — "}
                          {[source.journal_name, source.publication_year]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      ) : null}
                    </span>
                    <button
                      type="button"
                      className="chip chip-stage"
                      disabled={busy}
                      aria-label={`${t("project.addSource")}: ${source.title}`}
                      onClick={() => addSource(source.id)}
                    >
                      +
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tool ? (
        <article className="card">
          <p style={{ marginBlockStart: 0 }}>{t("project.notYet")}</p>
          <Link className="action" href={tool}>
            <strong>{t("project.openTool")}</strong>
            <span>{t(TOOL_LABEL[section] ?? "project.openTool")}</span>
          </Link>
        </article>
      ) : null}

      {pendingRemoval ? (
        // **حوارٌ بلا اسمٍ مُعلَن.** الدور والنمطية معلَنان، والاسم غائب —
        // فقارئ الشاشة يقول «حوار تنبيه» ولا يقول على أيّ شيء يُنبّه. وخلاصة
        // الأثر هي الاسم الصحيح: هي ما يُقرأ أوّلًا بالعين أصلًا.
        <div
          className="card"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="impact-summary"
        >
          <strong id="impact-summary">{pendingRemoval.impact.summary}</strong>
          <ul>
            {pendingRemoval.impact.consequences.map((consequence) => (
              <li key={consequence.kind}>
                {consequence.count} — {consequence.label}
              </li>
            ))}
          </ul>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="chip chip-muted"
              disabled={busy}
              onClick={confirmRemoval}
            >
              {t("project.impactConfirm")}
            </button>
            <button
              type="button"
              className="chip chip-stage"
              onClick={() => setPendingRemoval(null)}
            >
              {t("project.cancel")}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
