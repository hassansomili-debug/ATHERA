"use client";

import { useEffect, useState } from "react";

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
 * **ولا يُصيَّر ما لا يعمل.** فالحدّ هنا: إمّا جلسةٌ قائمة فتُعرض الشاشة،
 * وإمّا لا فيُذهب إلى الدخول قصدًا — لا بعد فشلِ نداء.
 *
 * والفحص بعد التركيب لا أثناءه: `localStorage` لا وجود له على الخادم،
 * وقراءته في أول تصيير تُنتج اختلاف ترطيب.
 */

/** ما لا يحتاج جلسة — وهو ما يُنشئها أو يسترجعها. */
const PUBLIC_SEGMENTS = ["/login", "/register"];

export function AuthGate({
  locale,
  children,
}: {
  locale: Locale;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<"checking" | "allowed">("checking");

  useEffect(() => {
    const path = window.location.pathname;
    const isPublic = PUBLIC_SEGMENTS.some((segment) => path.endsWith(segment));
    if (isPublic || isSignedIn()) {
      setState("allowed");
      return;
    }
    // الوجهة تُحفظ ليعود الباحث إلى ما قصده، لا إلى الرئيسية.
    const next = encodeURIComponent(path + window.location.search);
    window.location.assign(`/${locale}/login?next=${next}`);
  }, [locale]);

  if (state === "checking") {
    // لا هيكلٌ وهمي ولا مساحةُ عملٍ مؤقّتة: فراغٌ صريح لجزءٍ من ثانية أصدق
    // من واجهةٍ تُعرض ثم تُسحب.
    return <div aria-busy="true" style={{ minBlockSize: "50vh" }} />;
  }
  return <>{children}</>;
}
