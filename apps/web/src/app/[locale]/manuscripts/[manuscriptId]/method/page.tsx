"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * صياغة المنهجية (S5E-B).
 *
 * ثلاث حالات لا تُطوى في واحدة: **لا أدلة كافية**، و**لا إذن**، و**مسودة
 * بكشوفاتها**. ودمجها في «غير متاح» يخفي عن الباحث ما يستطيع فعله.
 *
 * والتمييز البصري بين الحقيقة والنقص مقصود: ادعاء بلا دليل يُعرض ناقصًا لا
 * يُخفى، وما لم يجد له النموذج سندًا يبقى مكتوبًا.
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
  message: string;
  next_steps: string[];
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
  draft: "methods.statusDraft",
  needs_review: "methods.statusNeedsReview",
  approved: "methods.statusApproved",
  revision_requested: "methods.statusRevisionRequested",
};

export default function MethodsPage({
  params,
}: {
  params: Promise<{ locale: string; manuscriptId: string }>;
}) {
  const { locale: raw, manuscriptId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [context, setContext] = useState<ContextState | null>(null);
  const [section, setSection] = useState<SectionView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const base = `/api/v1/manuscripts/${manuscriptId}/sections/method`;

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
        <h1>{t("methods.title")}</h1>
        <p>{t("methods.subtitle")}</p>
      </header>

      {error ? <p role="alert">{error}</p> : null}

      {/* ١ — الأدلة المتاحة */}
      <section>
        <h2>{t("methods.evidence")}</h2>
        {context && !context.sufficient ? (
          <>
            <p>{t("methods.noEvidence")}</p>
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
                  · {t("methods.locator")}: {item.locator}
                </em>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {/* ٢ — الإذن: مستقلٌّ عن إذن التخطيط، ولا يُطوى في زرّ الصياغة */}
      {context?.sufficient ? (
        <section>
          <h2>{t("methods.consentTitle")}</h2>
          <p>{t("methods.consentBody")}</p>
          <p>
            {consent === "granted"
              ? t("methods.consentGranted")
              : consent === "stale"
                ? t("methods.consentStale")
                : consent === "declined"
                  ? t("methods.consentDeclined")
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
                {t("methods.consentGrant")}
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
                {t("methods.consentDecline")}
              </button>
            </>
          ) : null}
        </section>
      ) : null}

      {/* ٣ — الصياغة */}
      {consent === "granted" ? (
        <section>
          <button type="button" disabled={busy || approved} onClick={() => act(`${base}/draft`, null)}>
            {busy ? t("methods.drafting") : section ? t("methods.redraft") : t("methods.draft")}
          </button>
          {approved ? <p>{t("methods.approvedLock")}</p> : null}
        </section>
      ) : null}

      {/* ٤ — المسودة وادعاءاتها وكشوفاتها */}
      <section>
        <h2>
          {t("methods.draftTitle")}
          {section ? ` — ${t(STATUS_KEY[section.review_status] ?? "methods.statusDraft")}` : ""}
        </h2>
        {section?.text_ar ? (
          <>
            <p>{section.note}</p>
            <article>{section.text_ar}</article>

            <h3>{t("methods.claims")}</h3>
            <ul>
              {section.claims.map((claim) => (
                <li key={claim.id}>
                  {claim.text_ar}
                  {claim.is_labelled_inference ? <em> ({t("methods.claimInference")})</em> : null}
                  {claim.status === "evidence_gap" ? <strong> ({t("methods.claimGap")})</strong> : null}
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

            <h3>{t("methods.issues")}</h3>
            {section.issues.length === 0 ? (
              <p>{t("methods.noIssues")}</p>
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
              {t("methods.approve")}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => act(`${base}/review`, { decision: "request_revision" })}
            >
              {t("methods.requestRevision")}
            </button>
          </>
        ) : (
          <p>{t("methods.noDraft")}</p>
        )}
      </section>
    </main>
  );
}
