"use client";

import Link from "next/link";
import { use } from "react";

import { AdminShell, CostLine, ResourceGate, useAdminResource } from "@/components/AdminShell";
import {
  formatBytes, formatCount, formatWhen, shortId, type AdminUserDetail,
} from "@/lib/admin";
import { DEFAULT_LOCALE, getMessages, isLocale, translator, type Locale } from "@/lib/i18n";

/**
 * تفصيلُ مستخدم — **عضوٌ في هذه المساحة، أو «غيرُ موجود»**.
 *
 * والجملةُ الثابتةُ أسفل الهُويّة تقول ما لا تفعله اللوحة: حالُ الحساب على
 * المنصّة كلّها، فلا يُغيَّر من مساحة عملٍ واحدة. وغيابُ الزرّ بلا جملةٍ
 * يُقرأ نقصًا؛ ومعها يُقرأ حدًّا مقصودًا.
 */
export default function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ locale: string; userId: string }>;
}) {
  const { locale: raw, userId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const { state, reload } = useAdminResource<AdminUserDetail>(
    locale, `/api/v1/admin/users/${encodeURIComponent(userId)}`);
  const d = state.status === "ready" ? state.data : null;
  const n = (v: number) => formatCount(locale, v);

  return (
    <AdminShell locale={locale} active="users">
      <p><Link href={`/${locale}/admin/users`}>{t("admin.backToUsers")}</Link></p>
      <ResourceGate locale={locale} state={state} reload={reload} />
      {d ? (
        <>
          <section className="admin-section card" aria-labelledby="admin-identity">
            <h2 id="admin-identity">{t("admin.identity")}</h2>
            <dl className="admin-dl">
              <dt>{t("admin.colUser")}</dt><dd data-testid="admin-user-name">{d.user.display_name}</dd>
              <dt>{t("admin.colEmail")}</dt><dd dir="ltr">{d.user.email}</dd>
              <dt>{t("admin.colAccount")}</dt>
              <dd>{d.user.is_active ? t("admin.statusActive") : t("admin.statusInactive")}</dd>
              <dt>{t("admin.colLastLogin")}</dt>
              <dd>{d.user.last_login_at ? formatWhen(locale, d.user.last_login_at) : t("admin.never")}</dd>
              <dt>{t("admin.colId")}</dt><dd><code>{shortId(d.user.user_id)}</code></dd>
            </dl>
            <p className="provenance-note" data-testid="admin-account-note">{t("admin.accountStateNote")}</p>
          </section>

          <section className="admin-section card" aria-labelledby="admin-roles">
            <h2 id="admin-roles">{t("admin.workspaceRoles")}</h2>
            <p>{d.user.roles.map((r) => t(`admin.roles.${r}`)).join("، ")}</p>
            <p className="metric-label">{t("admin.memberSince")}: {formatWhen(locale, d.first_membership_at)}</p>
          </section>

          <section className="admin-section" aria-labelledby="admin-activity">
            <h2 id="admin-activity">{t("admin.researchActivity")}</h2>
            <div className="grid">
              <article className="card">
                <div className="metric-label">{t("admin.ownedProjects")}</div>
                <div className="metric-value">{n(d.user.project_count)}</div>
              </article>
              <article className="card">
                <div className="metric-label">{t("admin.filesSummary")}</div>
                <div className="metric-value">{n(d.user.file_count)}</div>
                <p className="metric-label">{formatBytes(locale, d.file_bytes)}</p>
              </article>
              <article className="card">
                <div className="metric-label">{t("admin.thesisCount")}</div>
                <div className="metric-value">{n(d.thesis_count)}</div>
              </article>
            </div>
          </section>

          <section className="admin-section" aria-labelledby="admin-owned">
            <h2 id="admin-owned">{t("admin.ownedProjects")}</h2>
            {d.projects.length === 0 ? (
              <p className="metric-label">{t("admin.none")}</p>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th scope="col">{t("admin.colTitle")}</th>
                      <th scope="col">{t("admin.colLifecycle")}</th>
                      <th scope="col">{t("admin.colCreated")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.projects.map((p) => (
                      <tr key={p.project_id}>
                        <td>{p.title}</td>
                        <td>{t(`admin.lifecycle${p.lifecycle[0].toUpperCase()}${p.lifecycle.slice(1)}`)}</td>
                        <td>{formatWhen(locale, p.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {d.projects_truncated ? (
              <p className="metric-label">
                <Link href={`/${locale}/admin/projects?owner=${d.user.user_id}`}>{t("admin.moreProjects")}</Link>
              </p>
            ) : null}
          </section>

          <section className="admin-section card" aria-labelledby="admin-ai">
            <h2 id="admin-ai">{t("admin.aiSummary")}</h2>
            <p className="metric-label">
              {t("admin.modelRuns")}: {n(d.ai_30d.model_runs)} · {t("admin.inputTokens")}:{" "}
              {n(d.ai_30d.input_tokens)} · {t("admin.outputTokens")}: {n(d.ai_30d.output_tokens)}
            </p>
            <CostLine locale={locale} t={t} usage={d.ai_30d} />
            <p className="provenance-note">{t("admin.attributedNote")}</p>
          </section>

          <section className="admin-section card" aria-labelledby="admin-recent">
            <h2 id="admin-recent">{t("admin.recentActivity")}</h2>
            <p className="metric-label">{t("admin.agentRuns30d")}: {n(d.agent_runs_30d)}</p>
            <p className="metric-label">
              {t("admin.latestModelActivity")}:{" "}
              {d.latest_model_activity_at ? formatWhen(locale, d.latest_model_activity_at) : t("admin.none")}
            </p>
          </section>
        </>
      ) : null}
    </AdminShell>
  );
}
