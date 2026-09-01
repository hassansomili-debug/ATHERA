"use client";

import { use, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { isSignedIn, saveSession, type TokenPair } from "@/lib/session";

/**
 * تسجيل الدخول.
 *
 * **الخطوة الثانية تظهر حين يطلبها الخادم — لا قبله.** كان حقل رمز التحقق
 * معروضًا دائمًا، فيقرأ كل باحث أن المنصّة تطلب منه رمزًا لا يملكه، وحسابه
 * لا يحتاجه أصلًا: الخادم يشترط التحقق على الأدوار الإدارية وحدها، وبإعداد
 * قابل للإطفاء. فالحقل كان يصف سياسةً لا تنطبق على من يراه.
 *
 * والعقد في الخادم لم يتغيّر: `totp_code` اختياري منذ البداية. المتغيّر هنا
 * أن الواجهة صارت تسأل عنه **بعد** أن يقول الخادم إنه مطلوب — فيكون سؤالًا
 * عن شيء يعرف السائل أنه لازم.
 */
type Step = "credentials" | "verification";

/** مسارٌ داخلي فقط — يمنع التحويل المفتوح إلى نطاق خارجي. */
function safeDestination(locale: string): string {
  const fallback = `/${locale}`;
  if (typeof window === "undefined") return fallback;
  const wanted = new URLSearchParams(window.location.search).get("next");
  // مسار نسبي واحد لا يبدأ بـ`//` ولا يحمل مخططًا — وإلا فالافتراضي.
  if (!wanted || !wanted.startsWith("/") || wanted.startsWith("//")) return fallback;
  if (/^\/[a-z]+:/i.test(wanted)) return fallback;
  return wanted;
}

export default function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [step, setStep] = useState<Step>("credentials");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // جلسة قائمة: لا نعرض النموذج أصلًا.
  const [alreadyIn] = useState(() => isSignedIn());

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
          // يُرسل فارغًا ما لم يطلبه الخادم — والعقد يقبل `null`.
          totp_code: totp.trim() === "" ? null : totp.trim(),
        }),
      });
      // بلا هذا السطر يضيع الرمز فور التحويل، فتُرفض كل شاشة بعده.
      saveSession(tokens);
      // إعادة تحميل كاملة عمدًا لا `router.push`: الجلسة تُقرأ عند التركيب،
      // فالتنقّل داخل العميل يترك الشريط الجانبي يعرض «تسجيل الدخول».
      window.location.assign(safeDestination(locale));
    } catch (err) {
      const code = err instanceof AtheraApiError ? err.payload.code : "";
      if (code === "auth.mfa_required" || code === "auth.mfa_invalid_code") {
        // الخادم قال إن الحساب يشترط التحقق — الآن يُسأل عنه، لا قبل ذلك.
        setStep("verification");
        setError(code === "auth.mfa_invalid_code" ? t("auth.totpInvalid") : null);
      } else {
        // **رسالة واحدة عامة.** التمييز بين «بريد غير موجود» و«كلمة خاطئة»
        // يمنح مَن يجرّب الحسابات طريقةً لعدّها.
        setError(t("auth.genericError"));
      }
    } finally {
      setBusy(false);
    }
  }

  if (alreadyIn) {
    return (
      <section className="card" style={{ maxWidth: 460, margin: "48px auto", display: "grid", gap: 12 }}>
        <strong>{t("auth.alreadySignedIn")}</strong>
        <a className="primary-action" href={`/${locale}`}>{t("auth.continueToApp")}</a>
      </section>
    );
  }

  return (
    <section
      className="card"
      style={{ maxWidth: 460, margin: "48px auto", display: "grid", gap: 16 }}
    >
      <div style={{ display: "grid", gap: 6, justifyItems: "center", textAlign: "center" }}>
        <span className="brand-mark" aria-hidden="true" style={{ width: 40, height: 40 }} />
        <strong style={{ fontSize: 22 }}>{t("app.name")}</strong>
        <h1 style={{ fontSize: 18, margin: 0 }}>{t("auth.signIn")}</h1>
      </div>

      <form className="form" onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
        <label>
          {t("auth.email")}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            disabled={step === "verification"}
          />
        </label>

        <label>
          {t("auth.password")}
          <span style={{ display: "flex", gap: 6 }}>
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              disabled={step === "verification"}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="action"
              aria-pressed={showPassword}
              aria-label={showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
              onClick={() => setShowPassword(!showPassword)}
              style={{ padding: "0 12px" }}
            >
              {showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
            </button>
          </span>
        </label>

        {/* الخطوة الثانية — لا تظهر إلا بعد أن يقول الخادم إنها لازمة. */}
        {step === "verification" ? (
          <label>
            {t("auth.totp")}
            <input
              inputMode="numeric"
              pattern="[0-9]{6}"
              value={totp}
              onChange={(e) => setTotp(e.target.value)}
              autoComplete="one-time-code"
              required
              autoFocus
            />
            <span className="provenance-note">{t("auth.totpHint")}</span>
          </label>
        ) : null}

        {error ? <p className="error" role="alert">{error}</p> : null}

        <button type="submit" className="primary-action" disabled={busy}>
          {busy ? t("app.loading") : t("auth.submit")}
        </button>
      </form>

      <p className="metric-label" style={{ margin: 0, textAlign: "center" }}>
        {/* لا مسار استعادة في المنصّة بعد — فلا يُعرض زرٌّ يوهم بوجوده. */}
        {t("auth.forgotPassword")}: {t("auth.forgotPasswordUnavailable")}
      </p>
    </section>
  );
}
