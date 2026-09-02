"use client";

import { useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { getMessages, translator, type Locale } from "@/lib/i18n";

/**
 * مساحة عمل قسم واحد من المخطوطة (S5E).
 *
 * ثلاث حالات لا تُطوى في واحدة: **لا أدلة كافية**، و**لا إذن**، و**مسودة
 * بكشوفاتها**. ودمجها في «غير متاح» يخفي عن الباحث ما يستطيع فعله.
 *
 * والتمييز البصري بين الحقيقة والنقص مقصود: ادعاء بلا دليل يُعرض ناقصًا لا
 * يُخفى، وما لم يجد له النموذج سندًا يبقى مكتوبًا.
 *
 * ومشتركٌ بين الأقسام عمدًا: نسختان تفترقان بأول تعديل، فيصير قسمٌ يعرض
 * كشوفاته وآخر يبتلعها.
 */
interface EvidenceRef {
  memory_id: string;
  role: string;
  statement_ar: string;
  locator: string | null;
  quote: string | null;
}

interface ContextState {
  manuscript_id: string;
  section_key: string;
  sufficient: boolean;
  evidence_count: number;
  roles: Record<string, number>;
  missing_roles: string[];
  fingerprint: string;
  consent_state: string;
  provider: string;
  model: string | null;
  evidence: EvidenceRef[];
  analysis_outputs: AnalysisOutputRef[];
  redacted_statistics: string[];
  message: string;
  next_steps: string[];
}

interface AnalysisOutputRef {
  output_id: string;
  test_key: string | null;
  label_ar: string;
}

interface ClaimView {
  id: string;
  text_ar: string;
  claim_type: string;
  status: string;
  is_labelled_inference: boolean;
  evidence: EvidenceRef[];
}

interface IssueView {
  issue_key: string;
  severity: string;
  message_ar: string;
  message_en: string;
  excerpt: string | null;
}

interface SectionView {
  manuscript_id: string;
  version_label: string;
  section_key: string;
  text_ar: string | null;
  review_status: string;
  claims: ClaimView[];
  issues: IssueView[];
  blocking: number;
  note: string;
}

const STATUS_KEY: Record<string, string> = {
  draft: "statusDraft",
  needs_review: "statusNeedsReview",
  approved: "statusApproved",
  revision_requested: "statusRevisionRequested",
};

export function SectionWorkspace({
  locale,
  manuscriptId,
  sectionKey,
  copy,
  strict = false,
}: {
  locale: Locale;
  manuscriptId: string;
  sectionKey: string;
  /** مساحة أسماء الرسائل لهذا القسم — فلكل قسم لغته الخاصة. */
  copy: string;
  /** النتائج وحدها: تعرض مخرجات التحليل وما حُجب من الأدلة. */
  strict?: boolean;
}) {
  const t = translator(getMessages(locale));
  // **مُخزَّنة كـ`t` نفسها.** دالةٌ تُنشأ عند كل عرض داخل مكوّن يستعمل
  // `useCallback` تُفقد المُترجم قدرته على حفظ التذكير، فيرفض ESLint البناء.
  // والسبب نفسه الذي جعل `t` مخزَّنة في `WeakMap` منذ البداية.
  const c = useCallback((key: string) => t(`${copy}.${key}`), [t, copy]);

  const [context, setContext] = useState<ContextState | null>(null);
  const [section, setSection] = useState<SectionView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const base = `/api/v1/manuscripts/${manuscriptId}/sections/${sectionKey}`;

  const load = useCallback(async () => {
    try {
      setContext(await apiFetch<ContextState>(`${base}/drafting-context`, { locale }));
      try {
        setSection(await apiFetch<SectionView>(base, { locale }));
      } catch {
        // لا مسودة بعد — حالة طبيعية لا خطأ.
        setSection(null);
      }
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [base, locale, t]);

  useDeferredLoad(load);

  const act = useCallback(
    async (path: string, body: Record<string, unknown> | null) => {
      setBusy(true);
      setError(null);
      try {
        await apiFetch(path, {
          method: "POST",
          locale,
          ...(body ? { body: JSON.stringify(body) } : {}),
        });
        await load();
      } catch (err) {
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
      } finally {
        setBusy(false);
      }
    },
    [load, locale, t],
  );

  const consent = context?.consent_state ?? "absent";
  const approved = section?.review_status === "approved";

  return (
    <main className="page">
      <header>
        <h1>{c("title")}</h1>
        <p>{c("subtitle")}</p>
      </header>

      {error ? <p role="alert">{error}</p> : null}

      {/* ١ — الأدلة المتاحة */}
      <section>
        <h2>{c("evidence")}</h2>
        {context && !context.sufficient ? (
          <>
            <p>{c("noEvidence")}</p>
            <ul>
              {context.next_steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          </>
        ) : null}
        <ul>
          {(context?.evidence ?? []).map((item) => (
            <li key={item.memory_id}>
              <strong>{item.role}</strong> — {item.statement_ar}
              {item.locator ? (
                <em>
                  {" "}
                  · {c("locator")}: {item.locator}
                </em>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {/* ١ب — الوضع الصارم: ما يسند رقمًا، وما حُجب لأنه بلا سند */}
      {strict ? (
        <section>
          <p>{t("results.strictNote")}</p>
          <h2>{t("results.outputs")}</h2>
          {(context?.analysis_outputs ?? []).length === 0 ? (
            <p>{t("results.noOutputs")}</p>
          ) : (
            <ul>
              {(context?.analysis_outputs ?? []).map((output) => (
                <li key={output.output_id}>
                  {output.label_ar}
                  {output.test_key ? ` · ${output.test_key}` : ""}
                </li>
              ))}
            </ul>
          )}
          <p>{t("results.outputsNote")}</p>
          {(context?.redacted_statistics ?? []).length > 0 ? (
            <>
              <h3>{t("results.redacted")}</h3>
              <ul>
                {(context?.redacted_statistics ?? []).map((value) => (
                  <li key={value}>{value}</li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}

      {/* ٢ — الإذن: مستقلٌّ عن إذن التخطيط، ولا يُطوى في زرّ الصياغة */}
      {context?.sufficient ? (
        <section>
          <h2>{c("consentTitle")}</h2>
          <p>{c("consentBody")}</p>
          <p>
            {consent === "granted"
              ? c("consentGranted")
              : consent === "stale"
                ? c("consentStale")
                : consent === "declined"
                  ? c("consentDeclined")
                  : null}
          </p>
          {consent !== "granted" ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  act(`${base}/drafting-consent`, {
                    decision: "grant",
                    context_fingerprint: context.fingerprint,
                  })
                }
              >
                {c("consentGrant")}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  act(`${base}/drafting-consent`, {
                    decision: "decline",
                    context_fingerprint: context.fingerprint,
                  })
                }
              >
                {c("consentDecline")}
              </button>
            </>
          ) : null}
        </section>
      ) : null}

      {/* ٣ — الصياغة */}
      {consent === "granted" ? (
        <section>
          <button type="button" disabled={busy || approved} onClick={() => act(`${base}/draft`, null)}>
            {busy ? c("drafting") : section ? c("redraft") : c("draft")}
          </button>
          {approved ? <p>{c("approvedLock")}</p> : null}
        </section>
      ) : null}

      {/* ٤ — المسودة وادعاءاتها وكشوفاتها */}
      <section>
        <h2>
          {c("draftTitle")}
          {section ? ` — ${t(STATUS_KEY[section.review_status] ?? "methods.statusDraft")}` : ""}
        </h2>
        {section?.text_ar ? (
          <>
            <p>{section.note}</p>
            <article>{section.text_ar}</article>

            <h3>{c("claims")}</h3>
            <ul>
              {section.claims.map((claim) => (
                <li key={claim.id}>
                  {claim.text_ar}
                  {claim.is_labelled_inference ? <em> ({c("claimInference")})</em> : null}
                  {claim.status === "evidence_gap" ? <strong> ({c("claimGap")})</strong> : null}
                  <ul>
                    {claim.evidence.map((ref) => (
                      <li key={ref.memory_id}>
                        {ref.statement_ar}
                        {ref.locator ? ` · ${ref.locator}` : ""}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>

            <h3>{c("issues")}</h3>
            {section.issues.length === 0 ? (
              <p>{c("noIssues")}</p>
            ) : (
              <ul>
                {section.issues.map((issue, index) => (
                  <li key={`${issue.issue_key}-${index}`}>
                    {locale === "en" ? issue.message_en : issue.message_ar}
                    {issue.excerpt ? ` — «${issue.excerpt}»` : ""}
                  </li>
                ))}
              </ul>
            )}

            {/* ٥ — قرار الباحث: لا يعتمد النموذج نفسه */}
            <button
              type="button"
              disabled={busy || approved}
              onClick={() => act(`${base}/review`, { decision: "approve" })}
            >
              {c("approve")}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => act(`${base}/review`, { decision: "request_revision" })}
            >
              {c("requestRevision")}
            </button>
          </>
        ) : (
          <p>{c("noDraft")}</p>
        )}
      </section>
    </main>
  );
}
