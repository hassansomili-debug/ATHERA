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
export interface AiAnswer {
  answer: string;
  status: string;
  evidence_state: string;
  capabilities_used: string[];
  limitations: string[];
  recommended_next_actions: string[];
}

export function AiAnswerCard({
  messages, data,
}: { messages: Messages; data: AiAnswer }) {
  const t = translator(messages);
  const evidenceLabel =
    data.evidence_state === "verified" ? t("ai.evidenceVerified")
    : data.evidence_state === "model_suggestion" ? t("ai.evidenceSuggestion")
    : t("ai.evidenceNone");

  return (
    <section className="card" style={{ marginBlockStart: 18, maxInlineSize: "78ch" }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockEnd: 10 }}>
        <span className={`chip ${data.evidence_state === "verified" ? "chip-ok" : "chip-stage"}`}>
          {evidenceLabel}
        </span>
        {data.status !== "ok" ? (
          <span className="chip chip-warn">{t(`ai.status_${data.status}`)}</span>
        ) : null}
      </div>

      <p style={{ whiteSpace: "pre-wrap", marginBlock: 0 }}>{data.answer}</p>

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
