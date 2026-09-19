"use client";

import Link from "next/link";
import { use, useState } from "react";

import { AdminShell, ResourceGate, useAdminResource } from "@/components/AdminShell";
import { formatCount, formatWhen, type AdminUserRow, type Page } from "@/lib/admin";
import { DEFAULT_LOCALE, getMessages, isLocale, translator, type Locale } from "@/lib/i18n";

/**
 * المستخدمون — **أعضاءُ هذه المساحة وحدهم**.
 *
 * والبحثُ يقع داخل العضويّة في الخادم لا في المتصفّح: لا يُجلب حسابٌ من خارج
 * المساحة ثمّ يُصفّى. ولا عمودَ لتعديل دورٍ ولا زرَّ لتعطيل حسابٍ ولا لانتحاله —
 * تلك مُحالةٌ إلى المرحلة ١٠ بقرار.
 */
const ROLES = ["researcher", "student", "co_author", "supervisor", "internal_reviewer",
  "research_admin", "college_admin", "institution_admin", "system_admin"];

export default function AdminUsersPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState({ search: "", role: "", status: "", cursor: "" });

  const params_ = new URLSearchParams();
  if (query.search) params_.set("search", query.search);
  if (query.role) params_.set("role", query.role);
  if (query.status) params_.set("active", query.status === "active" ? "true" : "false");
  if (query.cursor) params_.set("cursor", query.cursor);
  const path = `/api/v1/admin/users${params_.size ? `?${params_.toString()}` : ""}`;
  const { state, reload } = useAdminResource<Page<AdminUserRow>>(locale, path);
  // «لا يوجد» لا يُقال إلّا بعد أن يُجيب الخادم — وقبلَه `ResourceGate` تقول «جارٍ».
  const answered = state.status === "ready";
  const page = answered ? state.data : null;

  return (
    <AdminShell locale={locale} active="users">
      <form
        className="admin-filters"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery({ search: search.trim(), role, status, cursor: "" });
        }}
      >
        <label htmlFor="admin-user-search">
          {t("admin.searchUsersLabel")}
          <input id="admin-user-search" type="search" value={search}
                 onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label htmlFor="admin-user-role">
          {t("admin.roleFilter")}
          <select id="admin-user-role" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="">{t("admin.allRoles")}</option>
            {ROLES.map((key) => <option key={key} value={key}>{t(`admin.roles.${key}`)}</option>)}
          </select>
        </label>
        <label htmlFor="admin-user-status">
          {t("admin.statusFilter")}
          <select id="admin-user-status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">{t("admin.allStatuses")}</option>
            <option value="active">{t("admin.statusActive")}</option>
            <option value="inactive">{t("admin.statusInactive")}</option>
          </select>
        </label>
        <button type="submit" data-testid="admin-users-apply">{t("admin.apply")}</button>
      </form>

      <ResourceGate locale={locale} state={state} reload={reload} />
      {page && page.items.length === 0 ? (
        <p className="metric-label" data-testid="admin-users-empty">{t("admin.usersEmpty")}</p>
      ) : null}
      {page && page.items.length > 0 ? (
        <div className="admin-table-wrap">
          <table className="admin-table" data-testid="admin-users-table">
            <thead>
              <tr>
                <th scope="col">{t("admin.colUser")}</th>
                <th scope="col">{t("admin.colEmail")}</th>
                <th scope="col">{t("admin.colRoles")}</th>
                <th scope="col">{t("admin.colAccount")}</th>
                <th scope="col">{t("admin.colLastLogin")}</th>
                <th scope="col" className="num">{t("admin.colProjects")}</th>
                <th scope="col" className="num">{t("admin.colModelRuns30d")}</th>
                <th scope="col">{t("admin.colOpen")}</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((user) => (
                <tr key={user.user_id} data-testid="admin-user-row">
                  <td>{user.display_name}</td>
                  <td dir="ltr">{user.email}</td>
                  <td>{user.roles.map((r) => t(`admin.roles.${r}`)).join("، ")}</td>
                  <td>{user.is_active ? t("admin.statusActive") : t("admin.statusInactive")}</td>
                  <td>{user.last_login_at ? formatWhen(locale, user.last_login_at) : t("admin.never")}</td>
                  <td className="num">{formatCount(locale, user.project_count)}</td>
                  <td className="num">{formatCount(locale, user.attributed_model_runs_30d)}</td>
                  <td>
                    <Link href={`/${locale}/admin/users/${user.user_id}`}
                          aria-label={`${t("admin.open")}: ${user.display_name}`}>
                      {t("admin.open")}
                    </Link>
                  </td>
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
            <button type="button" data-testid="admin-users-next"
                    onClick={() => setQuery({ ...query, cursor: page.next_cursor ?? "" })}>
              {t("admin.nextPage")}
            </button>
          ) : null}
        </div>
      ) : null}
    </AdminShell>
  );
}
