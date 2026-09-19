"use client";

import { use, useState } from "react";

import { AdminShell, CostLine, ResourceGate, useAdminResource } from "@/components/AdminShell";
import {
  fill, formatCount, formatUsd, type AdminUsage, type UsageBucket,
} from "@/lib/admin";
import { DEFAULT_LOCALE, getMessages, isLocale, translator, type Locale } from "@/lib/i18n";

/**
 * استخدامُ الذكاء الاصطناعي — **من `model_runs` كما سُجّلت**.
 *
 * ولا مكتبةَ رسوم: الأشرطةُ `<span>` بعرضٍ نسبيّ داخل جدولٍ مقروءٍ بقارئ
 * الشاشة، فالرقمُ في الخليّة والشريطُ زينةٌ عليه لا بديلٌ عنه.
 */
const WINDOWS = ["7d", "30d", "90d"] as const;

export default function AdminUsagePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const [window_, setWindow] = useState<(typeof WINDOWS)[number]>("30d");
  const { state, reload } = useAdminResource<AdminUsage>(locale, `/api/v1/admin/usage?window=${window_}`);
  const u = state.status === "ready" ? state.data : null;
  const n = (v: number) => formatCount(locale, v);
  const label = { "7d": t("admin.days7"), "30d": t("admin.days30"), "90d": t("admin.days90") };

  return (
    <AdminShell locale={locale} active="usage">
      <div className="admin-filters" role="group" aria-label={t("admin.window")}>
        {WINDOWS.map((w) => (
          <button key={w} type="button" aria-pressed={w === window_}
                  data-testid={`admin-window-${w}`} onClick={() => setWindow(w)}>
            {label[w]}
          </button>
        ))}
      </div>
      <p className="provenance-note">{t("admin.modelRunsNote")}</p>
      <ResourceGate locale={locale} state={state} reload={reload} />
      {u ? (
        <>
          <div className="grid" data-testid="admin-usage-summary">
            <article className="card">
              <div className="metric-label">{t("admin.modelRuns")}</div>
              <div className="metric-value" data-testid="usage-model-runs">{n(u.summary.model_runs)}</div>
              <p className="metric-label">
                {t("admin.failedRuns")}: {n(u.summary.failed)} · {t("admin.ambiguousRuns")}:{" "}
                {n(u.summary.ambiguous)}
              </p>
            </article>
            <article className="card">
              <div className="metric-label">{t("admin.inputTokens")}</div>
              <div className="metric-value" data-testid="usage-input-tokens">{n(u.summary.input_tokens)}</div>
            </article>
            <article className="card">
              <div className="metric-label">{t("admin.outputTokens")}</div>
              <div className="metric-value" data-testid="usage-output-tokens">{n(u.summary.output_tokens)}</div>
            </article>
            <article className="card" data-testid="usage-cost">
              <div className="metric-label">{t("admin.recordedCost")}</div>
              <CostLine locale={locale} t={t} usage={u.summary} />
            </article>
            <article className="card">
              <div className="metric-label">{t("admin.latency")}</div>
              {u.latency.runs_with_latency > 0 ? (
                <>
                  <p className="metric-label">
                    {t("admin.latencyMedian")}: {n(u.latency.median_ms ?? 0)} ms ·{" "}
                    {t("admin.latencyAvg")}: {n(u.latency.average_ms ?? 0)} ms
                  </p>
                  <p className="provenance-note">
                    {fill(t("admin.latencyBasis"), { n: n(u.latency.runs_with_latency) })}
                  </p>
                </>
              ) : <p className="metric-label">{t("admin.latencyNone")}</p>}
            </article>
            <article className="card">
              <div className="metric-label">{t("admin.agentRuns")} · {t("admin.toolRuns")}</div>
              <p className="metric-label">{n(u.agent_runs)} · {n(u.tool_runs)}</p>
            </article>
          </div>
          {u.summary.model_runs === 0 ? (
            <p className="metric-label" data-testid="usage-empty">{t("admin.usageEmpty")}</p>
          ) : (
            <>
              <Breakdown locale={locale} t={t} title={t("admin.byDay")} rows={u.by_day} testid="usage-by-day" />
              <Breakdown locale={locale} t={t} title={t("admin.byProvider")} rows={u.by_provider} testid="usage-by-provider" />
              <Breakdown locale={locale} t={t} title={t("admin.byModel")} rows={u.by_model} testid="usage-by-model" />
              <Breakdown locale={locale} t={t} title={t("admin.byStatus")} rows={u.by_status} testid="usage-by-status" />
              <Breakdown locale={locale} t={t} title={t("admin.byOperation")} rows={u.by_operation} testid="usage-by-operation" />
            </>
          )}
        </>
      ) : null}
    </AdminShell>
  );
}

function Breakdown({ locale, t, title, rows, testid }: {
  locale: Locale; t: (k: string) => string; title: string; rows: UsageBucket[]; testid: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.model_runs));
  const n = (v: number) => formatCount(locale, v);
  return (
    <section className="admin-section" aria-label={title}>
      <h2>{title}</h2>
      <div className="admin-table-wrap">
        <table className="admin-table" data-testid={testid}>
          <thead>
            <tr>
              <th scope="col">{t("admin.colKey")}</th>
              <th scope="col" className="num">{t("admin.modelRuns")}</th>
              <th scope="col" aria-hidden="true" />
              <th scope="col" className="num">{t("admin.failedRuns")}</th>
              <th scope="col" className="num">{t("admin.inputTokens")}</th>
              <th scope="col" className="num">{t("admin.outputTokens")}</th>
              <th scope="col" className="num">{t("admin.recordedCost")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td dir="ltr">{row.key}</td>
                <td className="num">{n(row.model_runs)}</td>
                <td style={{ minInlineSize: 90 }} aria-hidden="true">
                  <span className="admin-bar"><span style={{ inlineSize: `${(row.model_runs / max) * 100}%` }} /></span>
                </td>
                <td className="num">{n(row.failed)}</td>
                <td className="num">{n(row.input_tokens)}</td>
                <td className="num">{n(row.output_tokens)}</td>
                <td className="num">
                  {row.runs_with_cost > 0 ? formatUsd(locale, row.recorded_cost_usd) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
