"use client";

import { use, useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  type Impact,
  type ProjectFile,
  type ProjectOverview,
  type ProjectSource,
  fileImpact,
  linkFile,
  projectFiles,
  projectOverview,
  projectSources,
  setSourceUse,
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
  const [pendingRemoval, setPendingRemoval] = useState<
    { fileId: string; impact: Impact } | null
  >(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      ),
    [locale, t],
  );

  const reload = useCallback(() => {
    projectOverview(locale, projectId).then(setOverview).catch(say);
    projectFiles(locale, projectId).then(setFiles).catch(say);
    projectSources(locale, projectId).then(setSources).catch(say);
  }, [locale, projectId, say]);

  useEffect(reload, [reload]);

  // مكتبة الباحث تُجلب لتقديم قائمة اختيار — لا ليكتب معرّفًا بيده.
  useEffect(() => {
    if (section === "files") {
      listLibraryFiles(locale).then(setLibrary).catch(say);
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

  const decide = async (sourceId: string, decision: ProjectSource["use_state"]) => {
    setBusy(true);
    try {
      await setSourceUse(locale, projectId, sourceId, decision);
      reload();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  };

  const tool = toolPath(section, locale, projectId);
  const linkedIds = new Set(files.filter((f) => f.state === "active").map((f) => f.file_id));
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

      <nav aria-label={t("project.overview")} style={{ marginBlock: "var(--space)" }}>
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
          {files.filter((file) => file.state === "active").length === 0 ? (
            <p style={{ color: "var(--muted)" }}>{t("project.noFiles")}</p>
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
          {unlinked.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>
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
                  <button
                    type="button"
                    className="chip chip-stage"
                    disabled={busy}
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
          {sources.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>{t("project.noSources")}</p>
          ) : null}
          <div style={{ display: "grid", gap: 6 }}>
            {sources.map((source) => (
              <article className="card" key={source.source_id}>
                <strong>{source.title}</strong>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
                  {(["included", "saved_only", "excluded"] as const).map((state) => (
                    <button
                      key={state}
                      type="button"
                      disabled={busy || source.use_state === state}
                      aria-pressed={source.use_state === state}
                      className={source.use_state === state ? "chip chip-stage" : "chip chip-muted"}
                      onClick={() => decide(source.source_id, state)}
                    >
                      {t(USE_LABEL[state])}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </>
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
        <div className="card" role="alertdialog" aria-modal="true">
          <strong>{pendingRemoval.impact.summary}</strong>
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
