"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  loadDeletionPreview,
  loadTrash,
  requestPermanentDelete,
  type DeletionPreview,
  type TrashView,
} from "@/lib/projectManagement";
import { displayTitle } from "@/lib/projectTitle";
import { restoreProject } from "@/lib/workspace";

/**
 * سلّةُ البحوث — **والحذف الظاهر تأجيلٌ لا إتلاف**.
 *
 * وهذه بعينها الشاشة التي عُرض فيها للباحث عنوانٌ من هذا النوع:
 *
 *     قبول 2026-09-09T17:12:41.883012+00:00
 *
 * وهو نصُّ حدثٍ في سجلّ التدقيق ووقتُه لُصقا في موضع العنوان. فلا يُقرأ
 * العمود خامًا هنا: العنوان يأتي من عقدٍ مشترك يقول «مشروع بدون عنوان»
 * حين لا عنوان، **ويعرض تاريخ الإنشاء في سطرٍ مستقلّ**، ويُبقي إعادة
 * التسمية متاحة.
 *
 * ## والإتلاف الدائم زرٌّ يُعاين ثمّ يقف
 *
 * فلا «هل أنت متأكد؟»: تحذيرٌ بلا رقم ليس تحذيرًا، ويضغط الباحث «نعم» لأنه
 * ضغطها مئة مرّة. والمعاينة تقول بعشرة أعدادٍ ما الذي يعتمد على هذا البحث.
 *
 * ثمّ يقف: سياسةُ الاحتفاظ في هذا النظام غير معرَّفةٍ تعريفًا صالحًا
 * للتنفيذ، فلا يُتلَف ما لا تُعرف مشروعيّة إتلافه. **والزرّ يبقى ظاهرًا**
 * ويقول الخادمُ لماذا وقف وما يلزم لرفعه — وزرٌّ يختفي يجعل الباحث يظنّ
 * أن طلبه أُهمل.
 */

type Load = "loading" | "ready" | "failed";

export default function ProjectTrashPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<TrashView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [preview, setPreview] = useState<DeletionPreview | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return loadTrash(locale)
      .then((view) => {
        setData(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, say]);

  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  const restore = (projectId: string) => {
    setBusy(projectId);
    setError(null);
    void restoreProject(locale, projectId)
      .then(() => {
        setPreview(null);
        return refresh();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /** **المعاينة قبل الزرّ لا بعده** — وبعشرة أعدادٍ باسمها. */
  const inspect = (projectId: string) => {
    setBusy(projectId);
    setError(null);
    setBlocked(null);
    void loadDeletionPreview(locale, projectId)
      .then((view) => setPreview(view))
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /** والطلب يُرسَل فعلًا: الخادم يردّ ٤٠٩ برسالةٍ تقول لماذا وقف. */
  const destroy = (projectId: string) => {
    setBusy(projectId);
    setError(null);
    void requestPermanentDelete(locale, projectId)
      .then(() => refresh())
      .catch((err: unknown) => setBlocked(say(err)))
      .finally(() => setBusy(null));
  };

  const projects = data?.projects ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("projectManagement.trashTitle")}</h1>
      <p className="metric-label">{data?.note ?? t("projectManagement.trashMeaning")}</p>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="trash-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="trash-failed" style={{ color: "var(--muted)" }}>
          {t("projectManagement.loadFailedNote")}
        </p>
      ) : projects.length === 0 ? (
        <p data-testid="trash-empty" style={{ color: "var(--muted)" }}>
          {t("projectManagement.emptyTrash")}
        </p>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {projects.map((row) => (
            <article className="card" key={row.project_id} data-testid="trashed-project">
              <strong>{displayTitle(row.title, locale)}</strong>
              {/* **لا عنوان يُصنَع من تاريخ** — والتاريخ في سطرٍ مستقلّ. */}
              {row.title.is_placeholder ? (
                <p className="metric-label" data-testid="untitled-note">
                  {t("projectManagement.untitledNote")}
                </p>
              ) : null}
              <p className="metric-label">
                {t("projectManagement.createdAt")}: {row.created_at.slice(0, 10)}
                {row.deleted_at
                  ? ` · ${t("projectManagement.deletedAt")}: ${row.deleted_at.slice(0, 10)}`
                  : ""}
              </p>

              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="chip chip-stage"
                  aria-label={`${t("projectManagement.restore")}: ${displayTitle(row.title, locale)}`}
                  disabled={busy === row.project_id}
                  onClick={() => restore(row.project_id)}
                >
                  {t("projectManagement.restore")}
                </button>
                <button
                  type="button"
                  className="chip chip-muted"
                  aria-label={`${t("projectManagement.deletionPreview")}: ${displayTitle(row.title, locale)}`}
                  disabled={busy === row.project_id}
                  onClick={() => inspect(row.project_id)}
                >
                  {t("projectManagement.deletionPreview")}
                </button>
              </div>

              {preview && preview.project_id === row.project_id ? (
                <section data-testid="deletion-preview" style={{ marginBlockStart: 8 }}>
                  <h2 style={{ fontSize: "1rem" }}>{t("projectManagement.dependencies")}</h2>
                  <ul>
                    {preview.dependencies.map((item) => (
                      <li key={item.kind}>
                        {item.label}: {item.count}
                      </li>
                    ))}
                  </ul>
                  <p className="metric-label">{preview.message}</p>
                  <p className="metric-label">
                    {t("projectManagement.unblockRequirement")}: {preview.unblock_requirement}
                  </p>
                  <p className="metric-label">
                    {t("projectManagement.policySources")}: {preview.policy_sources.join(" · ")}
                  </p>
                  <button
                    type="button"
                    className="chip chip-muted"
                    aria-label={`${t("projectManagement.permanentDelete")}: ${displayTitle(row.title, locale)}`}
                    disabled={busy === row.project_id}
                    onClick={() => destroy(row.project_id)}
                  >
                    {t("projectManagement.permanentDelete")}
                  </button>
                  {blocked ? (
                    <p className="error" role="alert" data-testid="deletion-blocked">
                      {t("projectManagement.blocked")} — {blocked}
                    </p>
                  ) : null}
                </section>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </>
  );
}
