"use client";

import { useEffect, useState } from "react";

import type { Locale, Messages } from "@/lib/i18n";
import { translator } from "@/lib/i18n";
import { clearSession, isSignedIn } from "@/lib/session";

/**
 * دخول أو خروج | Sign in or out.
 *
 * الحالة تُقرأ بعد التركيب لا أثناءه: `localStorage` غير موجود على الخادم،
 * وقراءته في أول تصيير تُنتج اختلافًا بين ما صُيّر وما يُعرض.
 */
export function SessionControl({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(isSignedIn());
  }, []);

  if (!signedIn) {
    return (
      <a className="session-link" href={`/${locale}/login`}>
        {t("auth.signIn")}
      </a>
    );
  }

  return (
    <button
      type="button"
      className="session-link"
      onClick={() => {
        clearSession();
        window.location.href = `/${locale}/login`;
      }}
    >
      {t("auth.signOut")}
    </button>
  );
}
