"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { useDeferredLoad } from "@/lib/useDeferredLoad";

/**
 * فرص النشر (S5D).
 *
 * **الترتيب هو الرسالة:** أدلةٌ أولًا، ثم إذنٌ صريح، ثم مقترحات، ثم قرار
 * الباحث، ثم خيطٌ وخريطةٌ وهيكل. ولا خطوة تسبق سابقتها — لأن كل واحدة تعتمد
 * على شيء قرّره إنسان قبلها.
 *
 * وثلاث حالات لا تُخلط أبدًا، ولكلٍّ شاشتها:
 *   نقصُ أدلة    — حدٌّ علمي، وأثيرا لا تخترع ما لا تجده
 *   إذنٌ مطلوب   — قرارُ الباحث في إرسال معرفته خارجًا
 *   عطبُ معالجة  — خللٌ في النظام لا في بحثه
 *
 * ودمجها في «تعذّر» واحد يجعل الباحث يظن أدلته ناقصة وهي كاملة، أو يظن
 * النظام معطوبًا وهو ينتظر إذنه.
 */
interface ContextState {
  project_id: string;
  sufficient: boolean;
  evidence_count: number;
  roles: Record<string, number>;
  missing_roles: string[];
  fingerprint: string;
  consent_state: "granted" | "declined" | "stale" | "absent";
  capability: string;
  provider: string;
  model: string | null;
  message: string;
  next_steps: string[];
}

interface Opportunity {
  id: string;
  working_title_ar: string;
  working_title_en: string | null;
  research_question_ar: string | null;
  opportunity_kind: string;
  paper_kind: string;
  status: string;
  planning_status: "proposed" | "selected" | "excluded" | "superseded";
  evidence_readiness_score: number | null;
  literature_validation_status: string;
  journal_validation_status: string;
  salami_alert: boolean;
  proposed_contribution_ar: string | null;
  claim_boundaries_ar: string | null;
  limitations_ar: string | null;
  missing_requirements: string[];
  evidence_count: number;
  proposal_notice: string;
}

interface OpportunityList {
  project_id: string;
  opportunities: Opportunity[];
  note: string;
}

interface EvidenceRef {
  memory_id: string;
  statement_ar: string;
  locator: string | null;
  quote: string | null;
}

interface MapEntry {
  element_id: string | null;
  element_type: string;
  claim_ar: string;
  origin: string;
  evidence: EvidenceRef[];
}

interface ThreadView {
  opportunity_id: string;
  elements: MapEntry[];
  issues: Array<{ check: string; severity: string; message_ar: string; message_en: string | null }>;
  blocking: number;
  advisory: number;
  note: string;
}

interface OutlineView {
  id: string;
  sections: Array<{
    key: string;
    title_ar: string;
    title_en: string;
    purpose_ar: string;
    evidence_roles_available: string[];
    evidence_roles_missing: string[];
    evidence: Array<{ role: string; locator: string | null; statement_ar: string }>;
    claims_allowed_ar: string[];
    claims_unsupported_ar: string[];
  }>;
  status: string;
  note: string;
}

/** حالة الشاشة — أوسمٌ صادقة لا رسالة واحدة تصلح لكل شيء. */
type Phase =
  | "loading"
  | "insufficient"
  | "consent"
  | "ready"
  | "generating"
  | "failed";

export default function PublicationOpportunitiesPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [context, setContext] = useState<ContextState | null>(null);
  const [list, setList] = useState<OpportunityList | null>(null);
  const [thread, setThread] = useState<ThreadView | null>(null);
  const [outline, setOutline] = useState<OutlineView | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [openEvidence, setOpenEvidence] = useState<string | null>(null);
  const [tab, setTab] = useState<"thread" | "map" | "outline">("thread");

  const load = useCallback(async () => {
    try {
      const state = await apiFetch<ContextState>(
        `/api/v1/projects/${projectId}/publication-context`, { locale },
      );
      setContext(state);
      const listing = await apiFetch<OpportunityList>(
        `/api/v1/projects/${projectId}/publication-opportunities`, { locale },
      );
      setList(listing);
      // الترتيب مقصود: نقص الأدلة يسبق طلب الإذن — لا معنى لإذنٍ على لا شيء.
      if (!state.sufficient) setPhase("insufficient");
      else if (state.consent_state !== "granted") setPhase("consent");
      else setPhase("ready");
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
      setPhase("failed");
    }
  }, [projectId, locale, t]);

  // الدورة الصغرى تمنع التصيير المتتالي — نفس المُساعد الذي تستعمله بقية الشاشات.
  useDeferredLoad(load);

  async function grantConsent() {
    if (!context || busy) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/projects/${projectId}/publication-consent`, {
        method: "POST", locale,
        // البصمة تُرسل مع القرار: الباحث يوافق على اللقطة التي رآها لا على غيرها.
        body: JSON.stringify({ decision: "grant", context_fingerprint: context.fingerprint }),
      });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setPhase("generating");
    try {
      const listing = await apiFetch<OpportunityList>(
        `/api/v1/projects/${projectId}/publication-opportunities`,
        { method: "POST", locale },
      );
      setList(listing);
      setPhase("ready");
    } catch (err) {
      // عطبُ معالجة — لا يُعرض «لا فرص»: الفرق بينهما هو الفرق بين نظامٍ
      // معطوب وبحثٍ لا يحتمل ورقة.
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("publicationPlanning.providerFailed"));
      setPhase("failed");
    } finally {
      setBusy(false);
    }
  }

  async function decide(opportunity: Opportunity, decision: "select" | "exclude") {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(
        `/api/v1/projects/${projectId}/publication-opportunities/${opportunity.id}/decide`,
        { method: "POST", locale, body: JSON.stringify({ decision }) },
      );
      setThread(null);
      setOutline(null);
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  const selected = list?.opportunities.find((o) => o.planning_status === "selected") ?? null;

  async function buildThread() {
    if (!selected || busy) return;
    setBusy(true);
    try {
      setThread(await apiFetch<ThreadView>(
        `/api/v1/projects/${projectId}/publication-opportunities/${selected.id}/thread`,
        { method: "POST", locale },
      ));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function buildOutline() {
    if (!selected || busy) return;
    setBusy(true);
    try {
      setOutline(await apiFetch<OutlineView>(
        `/api/v1/projects/${projectId}/publication-opportunities/${selected.id}/outline`,
        { method: "POST", locale },
      ));
      setTab("outline");
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  const planningLabel: Record<string, string> = {
    proposed: t("publicationPlanning.statusProposed"),
    selected: t("publicationPlanning.statusSelected"),
    excluded: t("publicationPlanning.statusExcluded"),
    superseded: t("publicationPlanning.statusSuperseded"),
  };

  return (
    <>
      <div className="page-head">
        <h1>{t("publicationPlanning.title")}</h1>
        <p>{t("publicationPlanning.subtitle")}</p>
      </div>

      {error ? <p className="error-text" role="alert">{error}</p> : null}
      {phase === "loading" ? <p className="metric-label">{t("app.loading")}</p> : null}

      {/* ── نقص الأدلة: حدٌّ علمي يُشرح، لا خطأ يُعرض ── */}
      {phase === "insufficient" && context ? (
        <section className="card" style={{ display: "grid", gap: 10 }}>
          <strong>{t("publicationPlanning.insufficient")}</strong>
          <p className="provenance-note" style={{ margin: 0 }}>
            {t("publicationPlanning.insufficientWhy")}
          </p>
          <p className="metric-label" style={{ margin: 0 }}>
            {t("publicationPlanning.verifiedFacts")}: {context.evidence_count}
          </p>
          {context.missing_roles.length > 0 ? (
            <p className="metric-label" style={{ margin: 0 }}>
              {t("publicationPlanning.missingRoles")}: {context.missing_roles.join(" · ")}
            </p>
          ) : null}
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>
            {[
              ["stepReview", `/${locale}/theses`],
              ["stepApprove", `/${locale}/facts`],
              ["stepUpload", `/${locale}/theses`],
              ["stepData", `/${locale}/analysis`],
            ].map(([key, href]) => (
              <li key={key}>
                <a href={href}>{t(`publicationPlanning.${key}`)}</a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* ── الإذن: قرارُ الباحث، ونصّه يسمّي المزوّد المضبوط فعلًا ── */}
      {phase === "consent" && context ? (
        <section
          className="card"
          style={{
            display: "grid", gap: 10,
            background: "color-mix(in srgb, var(--athera-mint, #A7F3D0) 18%, transparent)",
          }}
        >
          <strong>{t("publicationPlanning.consentTitle")}</strong>
          <p style={{ margin: 0, whiteSpace: "pre-line" }}>
            {t("publicationPlanning.consentBody")}
          </p>
          <p className="metric-label" style={{ margin: 0 }}>
            {t("publicationPlanning.provider")}: {context.provider}
            {context.model ? ` · ${context.model}` : ""}
            {" · "}
            {t("publicationPlanning.verifiedFacts")}: {context.evidence_count}
          </p>
          {context.consent_state === "stale" ? (
            <p className="provenance-note" style={{ margin: 0 }}>
              {t("publicationPlanning.consentStale")}
            </p>
          ) : null}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="primary-action" disabled={busy}
                    onClick={() => void grantConsent()}>
              {t("publicationPlanning.consentAccept")}
            </button>
            <a className="action" href={`/${locale}/portfolio`}>
              {t("publicationPlanning.consentBack")}
            </a>
          </div>
        </section>
      ) : null}

      {/* ── البناء والفرص ── */}
      {(phase === "ready" || phase === "generating") && context ? (
        <section style={{ display: "grid", gap: 14 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <button type="button" className="primary-action" disabled={busy}
                    onClick={() => void generate()}>
              {list?.opportunities.length
                ? t("publicationPlanning.regenerate")
                : t("publicationPlanning.generate")}
            </button>
            <span className="metric-label">
              {t("publicationPlanning.consentGranted")} · {context.provider} ·{" "}
              {t("publicationPlanning.verifiedFacts")}: {context.evidence_count}
            </span>
          </div>
          <p className="provenance-note" style={{ margin: 0 }}>
            {t("publicationPlanning.regenerateHint")}
          </p>
          {phase === "generating" ? (
            <p className="metric-label" aria-live="polite">
              {t("publicationPlanning.generating")}
            </p>
          ) : null}
          {list && list.opportunities.length === 0 && phase === "ready" ? (
            <p className="metric-label">{t("publicationPlanning.empty")}</p>
          ) : null}

          {list?.opportunities.map((item) => (
            <article className="card" key={item.id} style={{ display: "grid", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10,
                            flexWrap: "wrap", alignItems: "start" }}>
                <strong>{item.working_title_ar}</strong>
                {/* الحالة نصًّا لا لونًا وحده — واللون يزيدها ولا يحملها. */}
                <span className="metric-label">{planningLabel[item.planning_status]}</span>
              </div>
              <span className="metric-label" style={{
                border: "1px dashed var(--border)", borderRadius: "var(--radius)",
                padding: "2px 8px", justifySelf: "start",
              }}>
                {t("publicationPlanning.proposal")}
              </span>

              {item.research_question_ar ? (
                <p style={{ margin: 0 }}>
                  <span className="metric-label">{t("publicationPlanning.question")}: </span>
                  {item.research_question_ar}
                </p>
              ) : null}
              {item.proposed_contribution_ar ? (
                <p style={{ margin: 0 }}>
                  <span className="metric-label">{t("publicationPlanning.contribution")}: </span>
                  {item.proposed_contribution_ar}
                </p>
              ) : null}
              {item.claim_boundaries_ar ? (
                <p className="provenance-note" style={{ margin: 0 }}>
                  {t("publicationPlanning.claimBoundary")}: {item.claim_boundaries_ar}
                </p>
              ) : null}

              <p className="metric-label" style={{ margin: 0 }}>
                {t("publicationPlanning.evidenceReady")}:{" "}
                {item.evidence_readiness_score ?? "—"} ·{" "}
                {t("publicationPlanning.verifiedFacts")}: {item.evidence_count}
              </p>
              <p className="provenance-note" style={{ margin: 0 }}>
                {t("publicationPlanning.evidenceReadyHint")}
              </p>

              {/* §6 — حالات صادقة: السجل مغلق فلا جدّة ولا مجلة. */}
              <p className="metric-label" style={{ margin: 0 }}>
                {t("publicationPlanning.literaturePending")} ·{" "}
                {t("publicationPlanning.journalNotAssessed")}
              </p>
              {item.salami_alert ? (
                <p className="provenance-note" style={{ margin: 0 }}>
                  {t("publicationPlanning.overlapHigh")}
                </p>
              ) : null}
              {item.missing_requirements.length > 0 ? (
                <p className="metric-label" style={{ margin: 0 }}>
                  {t("publicationPlanning.missingRequirements")}:{" "}
                  {item.missing_requirements.join(" · ")}
                </p>
              ) : null}

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="primary-action" disabled={busy}
                        aria-pressed={item.planning_status === "selected"}
                        onClick={() => void decide(item, "select")}>
                  {t("publicationPlanning.select")}
                </button>
                <button type="button" className="action" disabled={busy}
                        onClick={() => void decide(item, "exclude")}>
                  {t("publicationPlanning.exclude")}
                </button>
                <button type="button" className="action" disabled={busy}
                        aria-expanded={openEvidence === item.id}
                        onClick={() => setOpenEvidence(openEvidence === item.id ? null : item.id)}>
                  {t("publicationPlanning.showEvidence")}
                </button>
              </div>
              <p className="provenance-note" style={{ margin: 0 }}>{item.proposal_notice}</p>
            </article>
          ))}
        </section>
      ) : null}

      {/* ── مساحة الفرصة المختارة: خيطٌ وخريطةٌ وهيكل ── */}
      {selected ? (
        <section style={{ marginBlockStart: 26, display: "grid", gap: 12 }}>
          <h2>{t("publicationPlanning.workspace")}</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {(["thread", "map", "outline"] as const).map((key) => (
              <button key={key} type="button" className="action"
                      aria-pressed={tab === key} onClick={() => setTab(key)}>
                {t(`publicationPlanning.${key === "map" ? "evidenceMap" : key}`)}
              </button>
            ))}
          </div>

          {tab !== "outline" ? (
            <div style={{ display: "grid", gap: 10 }}>
              <button type="button" className="primary-action" disabled={busy}
                      onClick={() => void buildThread()}>
                {t("publicationPlanning.buildThread")}
              </button>
              {thread ? (
                <>
                  <p className="metric-label" style={{ margin: 0 }}>
                    {t("publicationPlanning.threadIssues")}: {thread.blocking}{" "}
                    {t("publicationPlanning.blocking")} · {thread.advisory}{" "}
                    {t("publicationPlanning.advisory")}
                  </p>
                  {thread.issues.length === 0 ? (
                    <p className="provenance-note" style={{ margin: 0 }}>
                      {t("publicationPlanning.noIssues")}
                    </p>
                  ) : (
                    <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                      {thread.issues.map((issue) => (
                        <li key={`${issue.check}-${issue.message_ar}`}>
                          <span className="metric-label">
                            [{issue.severity === "blocking"
                              ? t("publicationPlanning.blocking")
                              : t("publicationPlanning.advisory")}]
                          </span>{" "}
                          {locale === "en" && issue.message_en
                            ? issue.message_en : issue.message_ar}
                        </li>
                      ))}
                    </ul>
                  )}
                  {thread.elements.map((entry) => (
                    <article className="card" key={entry.element_id ?? entry.claim_ar}
                             style={{ display: "grid", gap: 6 }}>
                      <div style={{ display: "flex", gap: 10, justifyContent: "space-between",
                                    flexWrap: "wrap" }}>
                        <strong>{entry.claim_ar}</strong>
                        <span className="metric-label">
                          {entry.origin === "verified_evidence"
                            ? t("publicationPlanning.verified")
                            : t("publicationPlanning.proposal")}
                        </span>
                      </div>
                      {/* خريطة الأدلة: الموضع من الذاكرة الموثقة، ولا رابط تخزين. */}
                      {entry.evidence.map((ref) => (
                        <p className="provenance-note" key={ref.memory_id} style={{ margin: 0 }}>
                          {t("publicationPlanning.evidenceOf")}: {ref.statement_ar}
                          {ref.locator
                            ? ` · ${t("publicationPlanning.locator")}: ${ref.locator}` : ""}
                        </p>
                      ))}
                    </article>
                  ))}
                  <p className="provenance-note" style={{ margin: 0 }}>{thread.note}</p>
                </>
              ) : null}
            </div>
          ) : null}

          {tab === "outline" ? (
            <div style={{ display: "grid", gap: 10 }}>
              <button type="button" className="primary-action" disabled={busy}
                      onClick={() => void buildOutline()}>
                {t("publicationPlanning.buildOutline")}
              </button>
              <p className="provenance-note" style={{ margin: 0 }}>
                {t("publicationPlanning.outlineNotice")}
              </p>
              {outline?.sections.map((section) => (
                <article className="card" key={section.key} style={{ display: "grid", gap: 6 }}>
                  <strong>{locale === "en" ? section.title_en : section.title_ar}</strong>
                  <p style={{ margin: 0 }}>
                    <span className="metric-label">
                      {t("publicationPlanning.sectionPurpose")}:{" "}
                    </span>
                    {section.purpose_ar}
                  </p>
                  <p className="metric-label" style={{ margin: 0 }}>
                    {t("publicationPlanning.evidenceAvailable")}:{" "}
                    {section.evidence_roles_available.join(" · ") || "—"}
                  </p>
                  <p className="metric-label" style={{ margin: 0 }}>
                    {t("publicationPlanning.evidenceMissing")}:{" "}
                    {section.evidence_roles_missing.join(" · ") || "—"}
                  </p>
                  {section.claims_allowed_ar.length > 0 ? (
                    <p style={{ margin: 0 }}>
                      <span className="metric-label">
                        {t("publicationPlanning.claimsAllowed")}:{" "}
                      </span>
                      {section.claims_allowed_ar.join(" · ")}
                    </p>
                  ) : null}
                  {section.claims_unsupported_ar.length > 0 ? (
                    <p className="provenance-note" style={{ margin: 0 }}>
                      {t("publicationPlanning.claimsUnsupported")}:{" "}
                      {section.claims_unsupported_ar.join(" · ")}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}
        </section>
      ) : list?.opportunities.length ? (
        <p className="metric-label" style={{ marginBlockStart: 18 }}>
          {t("publicationPlanning.selectionRequired")}
        </p>
      ) : null}
    </>
  );
}
