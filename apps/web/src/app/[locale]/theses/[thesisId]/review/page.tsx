"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { Dic2Consent } from "@/components/Dic2Consent";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { useDeferredLoad } from "@/lib/useDeferredLoad";

/**
 * «راجع ما استخرجته أثيرا» (§17، §19).
 *
 * **كل حقل يحمل مصدره.** الاقتباس الحرفي والموضع معروضان مع القيمة، لا خلف
 * نقرة: الباحث يحكم على ما قرأته أثيرا لا على ادعائها. وسؤال الشاشة صريح:
 * «من أين استخرجت أثيرا هذه المعلومة؟»
 *
 * **ولا حقل يُعتمد بالصمت.** ما لم يقرّره الباحث يبقى «بانتظار مراجعتك»،
 * وما لم يرد في الملف يُعلَن «لم يُستخرَج» ولا يُخفى ليبدو النموذج مكتملًا.
 *
 * **والثقة ثقة استخراج لا ثقة علم** — مكتوبة بهذا المعنى تحت الرقم، لأن
 * رقمًا عاريًا يُقرأ حكمًا على جودة البحث.
 */
interface Candidate {
  id: string;
  field_key: string;
  label: string;
  value: unknown;
  status: string;
  extraction_status: string | null;
  extraction_confidence: number | null;
  quote: string | null;
  locator: string | null;
  decided_at: string | null;
  edited_by_human: boolean;
  conflict_with: unknown;
}

interface SectionGroup {
  key: string;
  label: string;
  fields: Candidate[];
}

interface Review {
  thesis_id: string;
  sections: SectionGroup[];
  total: number;
  approved: number;
  rejected: number;
  unknown: number;
  pending: number;
  note: string;
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(asText).join("، ");
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export default function ReviewPage({
  params,
}: {
  params: Promise<{ locale: string; thesisId: string }>;
}) {
  const { locale: raw, thesisId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  // بعد الإذن يستأنف الاستخراج ثوانيَ — والشاشة كانت تقول «لا مقترحات بعد»
  // وتبقى عليها. فتُعاد القراءة مرّاتٍ **معدودة**، ثم تتوقّف: رسالةُ «لا
  // مقترحات» بعد ذلك صادقة، وليست انتظارًا بلا نهاية.
  const [awaiting, setAwaiting] = useState(0);
  // **الشاشة كانت صامتة تمامًا ريثما تصل المراجعة.** `review === null` تعني
  // «لا شيء يُعرض» — ولا تُفرَّق عن مراجعةٍ وصلت وهي خالية. والباحث جاء
  // ليراجع، فالصمت أوّل ما يقرؤه ولا يعرف أينتظر أم لا شيء هناك.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setReview(await apiFetch<Review>(`/api/v1/theses/${thesisId}/review`, { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, t, thesisId]);

  useDeferredLoad(load);

  useEffect(() => {
    // ويتوقّف فور وصول أول مقترح — لا يُكمل عدَّه بلا سبب.
    if (awaiting === 0 || (review?.total ?? 0) > 0) return;
    const timer = window.setTimeout(() => {
      setAwaiting((left) => left - 1);
      void load();
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [awaiting, review, load]);

  async function decide(
    candidate: Candidate,
    decision: "approve" | "reject" | "unknown",
    value?: string,
  ) {
    setBusy(candidate.id);
    setError(null);
    try {
      await apiFetch(`/api/v1/theses/candidates/${candidate.id}/decide`, {
        method: "POST",
        locale,
        body: JSON.stringify({
          decision,
          value: value === undefined || value.trim() === "" ? null : value.trim(),
          reason: reason.trim() === "" ? null : reason.trim(),
        }),
      });
      setEditing(null);
      setDraft("");
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(null);
    }
  }

  const statusLabel: Record<string, string> = {
    approved: t("thesisReview.statusApproved"),
    rejected: t("thesisReview.statusRejected"),
    unknown: t("thesisReview.statusUnknown"),
    unverified: t("thesisReview.statusPending"),
  };

  return (
    <>
      <h1>{t("thesisReview.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("thesisReview.subtitle")}</p>
      <Link href={`/${locale}/theses`} style={{ color: "var(--athera-teal)" }}>
        {t("thesisReview.backToTheses")}
      </Link>

      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p data-testid="review-loading" style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : null}

      {/* **الإذن قبل المراجعة.** المكتبة تقول للباحث إن المتابعة تنتظر
          موافقته، وتحيله إلى هنا؛ فيجب أن يجد الباب حيث أُرسل — لا قائمةً
          يبحث فيها عن رسالته ثم لا يجد فيها زرًّا يمنح به شيئًا. وما دام
          الحدّ قائمًا فلا مرشّحات تُعرض أصلًا: الشاشة تطلب قرارًا واحدًا. */}
      <Dic2Consent
        locale={locale}
        messages={getMessages(locale)}
        thesisId={thesisId}
        onDecision={(decision) => {
          if (decision !== "grant") return;
          void load();
          // أربعٌ وعشرون محاولة على مدى دقيقة — حدٌّ معلن لا انتظارٌ مفتوح.
          setAwaiting(24);
        }}
      />

      {review === null ? null : (
        <>
          <p className="metric-label" style={{ marginBlockStart: 16 }}>
            {t("thesisReview.progress")
              .replace("{approved}", String(review.approved))
              .replace("{total}", String(review.total))
              .replace("{pending}", String(review.pending))}
          </p>
          {/* الفئات الأربع مفصولة (§10): دمج «لا أعرف» في الرفض يضخّم عدّ
              المرفوضات ويخفي تردّدًا هو نفسه معلومة. */}
          <p className="metric-label">
            {t("thesisReview.tallyLine")
              .replace("{approved}", String(review.approved))
              .replace("{rejected}", String(review.rejected))
              .replace("{unknown}", String(review.unknown))
              .replace("{pending}", String(review.pending))}
          </p>

          {review.sections.length === 0 ? <p>{t("thesisReview.empty")}</p> : null}

          {review.sections.map((section) => (
            <section key={section.key} style={{ marginBlockStart: 24 }}>
              <h2 style={{ fontSize: 18 }}>{section.label}</h2>
              <div style={{ display: "grid", gap: 10 }}>
                {section.fields.map((field) => {
                  const absent = field.extraction_status === "not_found" || !field.quote;
                  const isUnknown = field.status === "unknown";
                  // «لا أعرف» حكمٌ لم يُحسم — فتبقى قابلة للعودة إليها، ولا
                  // تُعامَل معاملة المحسوم نهائيًّا.
                  const settled = field.status === "approved" || field.status === "rejected";
                  return (
                    <article className="card" key={field.id}>
                      <div
                        style={{
                          display: "flex", justifyContent: "space-between",
                          gap: 12, flexWrap: "wrap",
                        }}
                      >
                        <strong>{field.label}</strong>
                        <span
                          className="metric-label"
                          // الحال القانونية بجانب نصّها المترجَم — كما في
                          // بطاقة المكتبة. والفرق بين «معتمَد» و«معتمَدة»
                          // فرقُ حرفٍ في ترجمة، لا فرقٌ في ما وقع.
                          data-candidate-status={field.status}
                          style={
                            isUnknown
                              ? {
                                  // محايد لا لون خطأ: التردّد ليس بطلانًا.
                                  color: "var(--muted)",
                                  border: "1px dashed var(--border)",
                                  borderRadius: "var(--radius)",
                                  padding: "2px 8px",
                                }
                              : undefined
                          }
                        >
                          {statusLabel[field.status] ?? field.status}
                        </span>
                      </div>
                      {isUnknown ? (
                        <p className="provenance-note" style={{ margin: "6px 0 0" }}>
                          {t("thesisReview.statusUnknownHint")}
                        </p>
                      ) : null}

                      {absent ? (
                        <>
                          <p style={{ color: "var(--muted)", margin: "6px 0 0" }}>
                            {t("thesisReview.notExtracted")}
                          </p>
                          <p className="provenance-note" style={{ margin: "2px 0 0" }}>
                            {t("thesisReview.notExtractedHint")}
                          </p>
                        </>
                      ) : (
                        <>
                          <p style={{ margin: "6px 0 0" }}>{asText(field.value)}</p>
                          {field.edited_by_human ? (
                            <span className="metric-label">{t("thesisReview.editedByHuman")}</span>
                          ) : null}

                          {/* المصدر — لا خلف نقرة: الحكم يحتاج ما حُكم عليه. */}
                          <details style={{ marginBlockStart: 8 }} open>
                            <summary style={{ cursor: "pointer", color: "var(--muted)" }}>
                              {t("thesisReview.provenanceQuestion")}
                            </summary>
                            <blockquote
                              style={{
                                margin: "8px 0 0", paddingInlineStart: 12,
                                borderInlineStart: "3px solid var(--border)",
                                color: "var(--muted)", fontSize: 14,
                              }}
                            >
                              {field.quote}
                            </blockquote>
                            <div className="metric-label" style={{ marginBlockStart: 4 }}>
                              {t("thesisReview.locatorLabel")}: {field.locator}
                              {field.extraction_confidence !== null
                                ? ` · ${t("thesisReview.confidenceLabel")}: ${Math.round(
                                    field.extraction_confidence * 100,
                                  )}%`
                                : ""}
                            </div>
                            {field.extraction_confidence !== null ? (
                              <p className="provenance-note" style={{ margin: "2px 0 0" }}>
                                {t("thesisReview.confidenceMeaning")}
                              </p>
                            ) : null}
                          </details>
                        </>
                      )}

                      {field.conflict_with !== null && field.conflict_with !== undefined ? (
                        <div
                          style={{
                            marginBlockStart: 10, padding: 10,
                            borderRadius: "var(--radius)",
                            border: "1px solid var(--athera-amber, #F59E0B)",
                          }}
                        >
                          <strong style={{ fontSize: 14 }}>{t("thesisReview.conflictTitle")}</strong>
                          <p style={{ margin: "4px 0 0", fontSize: 14 }}>
                            {asText(field.conflict_with)}
                          </p>
                          <p className="provenance-note" style={{ margin: "4px 0 0" }}>
                            {t("thesisReview.conflictBody")}
                          </p>
                        </div>
                      ) : null}

                      {editing === field.id ? (
                        <div style={{ display: "grid", gap: 8, marginBlockStart: 10 }}>
                          {/* حقلا التحرير كانا بلا اسمٍ مُعلَن، ونائبُهما
                              يختفي بأول حرف. والاسم يحمل اسم الحقل المُحرَّر
                              لأن الشاشة قد تعرض حقولًا كثيرة متشابهة. */}
                          <label className="sr-only" htmlFor={`review-value-${field.id}`}>
                            {`${t("thesisReview.valuePlaceholder")}: ${field.label}`}
                          </label>
                          <input
                            id={`review-value-${field.id}`}
                            value={draft}
                            onChange={(event) => setDraft(event.target.value)}
                            placeholder={t("thesisReview.valuePlaceholder")}
                          />
                          <label className="sr-only" htmlFor={`review-reason-${field.id}`}>
                            {`${t("thesisReview.reasonPlaceholder")}: ${field.label}`}
                          </label>
                          <input
                            id={`review-reason-${field.id}`}
                            value={reason}
                            onChange={(event) => setReason(event.target.value)}
                            placeholder={t("thesisReview.reasonPlaceholder")}
                          />
                          <div style={{ display: "flex", gap: 8 }}>
                            <button
                              type="button"
                              disabled={busy === field.id || absent}
                              onClick={() => void decide(field, "approve", draft)}
                            >
                              {t("thesisReview.save")}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditing(null);
                                setDraft("");
                              }}
                              style={{
                                border: "1px solid var(--border)", background: "transparent",
                                color: "inherit", borderRadius: "var(--radius)",
                                padding: "8px 16px", font: "inherit", cursor: "pointer",
                              }}
                            >
                              {t("thesisReview.cancel")}
                            </button>
                          </div>
                          {absent ? (
                            <p className="provenance-note" style={{ margin: 0 }}>
                              {t("thesisReview.cannotApproveAbsent")}
                            </p>
                          ) : null}
                        </div>
                      ) : settled ? null : (
                        <div
                          style={{
                            display: "flex", gap: 8, marginBlockStart: 10, flexWrap: "wrap",
                          }}
                        >
                          {absent ? null : (
                            <button
                              type="button"
                              disabled={busy === field.id}
                              onClick={() => void decide(field, "approve")}
                            >
                              {t("thesisReview.approve")}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              setEditing(field.id);
                              setDraft(asText(field.value));
                            }}
                            style={{
                              border: "1px solid var(--border)", background: "transparent",
                              color: "inherit", borderRadius: "var(--radius)",
                              padding: "8px 16px", font: "inherit", cursor: "pointer",
                            }}
                          >
                            {t("thesisReview.edit")}
                          </button>
                          {absent ? null : (
                            <button
                              type="button"
                              disabled={busy === field.id}
                              onClick={() => void decide(field, "reject")}
                              style={{
                                border: "1px solid var(--border)", background: "transparent",
                                color: "inherit", borderRadius: "var(--radius)",
                                padding: "8px 16px", font: "inherit", cursor: "pointer",
                              }}
                            >
                              {t("thesisReview.reject")}
                            </button>
                          )}
                          <button
                            type="button"
                            disabled={busy === field.id || absent || isUnknown}
                            onClick={() => void decide(field, "unknown")}
                            style={{
                              border: "1px solid var(--border)", background: "transparent",
                              color: "inherit", borderRadius: "var(--radius)",
                              padding: "8px 16px", font: "inherit", cursor: "pointer",
                            }}
                          >
                            {t("thesisReview.unknown")}
                          </button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          ))}

          <p className="provenance-note" style={{ marginBlockStart: 24 }}>{review.note}</p>
        </>
      )}
    </>
  );
}
