"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  createOpportunity,
  createProjectFromOpportunity,
  loadGaps,
  loadOpportunities,
  loadOpportunityPreview,
  loadProjectPreview,
  type Gap,
  type Opportunity,
  type OpportunitiesView,
  type OpportunityPreview,
  type ProjectPreview,
} from "@/lib/synthesis";

/**
 * الفرص البحثية — **ولا فرصة من فجوةٍ لم يعتمدها الباحث بنفسه**.
 *
 * البطاقة تجيب عن سبعة أسئلة، ومنها سؤالٌ لا يُحذف: **ما الذي ما زال غير
 * مؤكد؟** فبطاقةٌ بلا عدم يقينٍ معلن تُقرأ خطةً مثبتة، وهي عكس الغرض من
 * هذه الطبقة كلّها. ولذلك الحقل إلزاميّ هنا وفي العقد وفي القاعدة.
 *
 * **والمعاينة ليست إنشاء.** فتحُ البطاقة لا يكتب شيئًا؛ والإنشاء لا يقع
 * إلا بضغطةٍ ثانية على «أنشئ البطاقة».
 *
 * **و«إنشاء مشروع بحثي» معاينةٌ ثم تأكيد.** والمعاينة تقول ما **لن** يقع
 * أيضًا: لا تُنقل المراجع، ولا تُدرَج دراسة، ولا تتغيّر حالُ مرجعٍ واحد في
 * بحثك الحالي. وباحثٌ ظنّ أن مراجعه ستُنقل سيكتشف ظنّه بعد أسبوع.
 */

type Load = "loading" | "ready" | "failed";

interface Draft {
  gap: Gap;
  preview: OpportunityPreview;
  phenomenon: string;
  context: string;
  population: string;
  constructs: string;
  contribution: string;
  method: string;
  evidence: string;
  uncertainties: string;
}

/** بطاقةٌ لا تُنشأ بلا ظاهرةٍ وإسهامٍ وأدلةٍ **وعدمِ يقينٍ معلن**. */
function draftIsComplete(draft: Draft): boolean {
  return (
    draft.phenomenon.trim().length > 0 &&
    draft.contribution.trim().length > 0 &&
    draft.evidence.trim().length > 0 &&
    draft.uncertainties.trim().length > 0
  );
}

export default function ResearchOpportunitiesPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<OpportunitiesView | null>(null);
  const [approved, setApproved] = useState<Gap[]>([]);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [projectPreview, setProjectPreview] = useState<ProjectPreview | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return Promise.all([
      loadOpportunities(locale, projectId),
      loadGaps(locale, projectId),
    ])
      .then(([cards, gaps]) => {
        setData(cards);
        setApproved(gaps.gaps.filter((gap) => gap.may_become_opportunity));
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, projectId, say]);

  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  /** المعاينة تقرأ ولا تكتب — واستطلاعُ فكرةٍ لا يترك أثرًا في البحث. */
  const openDraft = (gap: Gap) => {
    setBusy(gap.id);
    setError(null);
    void loadOpportunityPreview(locale, projectId, gap.id)
      .then((preview) =>
        setDraft({
          gap,
          preview,
          phenomenon: "",
          context: "",
          population: "",
          constructs: "",
          contribution: "",
          method: "",
          evidence: preview.evidence_basis_ar,
          uncertainties: preview.still_uncertain_ar,
        }),
      )
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const submitDraft = () => {
    if (!draft || !draftIsComplete(draft)) return;
    setBusy(draft.gap.id);
    setError(null);
    void createOpportunity(locale, projectId, {
      gap_candidate_id: draft.gap.id,
      confirmed: true,
      phenomenon_ar: draft.phenomenon.trim(),
      context_ar: draft.context.trim() || null,
      population_ar: draft.population.trim() || null,
      constructs_ar: draft.constructs.trim() || null,
      possible_contribution_ar: draft.contribution.trim(),
      methodological_opportunity_ar: draft.method.trim() || null,
      evidence_basis_ar: draft.evidence.trim(),
      uncertainties_ar: draft.uncertainties.trim(),
    })
      .then(() => {
        setDraft(null);
        return refresh();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const openProjectPreview = (card: Opportunity) => {
    setBusy(card.id);
    setError(null);
    void loadProjectPreview(locale, projectId, card.id)
      .then((preview) => setProjectPreview(preview))
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const confirmProject = () => {
    if (!projectPreview) return;
    const id = projectPreview.from_opportunity_id;
    setBusy(id);
    setError(null);
    void createProjectFromOpportunity(
      locale,
      projectId,
      id,
      projectPreview.working_title_ar,
    )
      .then(() => {
        setProjectPreview(null);
        return refresh();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const cards = data?.opportunities ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("synthesis.opportunitiesTitle")}</h1>
      <p className="metric-label">{t("synthesis.opportunitiesMeaning")}</p>

      <nav aria-label={t("synthesis.tabsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/themes`}>
              {t("synthesis.themesTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/contradictions`}>
              {t("synthesis.contradictionsTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/gaps`}>
              {t("synthesis.gapsTitle")}
            </Link>
          </li>
        </ul>
      </nav>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="research-opportunities-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="research-opportunities-failed" style={{ color: "var(--muted)" }}>
          {t("synthesis.loadFailedNote")}
        </p>
      ) : (
        <>
          <section>
            <h2>{t("synthesis.approvedGapsTitle")}</h2>
            <p className="metric-label">{t("synthesis.approvedGapsMeaning")}</p>
            {approved.length === 0 ? (
              <p className="metric-label">{t("synthesis.noApprovedGaps")}</p>
            ) : (
              <ul style={{ paddingInlineStart: 18 }}>
                {approved.map((gap) => (
                  <li key={gap.id} style={{ marginBlockEnd: 6 }}>
                    <strong>{gap.gap_type_label_ar}</strong> — {gap.description_ar}
                    <div>
                      <button
                        type="button"
                        className="chip chip-stage"
                        aria-label={`${t("synthesis.buildOpportunity")}: ${gap.gap_type_label_ar}`}
                        disabled={busy === gap.id}
                        onClick={() => openDraft(gap)}
                      >
                        {t("synthesis.buildOpportunity")}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {cards.length === 0 ? (
            <p data-testid="research-opportunities-empty" style={{ color: "var(--muted)" }}>
              {t("synthesis.opportunitiesEmpty")}
            </p>
          ) : (
            <section style={{ marginBlockStart: "var(--space)" }}>
              <h2>{t("synthesis.cardsTitle")}</h2>
              <p className="metric-label">{data?.note_ar}</p>
              <div style={{ display: "grid", gap: 12 }}>
                {cards.map((card) => (
                  <article className="card" key={card.id}>
                    <span className="chip chip-muted">{card.gap_type_label_ar}</span>
                    <strong style={{ display: "block", marginBlockStart: 6 }}>
                      {card.phenomenon_ar}
                    </strong>
                    <p style={{ marginBlock: 6 }}>
                      <strong>{t("synthesis.contributionLabel")}: </strong>
                      {card.possible_contribution_ar}
                    </p>
                    <p style={{ marginBlock: 6 }}>
                      <strong>{t("synthesis.evidenceLabel")}: </strong>
                      {card.evidence_basis_ar}
                    </p>
                    {/* **السؤال الذي لا يُحذف.** */}
                    <p style={{ marginBlock: 6 }}>
                      <strong>{t("synthesis.uncertaintiesLabel")}: </strong>
                      {card.uncertainties_ar}
                    </p>
                    {card.context_ar ? (
                      <div className="metric-label">
                        {t("synthesis.contextLabel")}: {card.context_ar}
                      </div>
                    ) : null}
                    {card.population_ar ? (
                      <div className="metric-label">
                        {t("synthesis.populationLabel")}: {card.population_ar}
                      </div>
                    ) : null}
                    {card.methodological_opportunity_ar ? (
                      <div className="metric-label">
                        {t("synthesis.methodLabel")}: {card.methodological_opportunity_ar}
                      </div>
                    ) : null}

                    {card.spawned_project_id ? (
                      <p className="metric-label">{t("synthesis.projectAlreadyCreated")}</p>
                    ) : (
                      <button
                        type="button"
                        className="chip chip-stage"
                        aria-label={`${t("synthesis.createProject")}: ${card.phenomenon_ar}`}
                        disabled={busy === card.id}
                        onClick={() => openProjectPreview(card)}
                      >
                        {t("synthesis.createProject")}
                      </button>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {draft ? (
        <div
          className="card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="draft-title"
          style={{ marginBlockStart: 16 }}
        >
          <strong id="draft-title">
            {t("synthesis.draftTitle")}: {draft.preview.gap_type_label_ar}
          </strong>

          {/* سبعةُ أسئلةٍ بأجوبتها — مقروءةً من الفجوة، قبل أن يكتب الباحث. */}
          <p style={{ marginBlock: 6 }}>
            <strong>{t("synthesis.noticedLabel")}: </strong>
            {draft.preview.what_we_noticed_ar}
          </p>
          <p style={{ marginBlock: 6 }}>
            <strong>{t("synthesis.whyLabel")}: </strong>
            {draft.preview.why_it_might_matter_ar}
          </p>
          <p style={{ marginBlock: 6 }}>
            <strong>{t("synthesis.evidenceLabel")}: </strong>
            {draft.preview.evidence_basis_ar}
          </p>
          <p style={{ marginBlock: 6 }}>
            <strong>{t("synthesis.relatedLabel")}: </strong>
            {draft.preview.related_studies.map((study) => study.title).join(" · ") ||
              t("synthesis.notRecorded")}
          </p>
          <p style={{ marginBlock: 6 }}>
            <strong>{t("synthesis.uncertaintiesLabel")}: </strong>
            {draft.preview.still_uncertain_ar}
          </p>
          <p style={{ marginBlock: 6 }}>
            <strong>{t("synthesis.nextStepLabel")}: </strong>
            {draft.preview.next_step_ar}
          </p>
          <div className="metric-label">
            {draft.preview.strength_label_ar} — {draft.preview.strength_meaning_ar}
          </div>

          <p className="metric-label" style={{ marginBlockStart: 8 }}>
            {t("synthesis.draftIsYours")}
          </p>

          <label htmlFor="draft-phenomenon" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.phenomenonLabel")}
          </label>
          <textarea
            id="draft-phenomenon"
            rows={2}
            value={draft.phenomenon}
            onChange={(event) => setDraft({ ...draft, phenomenon: event.target.value })}
          />

          <label htmlFor="draft-context" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.contextLabel")}
          </label>
          <textarea
            id="draft-context"
            rows={2}
            value={draft.context}
            onChange={(event) => setDraft({ ...draft, context: event.target.value })}
          />

          <label htmlFor="draft-population" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.populationLabel")}
          </label>
          <textarea
            id="draft-population"
            rows={2}
            value={draft.population}
            onChange={(event) => setDraft({ ...draft, population: event.target.value })}
          />

          <label htmlFor="draft-constructs" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.constructsLabel")}
          </label>
          <textarea
            id="draft-constructs"
            rows={2}
            value={draft.constructs}
            onChange={(event) => setDraft({ ...draft, constructs: event.target.value })}
          />

          <label htmlFor="draft-contribution" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.contributionLabel")}
          </label>
          <textarea
            id="draft-contribution"
            rows={2}
            value={draft.contribution}
            onChange={(event) => setDraft({ ...draft, contribution: event.target.value })}
          />

          <label htmlFor="draft-method" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.methodLabel")}
          </label>
          <textarea
            id="draft-method"
            rows={2}
            value={draft.method}
            onChange={(event) => setDraft({ ...draft, method: event.target.value })}
          />

          <label htmlFor="draft-evidence" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.evidenceLabel")}
          </label>
          <textarea
            id="draft-evidence"
            rows={2}
            value={draft.evidence}
            onChange={(event) => setDraft({ ...draft, evidence: event.target.value })}
          />

          <label htmlFor="draft-uncertainties" style={{ display: "block", marginBlockStart: 8 }}>
            {t("synthesis.uncertaintiesRequired")}
          </label>
          <textarea
            id="draft-uncertainties"
            rows={3}
            value={draft.uncertainties}
            onChange={(event) => setDraft({ ...draft, uncertainties: event.target.value })}
          />

          <div style={{ display: "flex", gap: 6, marginBlockStart: 8 }}>
            {/* زرٌّ مُفعَّل لا يفعل شيئًا يُعلّم الباحث ألّا يثق بالأزرار. */}
            <button
              type="button"
              className="chip chip-stage"
              disabled={!draftIsComplete(draft) || busy === draft.gap.id}
              onClick={submitDraft}
            >
              {t("synthesis.createCard")}
            </button>
            <button type="button" className="chip chip-muted" onClick={() => setDraft(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : null}

      {projectPreview ? (
        <div
          className="card"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="project-preview-title"
          style={{ marginBlockStart: 16 }}
        >
          <strong id="project-preview-title">
            {t("synthesis.projectPreviewTitle")}: {projectPreview.working_title_ar}
          </strong>

          <p style={{ marginBlockStart: 8 }}>
            <strong>{t("synthesis.willCreate")}</strong>
          </p>
          <ul style={{ paddingInlineStart: 18 }}>
            {projectPreview.will_create_ar.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>

          {/* **ما لن يقع يُقال بصوتٍ عالٍ** — وإلا ظنّ الباحث أن مراجعه نُقلت. */}
          <p>
            <strong>{t("synthesis.willNotCreate")}</strong>
          </p>
          <ul style={{ paddingInlineStart: 18 }}>
            {projectPreview.will_not_create_ar.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>

          <p>
            <strong>{t("synthesis.unchanged")}</strong>
          </p>
          <ul style={{ paddingInlineStart: 18 }}>
            {projectPreview.unchanged_ar.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>

          <div style={{ display: "flex", gap: 6, marginBlockStart: 8 }}>
            {/* **التأكيد شرطٌ يقوله الخادم** — والواجهة لا تفترضه ولا تتجاوزه. */}
            <button
              type="button"
              className="chip chip-stage"
              disabled={
                !projectPreview.requires_confirmation ||
                busy === projectPreview.from_opportunity_id
              }
              onClick={confirmProject}
            >
              {t("synthesis.confirmCreateProject")}
            </button>
            <button
              type="button"
              className="chip chip-muted"
              onClick={() => setProjectPreview(null)}
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
