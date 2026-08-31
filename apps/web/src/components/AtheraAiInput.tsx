"use client";

import { useState } from "react";

import { type Locale, type Messages, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * مدخل أثيرا AI.
 *
 * **لا يدّعي إنجازًا.** ما دام مزوّد النموذج «لا مزوّد»، يبقى الإرسال معطّلًا
 * ويُعلَن السبب — لا نتيجة مولَّدة، ولا شريط تقدّم يوحي بعمل يجري. البوابة
 * تُقرأ من الخادم لا من ثابت في الواجهة.
 */
export function AtheraAiInput({
  locale, messages, rows = 3,
}: { locale: Locale; messages: Messages; rows?: number }) {
  const t = translator(messages);
  const { modelEnabled, loading } = usePosture(locale);
  const [value, setValue] = useState("");
  const disabled = loading || !modelEnabled;

  return (
    <>
      <div className="ai-box">
        <div className="ai-inner">
          <label className="sr-only" htmlFor="athera-ai-input">{t("ai.placeholder")}</label>
          <textarea
            id="athera-ai-input"
            rows={rows}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={t("ai.placeholder")}
          />
          <div className="ai-tools">
            <button type="button" className="ai-tool" disabled={disabled}>📎 {t("ai.upload")}</button>
            <button type="button" className="ai-tool" disabled={disabled}>🔗 {t("ai.link")}</button>
            <button type="button" className="ai-tool" disabled={disabled}>🎙 {t("ai.voice")}</button>
            <button type="button" className="ai-send" disabled={disabled || value.trim() === ""}>
              {t("ai.send")}
            </button>
          </div>
        </div>
      </div>

      {!loading && !modelEnabled ? (
        <div className="gate" style={{ marginBlockStart: 12 }}>
          <span aria-hidden="true">⏻</span>
          <span>
            <strong>{t("ai.gateTitle")}</strong> {t("ai.gateBody")}
          </span>
        </div>
      ) : null}
    </>
  );
}
