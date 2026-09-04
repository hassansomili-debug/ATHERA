"use client";

import { type Messages, translator } from "@/lib/i18n";

/**
 * عرض رد أثيرا AI.
 *
 * الرد يُفصل بصريًا لأن خلطه يضلّل: الاقتراح شيء، وحالة الدليل شيء، والحدّ
 * المعلن شيء ثالث. ونص واحد متصل يجعل القارئ يقرأ الاقتراح نتيجةً.
 *
 * ولا اسم أجنت ولا أداة ولا مزوّد ولا معرّف أثر — «أثيرا AI» هي الهوية.
 */
export interface AttachmentState {
  file_id: string;
  filename: string;
  processing_status: string;
  consent_state: string;
  approved_facts: number;
  pending_review: number;
  /** الفعل التالي بكلمة واحدة: process | review | chat_consent | none */
  needs: string;
}

/**
 * مرجعٌ أعادته الفهارس العلمية — **بنسبته لا بلا نسبة**.
 *
 * و`citation_counts` قاموسٌ لا رقم: Crossref يقول ١٢٠ وOpenAlex يقول ١٣٤،
 * وليس أحدهما كاذبًا — هما يعدّان مجموعتين. فدمجُهما يخترع رقمًا لا يقوله
 * أحد، وعرضُ أحدهما بلا اسمه يجعل ادعاء فهرسٍ حكمًا للمنصّة.
 */
export interface DiscoveredReference {
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  providers: string[];
  citation_counts: Record<string, number>;
  open_access: boolean | null;
  retraction_status: string;
  scope: string;
  can_be_saved: boolean;
}

/** محلّلُ الـDOI الرسمي — عنوانٌ واحد لا يُكرَّر في كل بطاقة. */
const DOI_RESOLVER = "https://doi.org/";

export interface ProviderStatusLine {
  provider: string;
  ok: boolean;
  results: number;
  detail: string | null;
}

export interface ProjectContext {
  project_id: string;
  working_title: string;
  status: string;
  current_gate: string | null;
}

export interface AiAnswer {
  answer: string;
  status: string;
  evidence_state: string;
  capabilities_used: string[];
  limitations: string[];
  recommended_next_actions: string[];
  attachment?: AttachmentState | null;
  intent?: string;
  search_performed?: boolean;
  references?: DiscoveredReference[];
  provider_statuses?: ProviderStatusLine[];
  project?: ProjectContext | null;
}

export function AiAnswerCard({
  messages, data, onSave,
}: {
  messages: Messages;
  data: AiAnswer;
  /** حفظُ المرجع في المكتبة — فعلٌ يملكه المُضيف، والبطاقة تعرضه فقط. */
  onSave?: (doi: string) => void;
}) {
  const t = translator(messages);
  const references = data.references ?? [];
  const failed = (data.provider_statuses ?? []).filter((one) => !one.ok);
  const evidenceLabel =
    data.evidence_state === "verified" ? t("ai.evidenceVerified")
    : data.evidence_state === "search_results" ? t("ai.evidenceSearch")
    : data.evidence_state === "model_suggestion" ? t("ai.evidenceSuggestion")
    : t("ai.evidenceNone");

  return (
    <section
      className="card"
      data-testid="ai-answer"
      style={{ marginBlockStart: 18, maxInlineSize: "78ch" }}
    >
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockEnd: 10 }}>
        <span className={`chip ${data.evidence_state === "verified" ? "chip-ok" : "chip-stage"}`}>
          {evidenceLabel}
        </span>
        {data.status !== "ok" ? (
          <span className="chip chip-warn">{t(`ai.status_${data.status}`)}</span>
        ) : null}
        {/* **سياقُ البحث يُرى، لا يُفترض.** الباحث الذي يسأل داخل بحثٍ
            يحتاج أن يعرف أيّ بحثٍ أُجيب فيه. */}
        {data.project ? (
          <span className="chip chip-muted" data-testid="ai-project-context">
            {t("ai.projectContext")}: {data.project.working_title}
          </span>
        ) : null}
      </div>

      <p data-testid="ai-answer-text" style={{ whiteSpace: "pre-wrap", marginBlock: 0 }}>
        {data.answer}
      </p>

      {/* ── المراجع المكتشَفة: **كلُّ قيمةٍ منسوبةٌ إلى قائلها** ── */}
      {references.length > 0 ? (
        <div style={{ marginBlockStart: 16 }} data-testid="ai-references">
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 6 }}>
            {t("ai.referencesLabel")}
          </p>
          <ul style={{ margin: 0, paddingInlineStart: 0, listStyle: "none" }}>
            {references.map((one, index) => {
              // يُلتقط قبل الإغلاق: TypeScript لا يبقي تضييق خاصّية كائنٍ
              // داخل دالّةٍ مغلقة، فيصير `one.doi` من جديد `string | null`.
              const doi = one.doi;
              return (
              <li
                key={doi ?? `${one.providers[0]}-${index}`}
                style={{ marginBlockEnd: 12, fontSize: 14 }}
              >
                <strong>{one.title}</strong>
                <div style={{ color: "var(--muted)" }}>
                  {/* والحقلُ الذي لم يقله فهرسٌ يُكتب «غير مذكور» — لا يُترك
                      فراغًا يُقرأ قيمة. */}
                  {one.authors.length > 0 ? one.authors.join("، ") : t("ai.refUnstated")}
                  {" · "}
                  {one.year ?? t("ai.refUnstated")}
                  {one.venue ? ` · ${one.venue}` : ""}
                </div>
                <div style={{ color: "var(--muted)", fontSize: 13 }}>
                  {t("ai.refSaidBy")}: {one.providers.join("، ")}
                  {Object.keys(one.citation_counts).length > 0
                    ? ` · ${t("ai.refCitations")}: ${Object.entries(one.citation_counts)
                        .map(([name, value]) => `${name} ${value}`).join("، ")}`
                    : ""}
                  {one.retraction_status === "retracted"
                    ? ` · ${t("ai.refRetracted")}` : ""}
                </div>
                <div style={{ display: "flex", gap: 10, marginBlockStart: 4 }}>
                  {doi ? (
                    <a href={`${DOI_RESOLVER}${doi}`} target="_blank" rel="noreferrer">
                      {doi}
                    </a>
                  ) : null}
                  {/* والفعلُ التالي زرٌّ لا تعليمة: الحفظ يقع بمعرّفٍ شرعي
                      وحده، فبلا DOI لا يُعرض زرٌّ يَعِد ثم يخذل. */}
                  {one.can_be_saved && doi && onSave ? (
                    <button
                      type="button"
                      onClick={() => onSave(doi)}
                      aria-label={`${t("ai.refSave")}: ${one.title}`}
                    >
                      {t("ai.refSave")}
                    </button>
                  ) : null}
                </div>
              </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {/* **فهرسٌ لم يُجب ليس فهرسًا قال «لا يوجد».** */}
      {failed.length > 0 ? (
        <p className="metric-label" style={{ marginBlockStart: 10 }}>
          {t("ai.refIndexDown")}: {failed.map((one) => one.provider).join("، ")}
        </p>
      ) : null}

      {data.limitations.length > 0 ? (
        <div className="gate" style={{ marginBlockStart: 14 }}>
          <span aria-hidden="true">◆</span>
          <span>
            <strong>{t("ai.limitations")}</strong>
            <ul style={{ margin: "6px 0 0", paddingInlineStart: "1.1rem" }}>
              {data.limitations.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </span>
        </div>
      ) : null}

      {data.recommended_next_actions.length > 0 ? (
        <div style={{ marginBlockStart: 14 }}>
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 6 }}>
            {t("ai.nextActions")}
          </p>
          <ul style={{ margin: 0, paddingInlineStart: "1.1rem", fontSize: 14 }}>
            {data.recommended_next_actions.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
