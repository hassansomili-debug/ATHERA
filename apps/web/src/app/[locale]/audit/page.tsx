"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * سجل التدقيق (§37، ADR-0004).
 *
 * الشاشة للقراءة فقط — ولا يوجد زرّ حذف أو تعديل لأن السجل نفسه لا يقبلهما:
 * صلاحيات UPDATE وDELETE مسحوبة على مستوى قاعدة البيانات، ومُحفّز يمنع
 * ما تبقّى. لو أضفنا زرًّا هنا لأعطينا انطباعًا بقدرة لا وجود لها.
 *
 * وزرّ «تحقق من السلسلة» يفحص تجزئة كل حدث مقابل سابقه: انقطاع واحد يعني
 * أن أحدهم مسّ السجل من خارج التطبيق.
 */
interface AuditEvent {
  id: string;
  occurred_at: string;
  actor_user_id: string | null;
  actor_kind: string;
  action: string;
  object_type: string;
  object_id: string | null;
  reason: string | null;
  chain_seq: number;
  hash: string;
}

interface ChainVerification {
  intact: boolean;
  broken_at_seq: number | null;
  events_checked: number;
}

export default function AuditPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [objectType, setObjectType] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // «لا أحداث» في سجلٍّ لا يقبل الحذف أصلًا دعوى ثقيلة — فلا تُقال قبل أن
  // يعود الجواب. وكانت تُقال، فيبدو السجل المحمي فارغًا لحظةَ فتح الشاشة.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const query = objectType.trim()
        ? `?object_type=${encodeURIComponent(objectType.trim())}`
        : "";
      setEvents(await apiFetch<AuditEvent[]>(`/api/v1/audit/events${query}`, { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, objectType, t]);

  useDeferredLoad(load);

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      setChain(await apiFetch<ChainVerification>("/api/v1/audit/chain/verify", { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>{t("audit.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("audit.subtitle")}</p>
      <p className="provenance-note">{t("audit.appendOnlyNote")}</p>
      {error ? <p className="error">{error}</p> : null}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockEnd: 12 }}>
        <input
          type="text"
          placeholder={t("audit.filterPlaceholder")}
          value={objectType}
          onChange={(event) => setObjectType(event.target.value)}
        />
        <button type="button" onClick={() => void load()}>
          {t("audit.filter")}
        </button>
        <button type="button" disabled={busy} onClick={() => void verify()}>
          {t("audit.verifyChain")}
        </button>
      </div>

      {chain ? (
        <p className={chain.intact ? "badge-ok" : "error"}>
          {chain.intact
            ? `${t("audit.chainIntact")} — ${t("audit.eventsChecked")}: ${chain.events_checked}`
            : `${t("audit.chainBroken")} — ${t("audit.brokenAt")}: ${chain.broken_at_seq}`}
        </p>
      ) : null}

      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : events.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("audit.empty")}</p>
      ) : null}

      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>{t("audit.action")}</th>
              <th>{t("audit.object")}</th>
              <th>{t("audit.actor")}</th>
              <th>{t("audit.when")}</th>
              <th>{t("audit.hash")}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{event.chain_seq}</td>
                <td>
                  {event.action}
                  {event.reason ? (
                    <div className="metric-label">{event.reason}</div>
                  ) : null}
                </td>
                <td>{event.object_type}</td>
                <td>{event.actor_user_id ?? event.actor_kind}</td>
                <td>{new Date(event.occurred_at).toLocaleString(locale)}</td>
                <td>
                  <code>{event.hash.slice(0, 12)}…</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="provenance-note">{t("audit.adminOnlyNote")}</p>
    </>
  );
}
