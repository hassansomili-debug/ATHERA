"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * الذاكرة الموثقة (§7.3) — لا تعرض إلا ما اعتمده الباحث، ومعه مصدره دائمًا.
 * عرض معلومة بلا مصدرها في هذه الشاشة يخالف §4 مباشرة.
 */
interface MemoryItem {
  id: string;
  memory_category: string;
  statement: string;
  source_type: string;
  source_locator: string | null;
  source_quote: string | null;
  verified_at: string | null;
}

export default function MemoryPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [items, setItems] = useState<MemoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  // **«لا معلومات موثّقة» كانت تُقال قبل أن يعود الجواب** — وهي أخطر ما
  // يُقال في هذه الشاشة بالذات: الباحث يقرأ أن ذاكرته المعتمَدة فارغة وهي
  // ليست كذلك، فيظن اعتماداته ضاعت.
  //
  // **والمحفوظ هو الاستعلام المُجاب لا رايةٌ ثنائية.** الشاشة تُعيد الطلب
  // عند كل حرفٍ يُكتب، فرايةٌ تُطفأ في جسم التأثير تصييرٌ متتالٍ يمنعه
  // `react-hooks/set-state-in-effect`. أمّا مقارنة الاستعلام المعروض
  // بالمُجاب فمشتقّة من الحالة، ولا تُضبط إلا في دالّة رد نداء.
  const [answered, setAnswered] = useState<string | null>(null);
  const loading = answered !== query;

  useEffect(() => {
    const controller = new AbortController();
    const path = `/api/v1/memory${query ? `?q=${encodeURIComponent(query)}` : ""}`;
    apiFetch<MemoryItem[]>(path, { locale, signal: controller.signal })
      .then((rows) => {
        setItems(rows);
        setAnswered(query);
      })
      .catch((err) => {
        // طلبٌ أُجهض ليس جوابًا: لا خطأ يُعلَن، ولا استعلام يُعدّ مُجابًا.
        if (controller.signal.aborted) return;
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
        setAnswered(query);
      });
    return () => controller.abort();
  }, [locale, query, t]);

  return (
    <>
      <h1>{t("memory.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("memory.subtitle")}</p>

      <input
        placeholder={t("memory.search")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{
          padding: "10px 12px",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          background: "var(--surface)",
          color: "inherit",
          font: "inherit",
          inlineSize: "min(100%, 360px)",
          marginBlockEnd: "var(--space)",
        }}
      />

      {error ? <p className="error">{error}</p> : null}
      {loading ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : items.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("memory.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: "var(--space)" }}>
        {items.map((item) => (
          <article className="card" key={item.id}>
            <div className="metric-label">
              {t("memory.category")}: {item.memory_category} · {t("provenance.verified")}
            </div>
            <p style={{ fontWeight: 600, marginBlock: 8 }}>{item.statement}</p>
            {item.source_quote ? (
              <blockquote
                style={{
                  margin: 0,
                  paddingInlineStart: 12,
                  borderInlineStart: "3px solid var(--athera-gold)",
                  color: "var(--muted)",
                  fontSize: 13,
                }}
              >
                «{item.source_quote}»
                <div style={{ fontSize: 12, marginBlockStart: 4 }}>
                  {t("memory.source")}: {item.source_type} · {item.source_locator}
                </div>
              </blockquote>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}
