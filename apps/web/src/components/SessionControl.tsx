"use client";

import { useSyncExternalStore } from "react";

import type { Locale, Messages } from "@/lib/i18n";
import { translator } from "@/lib/i18n";
import { clearSession, isSignedIn } from "@/lib/session";

/**
 * دخول أو خروج | Sign in or out.
 *
 * الحالة تُقرأ بعد التركيب لا أثناءه: `localStorage` غير موجود على الخادم،
 * وقراءته في أول تصيير تُنتج اختلافًا بين ما صُيّر وما يُعرض.
 *
 * و`useSyncExternalStore` هي الأداة الموضوعة لهذا بالضبط: لقطة على العميل،
 * ولقطة أخرى على الخادم تمنع اختلاف الترطيب. كان الكود يضبط الحالة داخل
 * `useEffect` — تصيير متتالٍ يمنعه `react-hooks/set-state-in-effect`.
 * لا اشتراك هنا: الجلسة لا تتغيّر إلا بفعل يعيد تحميل الصفحة.
 */
const NO_SUBSCRIPTION = () => () => undefined;
export function SessionControl({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const signedIn = useSyncExternalStore(NO_SUBSCRIPTION, isSignedIn, () => false);

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
        window.location.assign(`/${locale}/login`);
      }}
    >
      {t("auth.signOut")}
    </button>
  );
}
