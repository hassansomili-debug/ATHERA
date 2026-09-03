"use client";

import { useCallback, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";

/**
 * حدّ الإذن على مستندٍ بعينه (DIC2).
 *
 * **الحدّ كان بلا باب.** القراءة المحلية تتوقف عند `awaiting_consent`
 * وتنتظر إذن الباحث — والمكتبة تقول له ذلك صراحةً منذ أن صار انتظارُه
 * يُسمّى باسمه. لكنّ الزرّ الذي يمنح الإذن كان يعيش داخل مكوّن الرفع وحده،
 * ولا يظهر إلا لمن رفع مستنده من تلك الشاشة نفسها في تلك الجلسة نفسها.
 * فمن رفع من «مكتبتي» ثم تتبّع الرابط وصل إلى قائمة الرسائل ولم يجد فيها
 * ما يمنح به الإذن: طلبٌ يُعلَن ولا يُستجاب — وهو أسوأ من ألا يُعلَن.
 *
 * فصار الحدّ مكوّنًا واحدًا يُركَّب حيث يقف الباحث: في شاشة الرفع، وفي
 * مراجعة الرسالة التي يقصدها من مكتبته. **وتعريفٌ واحد** لا نسختان
 * تفترقان — فالسمة `dic2-grant` تصف الحدّ العلمي نفسه أينما ظهر.
 *
 * ونصّه يأتي من الخادم لا من ترجمة: هو من يعرف المزوّد المضبوط فعلًا،
 * وأيّ تصنيفٍ يُرسل، وأيّ مقاطع استُثنيت.
 */
export interface Dic2ConsentState {
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

export function Dic2Consent({
  locale, messages, thesisId, onDecision,
}: {
  locale: Locale;
  messages: Messages;
  thesisId: string;
  /** يُستدعى بعد قرارٍ ناجح — لتُحدَّث الحال المعروضة حول هذا المكوّن. */
  onDecision?: (decision: "grant" | "decline" | "revoke") => void;
}) {
  const t = translator(messages);
  const [consent, setConsent] = useState<Dic2ConsentState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setConsent(await apiFetch<Dic2ConsentState>(
        `/api/v1/theses/${thesisId}/consent`, { locale },
      ));
    } catch (err) {
      // الحدّ إن تعذّرت قراءته يُقال — ولا يُفترض ممنوحًا.
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [locale, thesisId, t]);

  useEffect(() => { void load(); }, [load]);

  async function decideConsent(decision: "grant" | "decline" | "revoke") {
    setBusy(true);
    setError(null);
    try {
      setConsent(await apiFetch<Dic2ConsentState>(`/api/v1/theses/${thesisId}/consent`, {
        method: "POST", locale, body: JSON.stringify({ decision }),
      }));
      onDecision?.(decision);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (!consent) {
    return error ? <p className="error" role="alert">{error}</p> : null;
  }

  if (consent.state === "granted") {
    return (
      <div className="metric-label" data-testid="dic2-granted" style={{ marginBlockStart: 8 }}>
        {t("theses.consentGranted")} · {consent.provider}
        <button
          type="button"
          data-testid="dic2-revoke"
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
        {error ? <p className="error" role="alert">{error}</p> : null}
      </div>
    );
  }

  return (
    <div
      data-testid="dic2-gate"
      style={{
        marginBlockStart: 10, padding: 14, borderRadius: "var(--radius)",
        border: "1px solid var(--border)",
        background: "color-mix(in srgb, var(--athera-mint, #A7F3D0) 18%, transparent)",
        display: "grid", gap: 8,
      }}
    >
      <strong>{consent.title}</strong>
      <p style={{ margin: 0, whiteSpace: "pre-line", fontSize: 14 }}>{consent.body}</p>
      <p className="provenance-note" style={{ margin: 0 }}>{t("theses.consentLocalDone")}</p>
      {Object.keys(consent.excluded_chunks).length > 0 ? (
        <p className="metric-label" style={{ margin: 0 }}>
          {t("theses.consentExcluded")}:{" "}
          {Object.values(consent.excluded_chunks).reduce((a, b) => a + b, 0)}
        </p>
      ) : null}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          // مِقبضٌ ثابت: نصّ الزرّ يأتي من الخادم فيتغيّر، والحدّ العلمي
          // الذي يمثّله لا يتغيّر — فيُستهدف بما يصفه.
          data-testid="dic2-grant"
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
          data-testid="dic2-decline"
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
      {error ? <p className="error" role="alert">{error}</p> : null}
    </div>
  );
}
