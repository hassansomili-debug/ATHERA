"use client";

import { use, useEffect, useState, useSyncExternalStore } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { clearSession } from "@/lib/session";

/**
 * إعادة تعيين كلمة المرور | Reset password.
 *
 * **الرمز يُقرأ من جزء الرابط (fragment) ولا يُعرض.** وما بعد `#` لا
 * يُرسَل في طلب HTTP إطلاقًا: لا يبلغ خادم الواجهة، ولا يظهر في سجلات
 * وصوله، ولا في ترويسة `Referer` عند الانتقال إلى صفحةٍ أخرى.
 *
 * **ولا دخولَ تلقائيّ بعد النجاح.** من يملك الرابط ليس بالضرورة من يملك
 * الحساب، ودخولٌ تلقائيّ يجعل سرقة الرابط سرقةَ جلسةٍ فورية. فيُطلب
 * الدخول بالكلمة الجديدة — وهي وحدها ما يثبت الملكية.
 */
const NO_SUBSCRIPTION = () => () => undefined;
const readFragment = () =>
  typeof window === "undefined" ? "" : window.location.hash;

export default function ResetPasswordPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  // يُقرأ بعد التركيب: `location` لا وجود له على الخادم.
  const fragment = useSyncExternalStore(NO_SUBSCRIPTION, readFragment, () => "");
  const token = new URLSearchParams(fragment.replace(/^#/, "")).get("token") ?? "";

  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // **الرمز يُنزع من شريط العنوان ومن سجل التنقّل حالما يُقرأ.**
  // فلا يبقى في تاريخ المتصفح ولا فيما يُشارَك من لقطة شاشة.
  useEffect(() => {
    if (!fragment) return;
    window.history.replaceState(null, "", window.location.pathname);
  }, [fragment]);

  const tooShort = next.length > 0 && next.length < 12;
  const mismatch = confirm.length > 0 && confirm !== next;
  const ready = token !== "" && next.length >= 12 && confirm === next;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch<void>("/api/v1/auth/reset-password", {
        method: "POST",
        locale,
        body: JSON.stringify({ token, new_password: next }),
      });
      setNext("");
      setConfirm("");
      setDone(true);
      clearSession();
      window.setTimeout(() => window.location.assign(`/${locale}/login`), 1800);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p className="chip chip-ok" role="status" data-testid="reset-done">
        ✓ {t("auth.resetDone")}
      </p>
    );
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("auth.resetTitle")}</h1>
        <p>{t("auth.resetHint")}</p>
      </div>

      {token === "" ? (
        // رابطٌ بلا رمز: يُقال ذلك صراحةً بدل نموذجٍ يفشل بعد الإرسال.
        <p className="error" role="alert" data-testid="reset-no-token">
          {t("auth.resetNoToken")}{" "}
          <a href={`/${locale}/forgot-password`}>{t("auth.forgotTitle")}</a>
        </p>
      ) : (
        <form className="form" onSubmit={onSubmit} style={{ maxInlineSize: 420 }}>
          <label htmlFor="reset-new">{t("settings.newPassword")}</label>
          <input
            id="reset-new"
            type="password"
            value={next}
            minLength={12}
            required
            autoComplete="new-password"
            aria-describedby="reset-hint"
            onChange={(e) => setNext(e.target.value)}
          />
          <p id="reset-hint" className="note" style={{ marginBlockStart: 0 }}>
            {tooShort ? t("auth.passwordTooShort") : t("auth.passwordRule")}
          </p>

          <label htmlFor="reset-confirm">{t("settings.confirmPassword")}</label>
          <input
            id="reset-confirm"
            type="password"
            value={confirm}
            required
            autoComplete="new-password"
            onChange={(e) => setConfirm(e.target.value)}
          />
          {mismatch ? (
            <p className="error" role="alert" data-testid="reset-mismatch">
              {t("settings.passwordMismatch")}
            </p>
          ) : null}

          {error ? (
            <p className="error" role="alert" data-testid="reset-error">
              {error}
            </p>
          ) : null}

          <button type="submit" disabled={busy || !ready}>
            {busy ? t("app.loading") : t("auth.resetSubmit")}
          </button>
        </form>
      )}
    </>
  );
}
