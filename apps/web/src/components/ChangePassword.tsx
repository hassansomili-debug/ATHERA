"use client";

import { useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { clearSession } from "@/lib/session";

/**
 * تغيير كلمة المرور | Change your password.
 *
 * **لم يكن في المنتج بابٌ لهذا إطلاقًا.** تسجيلٌ ودخولٌ وتجديدٌ وخروج —
 * ولا مسار. فمن انكشفت كلمته لا يملك إلا أن يطلب من غيره، أو يترك الحساب
 * مفتوحًا. وقد وقع ذلك فعلًا.
 *
 * **والنجاح يُنهي الجلسة قصدًا.** الخادم يُبطل كل رموز التجديد، فرمزُ
 * الوصول في هذه الشاشة يبقى صالحًا دقائق ثم لا يُجدَّد. وتركُ الباحث
 * يعمل بجلسةٍ نصف حيّة يُنتج فشلًا غامضًا بعد حين — والعودة إلى الدخول
 * بكلمته الجديدة أصدق وأوضح.
 */
export function ChangePassword({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // تُقال الشروط قبل الإرسال لا بعد رفضه.
  const tooShort = next.length > 0 && next.length < 12;
  const mismatch = confirm.length > 0 && confirm !== next;
  const ready = next.length >= 12 && confirm === next && current.length > 0;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch<void>("/api/v1/auth/change-password", {
        method: "POST",
        locale,
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setDone(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      // الجلسة تُمحى فورًا، ثم يُطلب الدخول بالكلمة الجديدة.
      clearSession();
      window.setTimeout(() => window.location.assign(`/${locale}/login`), 1500);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p className="chip chip-ok" role="status" data-testid="password-changed">
        ✓ {t("settings.passwordChanged")}
      </p>
    );
  }

  return (
    <form className="form" onSubmit={onSubmit} style={{ maxInlineSize: 420 }}>
      <label htmlFor="pw-current">{t("settings.currentPassword")}</label>
      <input
        id="pw-current"
        type="password"
        value={current}
        required
        autoComplete="current-password"
        onChange={(e) => setCurrent(e.target.value)}
      />

      <label htmlFor="pw-new">{t("settings.newPassword")}</label>
      <input
        id="pw-new"
        type="password"
        value={next}
        minLength={12}
        required
        autoComplete="new-password"
        aria-describedby="pw-new-hint"
        onChange={(e) => setNext(e.target.value)}
      />
      <p id="pw-new-hint" className="note" style={{ marginBlockStart: 0 }}>
        {tooShort ? t("auth.passwordTooShort") : t("auth.passwordRule")}
      </p>

      <label htmlFor="pw-confirm">{t("settings.confirmPassword")}</label>
      <input
        id="pw-confirm"
        type="password"
        value={confirm}
        required
        autoComplete="new-password"
        onChange={(e) => setConfirm(e.target.value)}
      />
      {mismatch ? (
        <p className="error" role="alert" data-testid="password-mismatch">
          {t("settings.passwordMismatch")}
        </p>
      ) : null}

      {error ? (
        <p className="error" role="alert" data-testid="password-error">
          {error}
        </p>
      ) : null}

      <p className="note">{t("settings.passwordRevokesSessions")}</p>
      <button type="submit" disabled={busy || !ready}>
        {busy ? t("app.loading") : t("settings.changePassword")}
      </button>
    </form>
  );
}
