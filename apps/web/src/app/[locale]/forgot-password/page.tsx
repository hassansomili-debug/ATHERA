"use client";

import { use, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * نسيتُ كلمتي | Forgot password.
 *
 * **الجواب واحدٌ مهما كان البريد.** فرقٌ في النصّ بين بريدٍ مسجَّل وآخر
 * ليس كذلك يُحوّل هذه الشاشة إلى أداة تعداد حسابات: يجرّب المهاجم عناوين
 * ويقرأ من الجواب أيّها موجود. فالرسالة نفسها في الحالين، والخادم يقولها.
 */
interface GenericResponse {
  message_ar: string;
  message_en: string;
}

export default function ForgotPasswordPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const answer = await apiFetch<GenericResponse>("/api/v1/auth/forgot-password", {
        method: "POST",
        locale,
        body: JSON.stringify({ email }),
      });
      setSent(locale === "en" ? answer.message_en : answer.message_ar);
    } catch (err) {
      // حتى الخطأ لا يفشي وجود الحساب: الخادم لا يردّ إلا بحدّ المعدّل
      // أو بعطبٍ حقيقي، وكلاهما لا يقول شيئًا عن البريد.
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("auth.forgotFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <>
        <div className="page-head">
          <h1>{t("auth.forgotTitle")}</h1>
        </div>
        <p className="chip chip-ok" role="status" data-testid="forgot-sent">
          ✓ {sent}
        </p>
        <p style={{ marginBlockStart: 18 }}>
          <a href={`/${locale}/login`}>{t("auth.haveAccount")}</a>
        </p>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("auth.forgotTitle")}</h1>
        <p>{t("auth.forgotHint")}</p>
      </div>

      <form className="form" onSubmit={onSubmit} style={{ maxInlineSize: 420 }}>
        <label htmlFor="forgot-email">{t("auth.email")}</label>
        <input
          id="forgot-email"
          type="email"
          value={email}
          required
          autoComplete="email"
          onChange={(e) => setEmail(e.target.value)}
        />
        {error ? (
          <p className="error" role="alert" data-testid="forgot-error">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={busy || email.trim() === ""}>
          {busy ? t("app.loading") : t("auth.forgotSend")}
        </button>
      </form>

      <p style={{ marginBlockStart: 18 }}>
        <a href={`/${locale}/login`}>{t("auth.haveAccount")}</a>
      </p>
    </>
  );
}
