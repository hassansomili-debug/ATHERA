"use client";

import { useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { saveSession, type TokenPair } from "@/lib/session";
import { use } from "react";

export default function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const tokens = await apiFetch<TokenPair>("/api/v1/auth/login", {
        method: "POST",
        locale,
        body: JSON.stringify({
          email,
          password,
          totp_code: totp.trim() === "" ? null : totp.trim(),
        }),
      });
      // بلا هذا السطر يضيع الرمز فور التحويل، فتُرفض كل شاشة بعده.
      saveSession(tokens);
      // إعادة تحميل كاملة عمدًا لا `router.push`: الجلسة تُقرأ عند التركيب،
      // فالتنقّل داخل العميل يترك الشريط الجانبي يعرض «تسجيل الدخول».
      // و`assign` استدعاء لا إسناد على `window` — الإسناد يرفضه
      // `react-hooks/immutability`.
      // العودة إلى ما قصده الباحث قبل أن يُطلب منه الدخول — لا إلى
      // الرئيسية دائمًا. والوجهة تُقبل فقط إن كانت مسارًا داخليًّا.
      const next = new URLSearchParams(window.location.search).get("next");
      const safe = next && next.startsWith("/") && !next.startsWith("//") ? next : `/${locale}`;
      window.location.assign(safe);
    } catch (err) {
      // الخطأ يصل بلغتين؛ نعرض لغة الواجهة الحالية.
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("auth.signInFailed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>{t("auth.signIn")}</h1>
      <form className="form" onSubmit={onSubmit}>
        <label>
          {t("auth.email")}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </label>
        <label>
          {t("auth.password")}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        <label>
          {t("auth.totp")}
          <input
            inputMode="numeric"
            pattern="[0-9]{6}"
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
            autoComplete="one-time-code"
          />
        </label>
        {error ? <p className="error" role="alert" data-testid="login-error">{error}</p> : null}
        <button type="submit" disabled={busy}>
          {busy ? t("app.loading") : t("auth.submit")}
        </button>
      </form>

      {/* بابٌ إلى إنشاء حساب — بدونه صفحة الدخول طريق مسدود لمن لا حساب له. */}
      <p style={{ marginBlockStart: 18 }}>
        <a href={`/${locale}/register`}>{t("auth.needAccount")}</a>
      </p>
      <p>
        <a href={`/${locale}/forgot-password`}>{t("auth.forgotTitle")}</a>
      </p>
    </>
  );
}
