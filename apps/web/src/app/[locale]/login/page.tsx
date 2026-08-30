"use client";

import { useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { use } from "react";

interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

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
      await apiFetch<TokenPair>("/api/v1/auth/login", {
        method: "POST",
        locale,
        body: JSON.stringify({
          email,
          password,
          totp_code: totp.trim() === "" ? null : totp.trim(),
        }),
      });
      window.location.href = `/${locale}`;
    } catch (err) {
      // الخطأ يصل بلغتين؛ نعرض لغة الواجهة الحالية.
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("auth.genericError"),
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
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={busy}>
          {busy ? t("app.loading") : t("auth.submit")}
        </button>
      </form>
    </>
  );
}
