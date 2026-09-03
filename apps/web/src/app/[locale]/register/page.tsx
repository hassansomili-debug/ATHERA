"use client";

import { use, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { saveSession, type TokenPair } from "@/lib/session";

/**
 * أنشئ حسابًا | Create an account.
 *
 * **مسارٌ عامل في الخادم بلا باب في المتصفح ليس مسارًا.** `POST /auth/register`
 * قائمٌ منذ البداية، ولم تكن في الواجهة صفحةٌ تبلغه — فكان الدخول طريقًا
 * مسدودًا: من لا حساب له لا يستطيع أن يصنع واحدًا.
 *
 * **والتسجيل الذاتي يُنشئ مساحةً جديدة ولا ينضمّ إلى قائمة.** والخادم يرفض
 * اسمًا مأخوذًا (`auth.workspace_name_taken`) ولا يجعله انضمامًا — وتلك
 * ثغرة تفويضٍ أُغلقت هناك. فلا تعرض هذه الشاشة حقل «انضمّ إلى مساحة»،
 * ولا تسأل عن اسم مساحةٍ قائمة: الانضمام يحتاج دعوةً من إدارتها.
 */
export default function RegisterPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // اثنا عشر حرفًا شرطُ الخادم — يُقال قبل الإرسال لا بعد رفضه.
  const tooShort = password.length > 0 && password.length < 12;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const tokens = await apiFetch<TokenPair>("/api/v1/auth/register", {
        method: "POST",
        locale,
        body: JSON.stringify({
          email,
          password,
          full_name_ar: fullName,
          preferred_locale: locale,
        }),
      });
      saveSession(tokens);
      // تحميلٌ كامل عمدًا: الجلسة تُقرأ عند التركيب، فالتنقّل داخل العميل
      // يترك الشريط الجانبي يعرض «تسجيل الدخول».
      window.location.assign(`/${locale}`);
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("auth.genericError"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("auth.createAccount")}</h1>
        <p>{t("auth.createAccountHint")}</p>
      </div>

      <form className="form" onSubmit={onSubmit} style={{ maxInlineSize: 420 }}>
        <label htmlFor="reg-name">{t("auth.fullName")}</label>
        <input
          id="reg-name"
          name="full_name"
          value={fullName}
          minLength={2}
          required
          autoComplete="name"
          onChange={(e) => setFullName(e.target.value)}
        />

        <label htmlFor="reg-email">{t("auth.email")}</label>
        <input
          id="reg-email"
          name="email"
          type="email"
          value={email}
          required
          autoComplete="email"
          onChange={(e) => setEmail(e.target.value)}
        />

        <label htmlFor="reg-password">{t("auth.password")}</label>
        <input
          id="reg-password"
          name="password"
          type="password"
          value={password}
          minLength={12}
          required
          autoComplete="new-password"
          aria-describedby="reg-password-hint"
          onChange={(e) => setPassword(e.target.value)}
        />
        <p id="reg-password-hint" className="note" style={{ marginBlockStart: 0 }}>
          {tooShort ? t("auth.passwordTooShort") : t("auth.passwordRule")}
        </p>

        {error ? (
          <p className="error" role="alert" data-testid="register-error">
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={busy || password.length < 12}>
          {busy ? t("auth.creating") : t("auth.createAccount")}
        </button>
      </form>

      <p style={{ marginBlockStart: 18 }}>
        <a href={`/${locale}/login`}>{t("auth.haveAccount")}</a>
      </p>
    </>
  );
}
