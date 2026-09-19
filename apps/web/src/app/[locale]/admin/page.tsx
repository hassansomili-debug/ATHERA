"use client";

import Link from "next/link";
import { use } from "react";

import { AdminShell, CostLine, ResourceGate, useAdminResource } from "@/components/AdminShell";
import {
  fill, formatBytes, formatCount, formatWhen, type AdminOverview,
} from "@/lib/admin";
import { DEFAULT_LOCALE, getMessages, isLocale, translator, type Locale } from "@/lib/i18n";

/**
 * النظرةُ العامّة — **لا رقمَ قبل أن يعود الجواب**.
 *
 * «٠ أعضاء» قبل التحميل دعوى كاذبة، و«٠ أعضاء» بعد طلبٍ ساقطٍ أكذب. فالبطاقاتُ
 * لا تُصيَّر إلّا والبياناتُ جاهزة، وما عداها حالٌ بعبارتها.
 */
export default function AdminOverviewPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const { state, reload } = useAdminResource<AdminOverview>(locale, "/api/v1/admin/overview");
  const data = state.status === "ready" ? state.data : null;

  return (
    <AdminShell locale={locale} active="overview" workspace={data?.scope.tenant_name}>
      <ResourceGate locale={locale} state={state} reload={reload} />
      {data ? <Cards locale={locale} t={t} data={data} /> : null}
    </AdminShell>
  );
}

function Cards({ locale, t, data }: { locale: Locale; t: (k: string) => string; data: AdminOverview }) {
  const n = (v: number) => formatCount(locale, v);
  const ops = data.operations;
  const failures = ops.failed_agent_runs + ops.failed_model_runs + ops.failed_tool_runs
    + ops.thesis_processing_failures;
  const thesisFailed = (data.theses.by_processing_state.failed ?? 0)
    + (data.theses.by_processing_state.text_layer_missing ?? 0);
  const base = `/${locale}/admin`;

  return (
    <>
      {data.scope.current_admin_roles.length ? (
        <p className="metric-label">
          {t("admin.yourAdminRoles")}:{" "}
          {data.scope.current_admin_roles.map((r) => t(`admin.roles.${r}`)).join(" · ")}
        </p>
      ) : null}
      <div className="grid" data-testid="admin-overview-cards">
        <article className="card" data-testid="card-members">
          <div className="metric-label">{t("admin.cardMembers")}</div>
          <div className="metric-value">{n(data.users.member_count)}</div>
          <p className="metric-label">{t("admin.membersActive")}: {n(data.users.active_identity_count)}</p>
          <p className="metric-label">{t("admin.signedIn30d")}: {n(data.users.signed_in_30d)}</p>
          <p className="metric-label">{t("admin.signedIn7d")}: {n(data.users.signed_in_7d)}</p>
          <p className="provenance-note">{t("admin.signedInNote")}</p>
          <Link href={`${base}/users`}>{t("admin.openUsers")}</Link>
        </article>
        <article className="card" data-testid="card-projects">
          <div className="metric-label">{t("admin.cardProjects")}</div>
          <div className="metric-value">{n(data.projects.total)}</div>
          <p className="metric-label">
            {t("admin.projectsActive")}: {n(data.projects.active)} · {t("admin.projectsArchived")}:{" "}
            {n(data.projects.archived)}
          </p>
          <p className="metric-label">{t("admin.projectsTrashed")}: {n(data.projects.trashed)}</p>
          <Link href={`${base}/projects`}>{t("admin.openProjects")}</Link>
        </article>
        <article className="card" data-testid="card-files">
          <div className="metric-label">{t("admin.cardFiles")}</div>
          <div className="metric-value">{n(data.files.total)}</div>
          <p className="metric-label">{t("admin.filesBytes")}: {formatBytes(locale, data.files.total_bytes)}</p>
          <p className="metric-label">
            {t("admin.filesTrashed")}: {n(data.files.trashed)} · {t("admin.filesPending")}:{" "}
            {n(data.files.pending)}
          </p>
        </article>
        <article className="card" data-testid="card-theses">
          <div className="metric-label">{t("admin.cardTheses")}</div>
          <div className="metric-value">{n(data.theses.total)}</div>
          <p className="metric-label">
            {t("admin.thesesFailed")}: {n(thesisFailed)} · {t("admin.thesesStalled")}:{" "}
            {n(data.theses.stalled)}
          </p>
        </article>
        <article className="card" data-testid="card-model-runs">
          <div className="metric-label">{t("admin.cardModelRuns")}</div>
          <div className="metric-value">{n(data.ai.model_runs)}</div>
          <p className="metric-label">
            {t("admin.runsOk")}: {n(data.ai.succeeded)} · {t("admin.runsFailed")}: {n(data.ai.failed)}{" "}
            · {t("admin.runsAmbiguous")}: {n(data.ai.ambiguous)}
          </p>
          <Link href={`${base}/usage`}>{t("admin.openUsage")}</Link>
        </article>
        <article className="card" data-testid="card-cost">
          <div className="metric-label">{t("admin.cardCost")}</div>
          <CostLine locale={locale} t={t} usage={data.ai} />
        </article>
        <article className="card" data-testid="card-failures">
          <div className="metric-label">{t("admin.cardFailures")}</div>
          <div className="metric-value">{n(failures)}</div>
          <p className="metric-label">
            {fill(t("admin.failuresBreakdown"), {
              agents: n(ops.failed_agent_runs), models: n(ops.failed_model_runs),
              tools: n(ops.failed_tool_runs), theses: n(ops.thesis_processing_failures),
            })}
          </p>
          <Link href={`${base}/operations`}>{t("admin.openOperations")}</Link>
        </article>
        <article className="card" data-testid="card-audit">
          <div className="metric-label">{t("admin.cardAudit")}</div>
          {data.audit.latest_seq === null ? (
            <p className="metric-label">{t("admin.auditNone")}</p>
          ) : (
            <>
              <div className="metric-value">#{n(data.audit.latest_seq)}</div>
              <p className="metric-label">{t("admin.auditLatest")}: {formatWhen(locale, data.audit.latest_at)}</p>
            </>
          )}
          <Link href={`/${locale}/audit`}>{t("admin.openAudit")}</Link>
          <Link href={`/${locale}/settings`}>{t("admin.openPosture")}</Link>
        </article>
      </div>
    </>
  );
}
