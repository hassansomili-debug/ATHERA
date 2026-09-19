"use client";

import Link from "next/link";
import { use, useState } from "react";

import { AdminShell, ResourceGate, useAdminResource } from "@/components/AdminShell";
import { formatCount, formatWhen, shortId, type AdminOperations } from "@/lib/admin";
import { DEFAULT_LOCALE, getMessages, isLocale, translator, type Locale } from "@/lib/i18n";

/**
 * العمليات — **بياناتُ تشغيلٍ لا حمولات**.
 *
 * لا طلبَ أداةٍ ولا ردَّها، ولا ملخّصَ وكيل، ولا نصَّ خطأٍ حرّ: يُعرض أنّ خطأً
 * سُجّل، ومعرّفُ التشغيل والأثر للبحث عنه. ورمزُ إخفاق الرسالة يُعرض لأنّه من
 * مفرداتٍ مغلقةٍ في القاعدة، لا نصٌّ حرّ.
 */
const VIEWS = ["failed", "in_progress", "all"] as const;

export default function AdminOperationsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const [view, setView] = useState<(typeof VIEWS)[number]>("failed");
  const { state, reload } = useAdminResource<AdminOperations>(locale, `/api/v1/admin/operations?view=${view}`);
  // «لا يوجد» لا يُقال إلّا بعد أن يُجيب الخادم — وقبلَه `ResourceGate` تقول «جارٍ».
  const answered = state.status === "ready";
  const ops = answered ? state.data : null;
  const viewLabel = { failed: t("admin.viewFailed"), in_progress: t("admin.viewInProgress"), all: t("admin.viewAll") };
  const err = (present: boolean) => (present ? t("admin.errorRecorded") : t("admin.noError"));

  return (
    <AdminShell locale={locale} active="operations">
      <div className="admin-filters" role="group" aria-label={t("admin.viewFilter")}>
        {VIEWS.map((v) => (
          <button key={v} type="button" aria-pressed={v === view} data-testid={`admin-view-${v}`}
                  onClick={() => setView(v)}>
            {viewLabel[v]}
          </button>
        ))}
      </div>
      <p className="provenance-note">{t("admin.opsNote")}</p>
      <ResourceGate locale={locale} state={state} reload={reload} />
      {ops ? (
        <>
          <Section title={t("admin.opsAgents")} empty={ops.agent_runs.length === 0} t={t} testid="ops-agents">
            <thead><tr>
              <th scope="col">{t("admin.colAgent")}</th><th scope="col">{t("admin.colStatus")}</th>
              <th scope="col">{t("admin.colGate")}</th><th scope="col">{t("admin.colStarted")}</th>
              <th scope="col">{t("admin.colFinished")}</th><th scope="col">{t("admin.colRequestedBy")}</th>
              <th scope="col">{t("admin.colError")}</th><th scope="col">{t("admin.colTrace")}</th>
            </tr></thead>
            <tbody>
              {ops.agent_runs.map((a) => (
                <tr key={a.run_id} data-testid="ops-agent-row">
                  <td dir="ltr">{a.agent_key}</td><td>{a.status}</td><td>{a.gate ?? "—"}</td>
                  <td>{formatWhen(locale, a.started_at)}</td><td>{formatWhen(locale, a.finished_at)}</td>
                  <td>
                    {a.requested_by && a.requested_by_name ? (
                      <Link href={`/${locale}/admin/users/${a.requested_by}`}>{a.requested_by_name}</Link>
                    ) : "—"}
                  </td>
                  <td>{err(a.error_present)}</td>
                  <td>
                    {a.trace_id ? (
                      <Link href={`/${locale}/traces`} title={a.trace_id}>
                        <code>{shortId(a.trace_id)}</code>
                      </Link>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </Section>

          <Section title={t("admin.opsModels")} empty={ops.model_runs.length === 0} t={t} testid="ops-models">
            <thead><tr>
              <th scope="col">{t("admin.colProvider")}</th><th scope="col">{t("admin.colModel")}</th>
              <th scope="col">{t("admin.colOperation")}</th><th scope="col">{t("admin.colStatus")}</th>
              <th scope="col" className="num">{t("admin.colLatency")}</th>
              <th scope="col">{t("admin.colWhen")}</th><th scope="col">{t("admin.colError")}</th>
            </tr></thead>
            <tbody>
              {ops.model_runs.map((m) => (
                <tr key={m.run_id} data-testid="ops-model-row">
                  <td dir="ltr">{m.provider}</td><td dir="ltr">{m.model}</td>
                  <td dir="ltr">{m.operation ?? "—"}</td><td>{m.status}</td>
                  <td className="num">{m.latency_ms !== null ? formatCount(locale, m.latency_ms) : "—"}</td>
                  <td>{formatWhen(locale, m.created_at)}</td><td>{err(m.error_present)}</td>
                </tr>
              ))}
            </tbody>
          </Section>

          <Section title={t("admin.opsTools")} empty={ops.tool_runs.length === 0} t={t} testid="ops-tools">
            <thead><tr>
              <th scope="col">{t("admin.colTool")}</th><th scope="col">{t("admin.colStatus")}</th>
              <th scope="col" className="num">{t("admin.colLatency")}</th>
              <th scope="col">{t("admin.colWhen")}</th><th scope="col">{t("admin.colError")}</th>
            </tr></thead>
            <tbody>
              {ops.tool_runs.map((x) => (
                <tr key={x.run_id} data-testid="ops-tool-row">
                  <td dir="ltr">{x.tool_key}</td><td>{x.status}</td>
                  <td className="num">{x.duration_ms !== null ? formatCount(locale, x.duration_ms) : "—"}</td>
                  <td>{formatWhen(locale, x.created_at)}</td><td>{err(x.error_present)}</td>
                </tr>
              ))}
            </tbody>
          </Section>

          <Section title={t("admin.opsTheses")} empty={ops.theses.length === 0} t={t} testid="ops-theses">
            <thead><tr>
              <th scope="col">{t("admin.colId")}</th><th scope="col">{t("admin.colState")}</th>
              <th scope="col">{t("admin.colFailure")}</th>
              <th scope="col" className="num">{t("admin.colAttempts")}</th>
              <th scope="col">{t("admin.colWhen")}</th>
            </tr></thead>
            <tbody>
              {ops.theses.map((h) => (
                <tr key={h.thesis_id} data-testid="ops-thesis-row">
                  <td><code>{shortId(h.thesis_id)}</code></td>
                  <td>{h.processing_state}{h.stalled ? ` · ${t("admin.stalled")}` : ""}</td>
                  <td dir="ltr">{h.failure_code ?? "—"}</td>
                  <td className="num">{formatCount(locale, h.processing_attempts)}</td>
                  <td>{formatWhen(locale, h.processing_state_changed_at)}</td>
                </tr>
              ))}
            </tbody>
          </Section>
          <p><Link href={`/${locale}/traces`}>{t("admin.openTraces")}</Link></p>
        </>
      ) : null}
    </AdminShell>
  );
}

function Section({ title, empty, t, testid, children }: {
  title: string; empty: boolean; t: (k: string) => string; testid: string; children: React.ReactNode;
}) {
  return (
    <section className="admin-section" aria-label={title}>
      <h2>{title}</h2>
      {empty ? (
        <p className="metric-label" data-testid={`${testid}-empty`}>{t("admin.opsEmpty")}</p>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table" data-testid={testid}>{children}</table>
        </div>
      )}
    </section>
  );
}
