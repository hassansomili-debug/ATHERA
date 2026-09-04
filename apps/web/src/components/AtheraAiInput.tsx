"use client";

import { useEffect, useRef, useState } from "react";

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
/** حال المعالجة نصًّا — من حالات الخادم الحقيقية لا من تخمين الواجهة. */
const STATE_LABEL: Record<string, string> = {
  not_processed: "ai.stateNotProcessed",
  parsing: "ai.stateProcessing",
  extracting: "ai.stateProcessing",
  awaiting_consent: "ai.stateAwaitingConsent",
  awaiting_review: "ai.stateAwaitingReview",
  completed: "ai.stateReady",
  extract_failed: "ai.stateFailed",
  parse_failed: "ai.stateFailed",
};


export function AtheraAiInput({
  locale, messages, rows = 3, seed, attachFileId, projectId,
}: {
  locale: Locale;
  messages: Messages;
  rows?: number;
  seed?: string;
  /** مستندٌ في مكتبته يسأل عنه — يُرفَق باسمه، ولا يُطلب منه رفعه ثانية. */
  attachFileId?: string;
  /** البحثُ الذي يعمل فيه — يُرسَل بمعرّفه، والخادم يتحقّق من مستأجره. */
  projectId?: string;
}) {
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
  // آخر سؤال — يُعاد إرساله بعد الإذن، فلا يُطلب من الباحث كتابته ثانية.
  const [pending, setPending] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const disabled = loading || !modelEnabled || busy;

  // **المرفق قد يأتي من مكتبته لا من قرصه.** والاسم يُقرأ من الخادم: لا
  // يُحمَل في الرابط اسمُ ملفٍ قد لا يكون له.
  useEffect(() => {
    if (!attachFileId) return;
    let live = true;
    void apiFetch<{ id: string; original_filename: string }>(
      `/api/v1/files/${attachFileId}`, { locale },
    )
      .then((record) => {
        if (live) setAttached({ id: record.id, name: record.original_filename });
      })
      .catch((err) => {
        if (live) {
          setError(err instanceof AtheraApiError ? err.localized(locale) : t("ai.askFailed"));
        }
      });
    return () => { live = false; };
  }, [attachFileId, locale, t]);

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

  async function ask(question?: string) {
    const text = (question ?? value).trim();
    setBusy(true);
    setError(null);
    setAnswer(null);
    setPending(text);
    try {
      setAnswer(await apiFetch<AiAnswer>("/api/v1/ai/ask", {
        method: "POST",
        locale,
        // الملف المرفق يُمرَّر بمعرّفه — والخادم يقرّر ما يجوز قراءته منه.
        body: JSON.stringify({
          question: text,
          ...(attached ? { file_id: attached.id } : {}),
          ...(projectId ? { project_id: projectId } : {}),
        }),
      }));
    } catch (err) {
      // خطأ المزوّد يصل مترجَمًا — ولا يُستبدل بنصّ مُولَّد.
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("ai.askFailed"));
    } finally {
      setBusy(false);
    }
  }

  /** يمنح إذن السؤال عن المستند ثم **يُعيد السؤال نفسه** — بلا كتابةٍ ثانية. */
  async function authorizeAndAsk(fileId: string) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/theses/files/${fileId}/chat-consent?decision=grant`, {
        method: "POST", locale,
      });
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("ai.askFailed"));
      setBusy(false);
      return;
    }
    setBusy(false);
    await ask(pending ?? value);
  }

  /** يحفظ مرجعًا مكتشَفًا في مكتبته — **بمعرّفٍ شرعي وحده**.
   *
   * ونتيجةُ بحثٍ ليست مرجعًا محفوظًا: الحفظ فعلٌ مستقلّ يقرّره الباحث،
   * ويقع عبر مسار الاستيراد القائم بـDOI. ولا يُخزَّن شيءٌ بلا معرّف.
   */
  async function saveReference(doi: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await apiFetch("/api/v1/sources/import", {
        method: "POST", locale, body: JSON.stringify({ doi }),
      });
      setNotice(`${t("ai.refSaved")} — ${doi}`);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("ai.refSaveFailed"));
    } finally {
      setBusy(false);
    }
  }

  /** يبدأ معالجة المستند من هنا — فلا يُطلب من الباحث أن يبحث عن مكانها. */
  async function startProcessing(fileId: string) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/theses/process-file/${fileId}`, { method: "POST", locale });
      setError(null);
      setAnswer(null);
      setNotice(t("ai.processStarted"));
    } catch (err) {
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
            {/* **`sr-only` تخفي بالعين وتُبقي في شجرة الإتاحة.** فكان قارئ
                الشاشة يجد هنا حقل ملفٍّ بلا اسمٍ مُعلَن — «اختيار ملف» وحدها —
                بينما زرّ «📎 أرفق ملفًا» بجانبه هو المدخل الحقيقي. فمدخلان
                لفعلٍ واحد، أحدهما بلا اسم. و`hidden` تُخرجه من الشجرة ولا
                تمنع `.click()` عليه — وهو ما يفعله `ThesisIntake` أصلًا. */}
            <input
              ref={fileInput}
              type="file"
              hidden
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
        <p data-testid="ai-attachment" style={{ marginBlockStart: 10 }}>
          📎 {t("ai.attached")}: {attached.name}{" "}
          <button type="button" onClick={() => setAttached(null)}>{t("ai.detach")}</button>
        </p>
      ) : null}

      {/* ── الفعل التالي زرًّا، لا تعليمةً يُنفّذها الباحث بنفسه ──
          كانت الحدود تُقال نصًّا: «امنح الإذن…» — أي بنداء API. والباحث
          لا يملك طرفية، ولا يجب أن يملكها. */}
      {answer?.attachment ? (
        <section className="card" style={{ marginBlockStart: 14 }}>
          <div className="metric-label">
            {t("ai.fileState")}: {answer.attachment.filename} —{" "}
            {t(STATE_LABEL[answer.attachment.processing_status] ?? "ai.stateNotProcessed")}
            {answer.attachment.approved_facts > 0
              ? ` · ${answer.attachment.approved_facts} ${t("ai.consentFacts")}`
              : ""}
          </div>

          {answer.attachment.needs === "chat_consent" ? (
            <>
              <h3>{t("ai.consentTitle")}</h3>
              <p>{t("ai.consentBody")}</p>
              <p className="metric-label">
                {answer.attachment.approved_facts} {t("ai.consentFacts")}
              </p>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void authorizeAndAsk(answer.attachment!.file_id)}
                >
                  {t("ai.consentAllow")}
                </button>
                <button type="button" disabled={busy} onClick={() => setAnswer(null)}>
                  {t("ai.consentCancel")}
                </button>
              </div>
            </>
          ) : null}

          {answer.attachment.needs === "process" ? (
            <>
              <p>{t("ai.needsProcess")}</p>
              <button
                type="button"
                disabled={busy}
                onClick={() => void startProcessing(answer.attachment!.file_id)}
              >
                {t("ai.needsProcessAction")}
              </button>
            </>
          ) : null}

          {answer.attachment.needs === "review" ? (
            <>
              <p>{t("ai.needsReview")}</p>
              <a href={`/${locale}/theses`}>{t("ai.needsReviewAction")}</a>
            </>
          ) : null}
        </section>
      ) : null}

      {notice ? <p style={{ marginBlockStart: 10 }}>{notice}</p> : null}
      {/* الخطأ يُعلَن: «لم يحدث شيء» ليست حالة يجوز أن يراها الباحث. */}
      {error ? (
        <p className="error" role="alert" data-testid="ai-error" style={{ marginBlockStart: 10 }}>
          {error}
        </p>
      ) : null}
      {answer ? (
        <AiAnswerCard
          messages={messages}
          data={answer}
          onSave={(doi) => void saveReference(doi)}
        />
      ) : null}

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
