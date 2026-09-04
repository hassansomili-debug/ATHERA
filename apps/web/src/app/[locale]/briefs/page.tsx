"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * النشرة الاستخباراتية (§51.9).
 *
 * النشرة الفارغة تُعرض ولا تُخفى. إخفاؤها يجعل الصمت غامضًا: لا يعود
 * المستخدم يعرف أالرصد عمل ولم يجد، أم لم يعمل أصلًا — وهذان وضعان
 * يستدعيان تصرفين مختلفين تمامًا.
 *
 * وكل بند يحمل مرجعه: بند بلا مرجع إشاعة، والعقد يرفضه قبل الوصول إلى هنا.
 */
interface BriefItem {
  item_key: string;
  title_ar: string;
  evidence_ref: string;
  detail_ar: string | null;
}

interface Brief {
  id: string;
  cadence: string;
  cadence_label: string;
  period_start: string;
  period_end: string;
  new_trends: BriefItem[];
  score_changes: BriefItem[];
  new_cards: BriefItem[];
  alerts: BriefItem[];
  is_empty: boolean;
  summary: string;
  seen_at: string | null;
  acknowledged_at: string | null;
}

function Section({ title, items }: { title: string; items: BriefItem[] }) {
  if (items.length === 0) return null;
  return (
    <div style={{ marginBlockStart: 8 }}>
      <strong className="metric-label">{title}</strong>
      <ul style={{ marginBlock: 4, paddingInlineStart: 20 }}>
        {items.map((item) => (
          <li key={item.item_key}>
            {item.title_ar}
            <span className="provenance-note"> — {item.evidence_ref}</span>
            {item.detail_ar ? <div className="metric-label">{item.detail_ar}</div> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function BriefsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [briefs, setBriefs] = useState<Brief[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  // الشاشة كلّها مبنيّة على أن الصمت لا يكون غامضًا — ثم كانت تقول «لا
  // نشرات» قبل أن يعود الطلب، فتصنع الغموض الذي أُنشئت لتمنعه.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setBriefs(await apiFetch<Brief[]>("/api/v1/briefs", { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function acknowledge(id: string) {
    setBusyId(id);
    try {
      await apiFetch(`/api/v1/briefs/${id}/acknowledge`, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("briefs.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("briefs.subtitle")}</p>
      <p className="provenance-note">{t("briefs.evidenceNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : briefs.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("briefs.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {briefs.map((brief) => (
          <article className="card" key={brief.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{brief.cadence_label}</strong>
              <span className="metric-label">
                {new Date(brief.period_start).toLocaleDateString(locale)} —{" "}
                {new Date(brief.period_end).toLocaleDateString(locale)}
              </span>
            </div>
            <p style={{ marginBlock: 4 }}>{brief.summary}</p>

            {brief.is_empty ? (
              <p className="provenance-note">{t("briefs.emptyPeriodNote")}</p>
            ) : (
              <>
                <Section title={t("briefs.newTrends")} items={brief.new_trends} />
                <Section title={t("briefs.scoreChanges")} items={brief.score_changes} />
                <Section title={t("briefs.newCards")} items={brief.new_cards} />
                <Section title={t("briefs.alerts")} items={brief.alerts} />
              </>
            )}

            {brief.acknowledged_at ? (
              <p className="badge-ok">{t("briefs.acknowledged")}</p>
            ) : (
              <button
                type="button"
                style={{ marginBlockStart: 8 }}
                disabled={busyId === brief.id}
                onClick={() => void acknowledge(brief.id)}
              >
                {t("briefs.acknowledge")}
              </button>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
