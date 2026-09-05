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
  /**
   * **خطوةٌ يفتحها الخادم، لا حقلٌ دائم.**
   *
   * كان حقل «رمز التحقّق بخطوتين» معروضًا لكل من فتح الصفحة — ولا يملكه
   * إلّا من فعّل التحقّق. فيقرأ الأكثرون حقلًا لا يخصّهم، ويُشكّون: هل
   * نسيتُ شيئًا؟ هل حسابي ناقص؟ وحقلٌ لا يعني القارئَ يُعلّم العين أن
   * تتخطّى الحقول، فتتخطّى الذي يعنيه.
   *
   * فالخادم هو من يقول متى يلزم الرمز: `auth.mfa_invalid_code` تعني أنّ
   * لهذا الحساب عاملًا ثانيًا مؤكَّدًا وأنّ ما وصل لا يكفي. عندها — وعندها
   * وحدها — تُفتح الخطوة. **ولا يتغيّر ما يُرسَل**: الجسم هو الجسم نفسه،
   * والرمزُ `null` ما لم يُكتب. هذا عرضٌ لا سلوك.
   */
  const [mfaNeeded, setMfaNeeded] = useState(false);
  const [revealed, setRevealed] = useState(false);

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
      // **الرمز هو ما يُقرأ، لا نصّ الرسالة.** النصّ يصل بلغتين ويتبدّل
      // بتحرير؛ والرمز عقدٌ بين الطرفين.
      if (err instanceof AtheraApiError && err.payload.code === "auth.mfa_invalid_code") {
        setMfaNeeded(true);
      }
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
      <h1>{t("auth.welcomeTitle")}</h1>
      <p className="auth-sub">{t("auth.welcomeSubtitle")}</p>
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
        <label htmlFor="login-password">{t("auth.password")}</label>
        {/*
          **الكشفُ زرٌّ اسمُه يتبدّل، لا أيقونةٌ صامتة.** ومن لا يرى الحقل
          لا يعرف من رسمِ عينٍ أمفتوحةٌ كلمتُه أم مستورة، فيُنطق الاسم:
          «أظهِر» حين تكون مستورة، و«أخفِ» حين تكون ظاهرة.
        */}
        <div className="field-reveal">
          <input
            id="login-password"
            type={revealed ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
          {/*
            **الاسمُ المنطوق كاملٌ، والمرئيُّ قصير.**

            كان المرئيُّ هو الكامل («أظهِر كلمة المرور»)، فبلغ عرضُ الزرّ
            مئةً وأربعين بكسلًا ولم يقبل الانكماش — ودفع الصفَّ خارج شاشةٍ
            عرضُها ٣٩٠، فصار المستند يُمرَّر أفقيًّا. وقصُّ النصّ بالنقاط
            كان يخفي المعنى؛ وتصغيرُ الخطّ يخفيه على من يحتاجه.
            فالوسمُ يحمل الاسم كاملًا لقارئ الشاشة، والعين تقرأ كلمةً
            واحدة بجانب حقلٍ لا لبس فيه.
          */}
          <button
            type="button"
            className="reveal"
            aria-label={revealed ? t("auth.hidePassword") : t("auth.showPassword")}
            onClick={() => setRevealed((on) => !on)}
          >
            {revealed ? t("auth.hidePasswordShort") : t("auth.showPasswordShort")}
          </button>
        </div>
        {mfaNeeded ? (
          <div className="mfa-step" data-testid="login-mfa-step">
            <strong>{t("auth.mfaTitle")}</strong>
            <p>{t("auth.mfaHint")}</p>
            <label>
              {t("auth.totp")}
              <input
                inputMode="numeric"
                pattern="[0-9]{6}"
                value={totp}
                onChange={(e) => setTotp(e.target.value)}
                autoComplete="one-time-code"
                required
              />
            </label>
          </div>
        ) : null}
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
