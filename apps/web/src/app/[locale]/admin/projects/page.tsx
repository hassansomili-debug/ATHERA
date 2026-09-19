"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { AdminShell, ResourceGate, useAdminResource } from "@/components/AdminShell";
import { formatCount, formatWhen, shortId, type AdminProjectRow, type Page } from "@/lib/admin";
import { DEFAULT_LOCALE, getMessages, isLocale, translator, type Locale } from "@/lib/i18n";

/**
 * المشروعاتُ البحثيّة — **بياناتُ تشغيلٍ لا محتوى**.
 *
 * العنوانُ العاملُ وحدَه، والمالكُ، والطوابعُ، والأعداد — لا ملخّصَ ولا نصَّ
 * ولا دليل. ولا رابطَ يتجاوز صلاحيّات الكائن: رؤيةُ بيانات المشروع هنا لا تمنح
 * فتحَه في مساحة البحث.
 */
const LIFECYCLES = ["", "active", "archived", "trashed"] as const;

export default function AdminProjectsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [search, setSearch] = useState("");
  const [lifecycle, setLifecycle] = useState("");
  const [query, setQuery] = useState({ search: "", lifecycle: "", owner: "", cursor: "" });
  const [ownerReady, setOwnerReady] = useState(false);

  // مرشّحُ المالك من الرابط (يأتي من تفصيل المستخدم) — يُقرأ في المتصفّح وحدَه.
  useEffect(() => {
    // مؤجَّلٌ عن جسم الأثر — النمطُ نفسُه في `usePosture`.
    void Promise.resolve().then(() => {
      const owner = new URLSearchParams(window.location.search).get("owner") ?? "";
      if (/^[0-9a-f-]{36}$/i.test(owner)) setQuery((q) => ({ ...q, owner }));
      setOwnerReady(true);
    });
  }, []);

  const qs = new URLSearchParams();
  if (query.search) qs.set("search", query.search);
  if (query.lifecycle) qs.set("lifecycle", query.lifecycle);
  if (query.owner) qs.set("owner_id", query.owner);
  if (query.cursor) qs.set("cursor", query.cursor);
  const path = ownerReady ? `/api/v1/admin/projects${qs.size ? `?${qs.toString()}` : ""}` : null;
  const { state, reload } = useAdminResource<Page<AdminProjectRow>>(locale, path);
  const page = state.status === "ready" ? state.data : null;
  const lifeLabel = (key: string) =>
    key ? t(`admin.lifecycle${key[0].toUpperCase()}${key.slice(1)}`) : t("admin.lifecycleLive");

  return (
    <AdminShell locale={locale} active="projects">
      <form
        className="admin-filters"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery({ ...query, search: search.trim(), lifecycle, cursor: "" });
        }}
      >
        <label htmlFor="admin-project-search">
          {t("admin.searchProjectsLabel")}
          <input id="admin-project-search" type="search" value={search}
                 onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label htmlFor="admin-project-lifecycle">
          {t("admin.lifecycleFilter")}
          <select id="admin-project-lifecycle" value={lifecycle}
                  onChange={(event) => setLifecycle(event.target.value)}>
            {LIFECYCLES.map((key) => <option key={key || "live"} value={key}>{lifeLabel(key)}</option>)}
          </select>
        </label>
        <button type="submit" data-testid="admin-projects-apply">{t("admin.apply")}</button>
      </form>
      {query.owner ? (
        <p className="metric-label" data-testid="admin-owner-filter">
          {t("admin.ownerFiltered")} —{" "}
          <button type="button" onClick={() => setQuery({ ...query, owner: "", cursor: "" })}>
            {t("admin.clearFilter")}
          </button>
        </p>
      ) : null}
      <p className="provenance-note">{t("admin.noContentNote")}</p>

      <ResourceGate locale={locale} state={state} reload={reload} />
      {page && page.items.length === 0 ? (
        <p className="metric-label" data-testid="admin-projects-empty">{t("admin.projectsEmpty")}</p>
      ) : null}
      {page && page.items.length > 0 ? (
        <div className="admin-table-wrap">
          <table className="admin-table" data-testid="admin-projects-table">
            <thead>
              <tr>
                <th scope="col">{t("admin.colTitle")}</th>
                <th scope="col">{t("admin.colId")}</th>
                <th scope="col">{t("admin.colOwner")}</th>
                <th scope="col">{t("admin.colStatus")}</th>
                <th scope="col">{t("admin.colLifecycle")}</th>
                <th scope="col">{t("admin.colCreated")}</th>
                <th scope="col">{t("admin.colUpdated")}</th>
                <th scope="col" className="num">{t("admin.colFiles")}</th>
                <th scope="col" className="num">{t("admin.colCollaborators")}</th>
                <th scope="col" className="num">{t("admin.colManuscripts")}</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((p) => (
                <tr key={p.project_id} data-testid="admin-project-row">
                  <td>{p.title}</td>
                  <td><code title={p.project_id}>{shortId(p.project_id)}</code></td>
                  <td>
                    {p.owner_user_id && p.owner_name ? (
                      <Link href={`/${locale}/admin/users/${p.owner_user_id}`}>{p.owner_name}</Link>
                    ) : t("admin.ownerUnknown")}
                  </td>
                  <td>{p.status}</td>
                  <td>{lifeLabel(p.lifecycle)}</td>
                  <td>{formatWhen(locale, p.created_at)}</td>
                  <td>{formatWhen(locale, p.updated_at)}</td>
                  <td className="num">{formatCount(locale, p.files)}</td>
                  <td className="num">{formatCount(locale, p.collaborators)}</td>
                  <td className="num">{formatCount(locale, p.manuscripts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {page ? (
        <div className="admin-pager">
          {query.cursor ? (
            <button type="button" onClick={() => setQuery({ ...query, cursor: "" })}>
              {t("admin.firstPage")}
            </button>
          ) : null}
          {page.next_cursor ? (
            <button type="button" onClick={() => setQuery({ ...query, cursor: page.next_cursor ?? "" })}>
              {t("admin.nextPage")}
            </button>
          ) : null}
        </div>
      ) : null}
    </AdminShell>
  );
}
