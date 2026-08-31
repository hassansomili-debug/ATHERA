"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * صندوق القرارات (§9، §25).
 *
 * ثلاثة عدّادات لا رقم واحد: اعتماد ينتظر قرارًا شيء، وتنبيه نزاهة مفتوح
 * شيء آخر، والحاجب منها شيء ثالث. جمعها في «١٢ عنصرًا» يخفي أيّها يوقف عملًا.
 *
 * والرفض هنا يحتاج سببًا كما الاعتماد: قرار بلا سبب يجعل السجل يقول «رُفض»
 * ولا يقول لماذا، فيتكرر الطلب نفسه بعد شهر.
 */
interface Approval {
  id: string;
  gate: string;
  gate_label: string;
  object_type: string;
  object_id: string;
  status: string;
  requested_at: string;
  decided_at: string | null;
  reason: string | null;
}

interface Alert {
  id: string;
  alert_type: string;
  severity: string;
  name: string;
  detail: string | null;
  resolved_at: string | null;
  raised_at: string;
}

interface Summary {
  pending_approvals: number;
  open_alerts: number;
  blocking_alerts: number;
  unread_notifications: number;
}

export default function ApprovalsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [pending, open, counts] = await Promise.all([
        apiFetch<Approval[]>("/api/v1/approvals?status=pending", { locale }),
        apiFetch<Alert[]>("/api/v1/integrity-alerts?open_only=true", { locale }),
        apiFetch<Summary>("/api/v1/inbox/summary", { locale }),
      ]);
      setApprovals(pending);
      setAlerts(open);
      setSummary(counts);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function decide(id: string, approved: boolean) {
    const reason = (reasons[id] ?? "").trim();
    if (reason.length < 3) {
      setError(t("approvals.reasonRequired"));
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/approvals/${id}/decide`, {
        method: "POST",
        locale,
        body: JSON.stringify({ approved, reason }),
      });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  async function resolve(id: string) {
    const resolution = (reasons[id] ?? "").trim();
    if (resolution.length < 3) {
      setError(t("approvals.resolutionRequired"));
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/integrity-alerts/${id}/resolve`, {
        method: "POST",
        locale,
        body: JSON.stringify({ resolution_ar: resolution }),
      });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("approvals.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("approvals.subtitle")}</p>
      <p className="provenance-note">{t("approvals.noTimeoutNote")}</p>
      {error ? <p className="error">{error}</p> : null}

      {summary ? (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBlockEnd: 16 }}>
          <span className="metric-label">
            {t("approvals.pending")}: <strong>{summary.pending_approvals}</strong>
          </span>
          <span className="metric-label">
            {t("approvals.openAlerts")}: <strong>{summary.open_alerts}</strong>
          </span>
          <span className={summary.blocking_alerts > 0 ? "error" : "metric-label"}>
            {t("approvals.blockingAlerts")}: <strong>{summary.blocking_alerts}</strong>
          </span>
        </div>
      ) : null}

      <h2>{t("approvals.pendingSection")}</h2>
      {approvals.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("approvals.emptyApprovals")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {approvals.map((approval) => (
          <article className="card" key={approval.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>
                {approval.gate} — {approval.gate_label}
              </strong>
              <span className="metric-label">{approval.object_type}</span>
            </div>
            {approval.reason ? (
              <p style={{ marginBlock: 4 }}>{approval.reason}</p>
            ) : null}
            <label style={{ display: "block", marginBlockStart: 8 }}>
              {t("approvals.reasonLabel")}
              <textarea
                rows={2}
                style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
                value={reasons[approval.id] ?? ""}
                onChange={(event) =>
                  setReasons((prev) => ({ ...prev, [approval.id]: event.target.value }))
                }
              />
            </label>
            <div style={{ display: "flex", gap: 8, marginBlockStart: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                disabled={busyId === approval.id}
                onClick={() => void decide(approval.id, true)}
              >
                {t("approvals.approve")}
              </button>
              <button
                type="button"
                disabled={busyId === approval.id}
                onClick={() => void decide(approval.id, false)}
              >
                {t("approvals.reject")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <h2>{t("approvals.alertsSection")}</h2>
      {alerts.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("approvals.emptyAlerts")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {alerts.map((alert) => (
          <article className="card" key={alert.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{alert.name}</strong>
              <span className={alert.severity === "blocking" ? "error" : "metric-label"}>
                {t(`approvals.severity_${alert.severity}`)}
              </span>
            </div>
            {alert.detail ? <p style={{ marginBlock: 4 }}>{alert.detail}</p> : null}
            <label style={{ display: "block", marginBlockStart: 8 }}>
              {t("approvals.resolutionLabel")}
              <textarea
                rows={2}
                style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
                value={reasons[alert.id] ?? ""}
                onChange={(event) =>
                  setReasons((prev) => ({ ...prev, [alert.id]: event.target.value }))
                }
              />
            </label>
            <button
              type="button"
              style={{ marginBlockStart: 8 }}
              disabled={busyId === alert.id}
              onClick={() => void resolve(alert.id)}
            >
              {t("approvals.resolve")}
            </button>
          </article>
        ))}
      </div>
      <p className="provenance-note">{t("approvals.noDeleteNote")}</p>
    </>
  );
}
