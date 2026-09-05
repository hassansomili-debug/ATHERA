"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * شاشة مراجعة الحقائق (§10.2) — بوابة G0 عمليًا.
 *
 * كل صف يعرض الاقتباس الحرفي وموضعه في المصدر قبل أي زر قرار. المستخدم لا
 * يعتمد ادعاءً مجرّدًا، بل نصًا يستطيع التحقق منه بعينه.
 */
interface FactCandidate {
  id: string;
  memory_category: string;
  statement: string;
  quote: string;
  locator: string;
  confidence: number | null;
  status: string;
}

export default function FactsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [facts, setFacts] = useState<FactCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  // **«لا مقترحات بانتظار مراجعتك» كانت تُعرض قبل عودة الطلب.** وهي دعوى
  // عن حال بوابة G0 لم تُفحص بعد: الباحث يقرؤها فينصرف عن مراجعةٍ تنتظره.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setFacts(await apiFetch<FactCandidate[]>("/api/v1/profile/facts", { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function decide(id: string, decision: "approve" | "reject") {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/profile/facts/${id}/${decision}`, {
        method: "POST",
        locale,
        body: JSON.stringify({ reason: reasons[id] ?? null }),
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
      <h1>{t("facts.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("facts.subtitle")}</p>
      <p className="provenance-note">{t("facts.groundingNote")}</p>

      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : facts.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("facts.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: "var(--space)" }}>
        {facts.map((fact) => (
          <article className="card" key={fact.id}>
            {/*
              **الحالُ كانت تُقرأ من الخادم ولا تُعرض.** فالصفحة تعرض صفًّا
              من البطاقات بزرَّي «اعتماد» و«رفض» ولا تقول ما هذه البطاقات:
              أهي محفوظةٌ فعلًا؟ أم اقتراحاتٌ لم تُعتمد بعد؟ والفرق هو كلُّ
              معنى بوابة G0. فتُعلَن الحال بلونها وباسمها معًا — واللونُ
              وحده لا يكفي لمن لا يميّزه.
            */}
            <span className="chip chip-candidate" data-state="candidate">
              {t("facts.candidateState")}
            </span>
            <div className="metric-label" style={{ marginBlockStart: 8 }}>
              {t("facts.category")}: {fact.memory_category}
              {fact.confidence !== null ? ` · ${t("facts.confidence")}: ${fact.confidence}` : ""}
            </div>
            <p style={{ fontWeight: 600, marginBlock: 8 }}>{fact.statement}</p>

            <blockquote
              style={{
                margin: 0,
                paddingInlineStart: 12,
                borderInlineStart: "3px solid var(--athera-teal)",
                color: "var(--muted)",
                fontSize: 14,
              }}
            >
              «{fact.quote}»
              <div style={{ fontSize: 12, marginBlockStart: 4 }}>
                {t("facts.locator")}: {fact.locator}
              </div>
            </blockquote>

            <div style={{ display: "flex", gap: 8, marginBlockStart: 12, flexWrap: "wrap" }}>
              {/* **حقلٌ لكل مقترح، وكلّها كانت بلا اسمٍ مُعلَن.** فقارئ
                  الشاشة يجد صفًّا من حقولٍ متطابقة لا يُميَّز بينها — ولذلك
                  يحمل الاسم اسمَ المعلومة التي يُعلَّل قرارها. */}
              <label className="sr-only" htmlFor={`fact-reason-${fact.id}`}>
                {`${t("facts.reasonPlaceholder")}: ${fact.statement}`}
              </label>
              <input
                id={`fact-reason-${fact.id}`}
                className="reason"
                placeholder={t("facts.reasonPlaceholder")}
                value={reasons[fact.id] ?? ""}
                onChange={(e) => setReasons({ ...reasons, [fact.id]: e.target.value })}
                style={{
                  flex: 1,
                  minInlineSize: 200,
                  padding: "8px 10px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "var(--surface)",
                  color: "inherit",
                  font: "inherit",
                }}
              />
              <button
                type="button"
                onClick={() => decide(fact.id, "approve")}
                disabled={busyId === fact.id}
                style={{
                  padding: "8px 16px",
                  border: "none",
                  borderRadius: "var(--radius)",
                  background: "var(--athera-teal)",
                  color: "#fff",
                  font: "inherit",
                  cursor: "pointer",
                }}
              >
                {t("facts.approve")}
              </button>
              <button
                type="button"
                onClick={() => decide(fact.id, "reject")}
                disabled={busyId === fact.id}
                style={{
                  padding: "8px 16px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "transparent",
                  color: "inherit",
                  font: "inherit",
                  cursor: "pointer",
                }}
              >
                {t("facts.reject")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
