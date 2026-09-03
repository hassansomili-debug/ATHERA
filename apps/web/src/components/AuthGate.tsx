"use client";

import { useEffect, useSyncExternalStore } from "react";

import { isSignedIn } from "@/lib/session";
import type { Locale } from "@/lib/i18n";

/**
 * حدّ المصادقة | The authentication boundary.
 *
 * **سياسة المنتج: بُبريفا تطبيقٌ محمي، لا صفحةُ هبوطٍ عامة.**
 *
 * وكانت الحال مختلطة، وهي أسوأ الحالين: الرئيسية تُصيَّر كاملةً — عنوانٌ
 * وحقل سؤالٍ وخمس بطاقات — ثم يستدعي `usePosture` مسارًا محميًّا، فيردّ
 * الخادم 401، فيمحو العميل الجلسة ويقذف الزائر إلى صفحة الدخول. فيرى
 * الزائر مساحةَ عملٍ تبدو صالحة ثم تختفي تحته بلا سبب يفهمه.
 *
 * **ولا يُصيَّر ما لا يعمل.**
 *
 * والحال تُقرأ بـ`useSyncExternalStore` لا بـ`setState` داخل تأثير:
 * `localStorage` و`location` لا وجود لهما على الخادم، وضبطُ الحالة داخل
 * التأثير يُنتج تصييرًا متتاليًا يمنعه `react-hooks/set-state-in-effect`.
 * ولقطةُ الخادم تمنع اختلاف الترطيب. ولا اشتراك: الجلسة لا تتغيّر إلا بفعلٍ
 * يعيد تحميل الصفحة.
 */
const NO_SUBSCRIPTION = () => () => undefined;

/** ما لا يحتاج جلسة — وهو ما يُنشئها أو يسترجعها. */
const PUBLIC_SEGMENTS = ["/login", "/register"];

const readPath = () => (typeof window === "undefined" ? "" : window.location.pathname);
const readServerPath = () => "";
const readServerSignedIn = () => false;

export function AuthGate({
  locale,
  children,
}: {
  locale: Locale;
  children: React.ReactNode;
}) {
  const signedIn = useSyncExternalStore(NO_SUBSCRIPTION, isSignedIn, readServerSignedIn);
  const path = useSyncExternalStore(NO_SUBSCRIPTION, readPath, readServerPath);

  const isPublic = PUBLIC_SEGMENTS.some((segment) => path.endsWith(segment));
  const allowed = Boolean(path) && (isPublic || signedIn);

  useEffect(() => {
    if (!path || allowed) return;
    // الوجهة تُحفظ ليعود الباحث إلى ما قصده، لا إلى الرئيسية.
    const next = encodeURIComponent(path + window.location.search);
    window.location.assign(`/${locale}/login?next=${next}`);
  }, [allowed, path, locale]);

  if (!allowed) {
    // لا هيكلٌ وهمي ولا مساحةُ عملٍ مؤقّتة: فراغٌ صريح لجزءٍ من ثانية أصدق
    // من واجهةٍ تُعرض ثم تُسحب.
    return <div aria-busy="true" style={{ minBlockSize: "50vh" }} />;
  }
  return <>{children}</>;
}
