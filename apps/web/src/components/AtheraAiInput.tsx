"use client";

import { useRef, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { AiAnswerCard, type AiAnswer } from "./AiAnswer";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * مدخل أثيرا AI.
 *
 * **لا يدّعي إنجازًا.** ما دام مزوّد النموذج «لا مزوّد»، يبقى الإرسال معطّلًا
 * ويُعلَن السبب — لا نتيجة مولَّدة، ولا شريط تقدّم يوحي بعمل يجري. البوابة
 * تُقرأ من الخادم لا من ثابت في الواجهة.
 *
 * **وثلاثة أزرار كانت تُعرض كأنها تعمل.** المرفق والرابط والصوت: تُرسَم
 * قابلةً للنقر، وليس لواحدٍ منها معالج. والمستخدم يضغط فلا يحدث شيء — ولا
 * رسالة تقول لماذا. وزرٌّ ميت أسوأ من زرٍّ غائب: الأول يَعِد ثم يخذل.
 *
 * فالمرفق صار يعمل فعلًا، والآخران يقولان «قريبًا» صراحةً.
 */
export function AtheraAiInput({
  locale, messages, rows = 3, seed,
}: { locale: Locale; messages: Messages; rows?: number; seed?: string }) {
  const t = translator(messages);
  const { modelEnabled, modelGateReason, loading } = usePosture(locale);
  const [value, setValue] = useState("");
  // نصٌّ يأتي من مقترحات البداية — يملأ المدخل ويبقى قابلًا للتعديل.
  const [lastSeed, setLastSeed] = useState("");
  if (seed && seed !== lastSeed) {
    setLastSeed(seed);
    setValue(seed);
  }
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<AiAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attached, setAttached] = useState<{ id: string; name: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const disabled = loading || !modelEnabled || busy;

  /** يرفع الملف فعلًا عبر مسار الرفع القائم، ويُظهر ما أُرفق. */
  async function attach(file: File) {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("upload", file);
      form.append("classification", "C2");
      const stored = await apiFetch<{ id: string; original_filename: string }>(
        "/api/v1/files/upload", { method: "POST", locale, body: form },
      );
      setAttached({ id: stored.id, name: stored.original_filename });
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("ai.uploadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function ask() {
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await apiFetch<AiAnswer>("/api/v1/ai/ask", {
        method: "POST",
        locale,
        // الملف المرفق يُمرَّر بمعرّفه — والخادم يقرّر ما يجوز قراءته منه.
        body: JSON.stringify({
          question: value.trim(),
          ...(attached ? { file_id: attached.id } : {}),
        }),
      }));
    } catch (err) {
      // خطأ المزوّد يصل مترجَمًا — ولا يُستبدل بنصّ مُولَّد.
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("ai.askFailed"));
    } finally {
      setBusy(false);
    }
  }

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
            <input
              ref={fileInput}
              type="file"
              className="sr-only"
              onChange={(e) => {
                const picked = e.target.files?.[0];
                if (picked) void attach(picked);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              className="ai-tool"
              disabled={disabled}
              onClick={() => fileInput.current?.click()}
            >
              📎 {t("ai.upload")}
            </button>
            {/* معطَّلان بإعلان — لا يُرسمان قابلين للنقر بلا معالج. */}
            <button type="button" className="ai-tool" disabled title={t("ai.soon")}>
              🔗 {t("ai.link")} — {t("ai.soon")}
            </button>
            <button type="button" className="ai-tool" disabled title={t("ai.soon")}>
              🎙 {t("ai.voice")} — {t("ai.soon")}
            </button>
            <button
              type="button"
              className="ai-send"
              disabled={disabled || value.trim().length < 8}
              onClick={() => void ask()}
            >
              {busy ? t("ai.thinking") : t("ai.send")}
            </button>
          </div>
        </div>
      </div>

      {attached ? (
        <p style={{ marginBlockStart: 10 }}>
          📎 {t("ai.attached")}: {attached.name}{" "}
          <button type="button" onClick={() => setAttached(null)}>{t("ai.detach")}</button>
        </p>
      ) : null}

      {error ? <p className="error" style={{ marginBlockStart: 10 }}>{error}</p> : null}
      {answer ? <AiAnswerCard messages={messages} data={answer} /> : null}

      {/* السبب يُعرض كما هو — لا سببٌ واحد يُفترض لكل إغلاق. */}
      {!loading && !modelEnabled ? (
        <div className="gate" style={{ marginBlockStart: 12 }}>
          <span aria-hidden="true">⏻</span>
          <span>
            <strong>
              {modelGateReason === "unreachable"
                ? t("ai.gateUnreachableTitle")
                : t("ai.gateTitle")}
            </strong>{" "}
            {modelGateReason === "unreachable"
              ? t("ai.gateUnreachableBody")
              : t("ai.gateBody")}
          </span>
        </div>
      ) : null}
    </>
  );
}
