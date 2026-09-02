"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * رفع الرسالة ثم متابعة قراءتها.
 *
 * **الرفع أولًا، لا نموذج تسجيل.** الباحث لا يعرف بيانات رسالته أفضل من
 * رسالته: يرفعها فتُقرأ، ويراجع ما قُرئ. والنموذج اليدوي باقٍ أسفل الصفحة
 * لمن يسجّل رسالةً بلا ملف.
 *
 * **والحالات المعروضة هي ما في القاعدة.** لا «جارٍ التحليل» تُعرض على
 * تشغيلة ماتت، ولا «تم» قبل أن تصل. الحالة تُقرأ من الخادم، والاستطلاع
 * يتوقف عند حالة نهائية بدل أن يظل يقصف الـAPI بلا سبب.
 */
type Phase =
  | "idle"
  | "uploading"
  | "stored"
  | "parsing"
  | "parsed"
  | "extracting"
  | "awaiting_review"
  | "verified"
  | "parse_failed"
  | "extract_failed"
  | "awaiting_consent"
  | "local_only";

interface ExtractionState {
  thesis_id: string;
  file_id: string | null;
  status: Phase;
  chunks: number;
  candidates: number;
  error: string | null;
  message: string;
}

const TERMINAL: ReadonlySet<string> = new Set([
  "awaiting_review", "verified", "parse_failed", "extract_failed",
  // الانتظار والرفض حالتان مستقرّتان — لا يُستطلَع بعدهما.
  "awaiting_consent", "local_only",
]);

const STATE_KEY: Record<string, string> = {
  stored: "theses.stateStored",
  parsing: "theses.stateParsing",
  parsed: "theses.stateParsed",
  extracting: "theses.stateExtracting",
  awaiting_review: "theses.stateAwaitingReview",
  verified: "theses.stateVerified",
  parse_failed: "theses.stateParseFailed",
  extract_failed: "theses.stateExtractionFailed",
  awaiting_consent: "theses.stateAwaitingConsent",
  local_only: "theses.stateLocalOnly",
};

/** إذن إرسال هذا المستند إلى مزوّد خارجي — نصّه يأتي من الخادم لا من ترجمة. */
interface Consent {
  file_id: string;
  state: "granted" | "declined" | "absent";
  capability: string;
  max_classification: string;
  provider: string;
  model: string | null;
  title: string;
  body: string;
  accept_label: string;
  decline_label: string;
  revoke_label: string;
  excluded_chunks: Record<string, number>;
}

const ACCEPT = ".pdf,.docx,.doc,.txt";

export function ThesisIntake({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const { items } = usePosture(locale);
  const storageReady = items.find((i) => i.key === "storage")?.value !== "none";

  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [state, setState] = useState<ExtractionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState<Consent | null>(null);

  const poll = useCallback(
    async (thesisId: string) => {
      try {
        const next = await apiFetch<ExtractionState>(
          `/api/v1/theses/${thesisId}/extraction`, { locale },
        );
        setState(next);
        setPhase(next.status);
        setConsent(
          await apiFetch<Consent>(`/api/v1/theses/${thesisId}/consent`, { locale }),
        );
      } catch (err) {
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
      }
    },
    [locale, t],
  );

  // الاستطلاع يتوقف عند حالة نهائية — ولا يستمر بعد انتهاء العمل.
  useEffect(() => {
    if (!state || TERMINAL.has(state.status)) return;
    const id = window.setTimeout(() => void poll(state.thesis_id), 2500);
    return () => window.clearTimeout(id);
  }, [state, poll]);

  async function send(selected: File) {
    setPhase("uploading");
    setError(null);
    setState(null);
    try {
      const body = new FormData();
      body.append("upload", selected);
      // عبر عميل الـAPI: حارس الإعداد وتوحيد الأخطاء ومعالجة انتهاء الجلسة
      // كلها فيه، وكان الالتفاف عليه لأجل ترويسة `FormData` وحدها.
      const started = await apiFetch<ExtractionState>("/api/v1/theses/upload", {
        method: "POST", locale, body,
      });
      setState(started);
      setPhase(started.status);
    } catch (err) {
      setPhase("idle");
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("upload.failed"));
    }
  }

  async function decideConsent(decision: "grant" | "decline" | "revoke") {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      setConsent(
        await apiFetch<Consent>(`/api/v1/theses/${state.thesis_id}/consent`, {
          method: "POST",
          locale,
          body: JSON.stringify({ decision }),
        }),
      );
      if (decision === "grant") await poll(state.thesis_id);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function reprocess() {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiFetch<ExtractionState>(
        `/api/v1/theses/${state.thesis_id}/reprocess`, { method: "POST", locale },
      );
      setState(next);
      setPhase(next.status);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  // رفض الإرسال قرارٌ يُحترم، لا عطبٌ يُلوَّن بلون الخطأ.
  const failed = phase === "parse_failed" || phase === "extract_failed";

  return (
    <section className="card" style={{ display: "grid", gap: 10 }}>
      <div>
        <strong style={{ fontSize: 17 }}>{t("theses.uploadTitle")}</strong>
        <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>{t("theses.uploadHint")}</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          const selected = event.target.files?.[0];
          if (selected) void send(selected);
          event.target.value = "";
        }}
      />
      <div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={!storageReady || phase === "uploading"}
          style={{
            padding: "10px 20px", border: "none", borderRadius: "var(--radius)",
            background: "var(--athera-aqua, var(--athera-teal))", color: "#04302c",
            font: "inherit", fontWeight: 600,
            cursor: storageReady && phase !== "uploading" ? "pointer" : "not-allowed",
            opacity: storageReady && phase !== "uploading" ? 1 : 0.5,
          }}
        >
          {phase === "uploading" ? t("theses.uploadingLabel") : t("theses.uploadCtaFile")}
        </button>
      </div>

      {/* حدّ معلن لا مفاجأة: الممسوح ضوئيًا لا يُقرأ، ويُقال قبل الرفع. */}
      <p className="provenance-note" style={{ margin: 0 }}>{t("theses.noOcr")}</p>

      {state ? (
        <div
          style={{
            borderInlineStart: `3px solid ${failed ? "var(--athera-amber, #F59E0B)" : "var(--athera-teal)"}`,
            paddingInlineStart: 12, display: "grid", gap: 4,
          }}
        >
          <strong>{t(STATE_KEY[state.status] ?? "theses.stateStored")}</strong>
          <span className="metric-label">
            {state.chunks} {t("theses.chunksLabel")} · {state.candidates}{" "}
            {t("theses.candidatesLabel")}
          </span>
          {/* سبب الفشل يُعرض كما ورد — لا رسالة عامة تخفي ما حدث. */}
          {state.error ? <span className="metric-label">{state.error}</span> : null}

          {/* ── بوابة الإذن ──
              تظهر حين تمّت القراءة المحلية ولم يُحسم الإرسال الخارجي. ونصّها
              يأتي من الخادم فيسمّي المزوّد المضبوط فعلًا — لا اسمًا مكتوبًا
              في ترجمة قد تسبق تغييرَ المزوّد. */}
          {consent && consent.state !== "granted" ? (
            <div
              style={{
                marginBlockStart: 10, padding: 14, borderRadius: "var(--radius)",
                border: "1px solid var(--border)",
                background: "color-mix(in srgb, var(--athera-mint, #A7F3D0) 18%, transparent)",
                display: "grid", gap: 8,
              }}
            >
              <strong>{consent.title}</strong>
              <p style={{ margin: 0, whiteSpace: "pre-line", fontSize: 14 }}>{consent.body}</p>
              <p className="provenance-note" style={{ margin: 0 }}>
                {t("theses.consentLocalDone")}
              </p>
              {Object.keys(consent.excluded_chunks).length > 0 ? (
                <p className="metric-label" style={{ margin: 0 }}>
                  {t("theses.consentExcluded")}:{" "}
                  {Object.values(consent.excluded_chunks).reduce((a, b) => a + b, 0)}
                </p>
              ) : null}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void decideConsent("grant")}
                  style={{
                    padding: "8px 16px", border: "none", borderRadius: "var(--radius)",
                    background: "var(--athera-teal)", color: "#fff", font: "inherit",
                    cursor: "pointer",
                  }}
                >
                  {consent.accept_label}
                </button>
                <button
                  type="button"
                  disabled={busy || consent.state === "declined"}
                  onClick={() => void decideConsent("decline")}
                  style={{
                    padding: "8px 16px", border: "1px solid var(--border)",
                    borderRadius: "var(--radius)", background: "transparent",
                    color: "inherit", font: "inherit", cursor: "pointer",
                  }}
                >
                  {consent.decline_label}
                </button>
              </div>
            </div>
          ) : null}

          {consent && consent.state === "granted" ? (
            <div className="metric-label" style={{ marginBlockStart: 8 }}>
              {t("theses.consentGranted")} · {consent.provider}
              <button
                type="button"
                disabled={busy}
                onClick={() => void decideConsent("revoke")}
                style={{
                  marginInlineStart: 10, padding: "4px 10px",
                  border: "1px solid var(--border)", borderRadius: "var(--radius)",
                  background: "transparent", color: "inherit", font: "inherit",
                  cursor: "pointer", fontSize: 13,
                }}
              >
                {consent.revoke_label}
              </button>
              {/* السحب لا يستردّ ما أُرسل — ولا تدّعي الشاشة غير ذلك. */}
              <p className="provenance-note" style={{ margin: "4px 0 0" }}>
                {t("theses.consentNotRecall")}
              </p>
            </div>
          ) : null}

          <div style={{ display: "flex", gap: 8, marginBlockStart: 6, flexWrap: "wrap" }}>
            {state.status === "awaiting_review" || state.status === "verified" ? (
              <Link
                href={`/${locale}/theses/${state.thesis_id}/review`}
                style={{
                  padding: "8px 16px", borderRadius: "var(--radius)",
                  background: "var(--athera-teal)", color: "#fff", textDecoration: "none",
                }}
              >
                {t("theses.reviewCta")}
              </Link>
            ) : null}
            {TERMINAL.has(state.status) ? (
              <button
                type="button"
                onClick={() => void reprocess()}
                disabled={busy}
                style={{
                  padding: "8px 16px", border: "1px solid var(--border)",
                  borderRadius: "var(--radius)", background: "transparent",
                  color: "inherit", font: "inherit", cursor: "pointer",
                }}
              >
                {t("theses.reprocessCta")}
              </button>
            ) : null}
          </div>
          {TERMINAL.has(state.status) ? (
            <p className="provenance-note" style={{ margin: "4px 0 0" }}>
              {t("theses.reprocessNote")}
            </p>
          ) : null}
        </div>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}
