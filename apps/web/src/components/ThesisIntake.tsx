"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";
import { getAccessToken } from "@/lib/session";

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
  | "extraction_failed";

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
  "awaiting_review", "verified", "parse_failed", "extraction_failed",
]);

const STATE_KEY: Record<string, string> = {
  stored: "theses.stateStored",
  parsing: "theses.stateParsing",
  parsed: "theses.stateParsed",
  extracting: "theses.stateExtracting",
  awaiting_review: "theses.stateAwaitingReview",
  verified: "theses.stateVerified",
  parse_failed: "theses.stateParseFailed",
  extraction_failed: "theses.stateExtractionFailed",
};

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

  const poll = useCallback(
    async (thesisId: string) => {
      try {
        const next = await apiFetch<ExtractionState>(
          `/api/v1/theses/${thesisId}/extraction`, { locale },
        );
        setState(next);
        setPhase(next.status);
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
      const token = getAccessToken();
      const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      const response = await fetch(`${base}/api/v1/theses/upload`, {
        method: "POST",
        headers: {
          "Accept-Language": locale,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new AtheraApiError(response.status, payload?.error ?? {
          code: "file.upload_failed", locale, message: t("upload.failed"),
          messages: { ar: t("upload.failed"), en: t("upload.failed") },
        });
      }
      const started = (await response.json()) as ExtractionState;
      setState(started);
      setPhase(started.status);
    } catch (err) {
      setPhase("idle");
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("upload.failed"));
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

  const failed = phase === "parse_failed" || phase === "extraction_failed";

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
