/**
 * عميل الـAPI | API client.
 *
 * §38.6.8 — هذا هو المنفذ الوحيد للخارج من المتصفح: خادمنا فقط. لا مزود
 * نموذج، ولا مفتاح، ولا استدعاء مباشر. CSP تمنع غير ذلك، وAT-S0-09 يفشل
 * البناء لو حاول أحد.
 */
import type { Locale } from "./i18n";
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  saveSession,
  type TokenPair,
} from "./session";

const CONFIGURED_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
const BASE_URL = CONFIGURED_BASE_URL ?? "http://localhost:8000";

/**
 * هل نُشر التطبيق بلا ضبط عنوان الـAPI؟
 *
 * `NEXT_PUBLIC_*` يُثبَّت في الحزمة وقت البناء، فبناء بلا ضبطه يُنتج موقعًا
 * يوجّه طلباته إلى `localhost` — وCSP تحجبها بلا رسالة مفهومة. المستخدم يرى
 * صفحات تُعرض وبيانات لا تصل، ولا شيء يقول لماذا.
 *
 * الفحص هنا وقت التشغيل لا وقت البناء: صفحة تُعرض على نطاق حقيقي بينما
 * عنوانها المضبوط `localhost` هي بالتحديد الحالة المعطوبة.
 */
export function isApiMisconfigured(): boolean {
  if (typeof window === "undefined") return false;
  const servedLocally = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  if (servedLocally) return false;
  return !CONFIGURED_BASE_URL || BASE_URL.includes("localhost");
}

const MISCONFIGURED_ERROR: ApiError = {
  code: "config.api_base_url_missing",
  locale: "ar",
  message: "لم يُضبط عنوان الـAPI في هذا النشر.",
  messages: {
    ar:
      "لم يُضبط عنوان الـAPI في هذا النشر (NEXT_PUBLIC_API_BASE_URL). " +
      "الواجهة تعمل، ولا تصل إلى الخادم حتى يُضبط المتغيّر ويُعاد النشر.",
    en:
      "The API base URL was not set for this deployment (NEXT_PUBLIC_API_BASE_URL). " +
      "The interface runs but cannot reach the server until the variable is set and " +
      "the site redeployed.",
  },
};

export interface ApiError {
  code: string;
  locale: string;
  message: string;
  messages: Record<string, string>;
}

export class AtheraApiError extends Error {
  constructor(readonly status: number, readonly payload: ApiError) {
    super(payload.message);
  }

  /** الرسالة باللغة المطلوبة — الاستجابة تحمل اللغتين دائمًا. */
  localized(locale: Locale): string {
    return this.payload.messages[locale] ?? this.payload.message;
  }
}

/**
 * الرمز يُقرأ من الجلسة تلقائيًّا ما لم يُمرَّر صراحةً.
 *
 * الافتراض المعاكس — أن تتذكّر كل شاشة تمريره — فشل فعلًا: إحدى وعشرون
 * شاشة من اثنتين وعشرين كانت تستدعي الـAPI بلا ترويسة مصادقة، فيردّ
 * الخادم «بيانات الدخول غير صحيحة» وهو محقّ.
 */
/**
 * مسارات لا تُجدَّد أبدًا ولا تُسقط جلسة.
 *
 * ثلاثةٌ منها تُصدر الرموز، فتجديدُها دورٌ حول نفسه. **والاثنان الأخيران
 * مسارا استعادة**: يُستدعيان بلا جلسة أصلًا — فمن نسي كلمته ليس داخلًا.
 * ولو عُوملا كغيرهما لمحا الجلسة عند أي ردٍّ يشبه الرفض وقذفا الباحث إلى
 * صفحة الدخول **وهو في منتصف استعادته**، بلا سببٍ يفهمه.
 *
 * و`change-password` ليس منها عمدًا: هو مسارٌ مُصادَق، وانتهاءُ رمز وصوله
 * أثناء ملء النموذج حالٌ يصحّ فيها التجديد المعتاد.
 */
const AUTH_PATHS = [
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
  "/api/v1/auth/forgot-password",
  "/api/v1/auth/reset-password",
];

const isAuthPath = (path: string) => AUTH_PATHS.some((p) => path.startsWith(p));

/**
 * تجديدٌ واحد في الطيران | single-flight refresh.
 *
 * **رمز التحديث يدور**: كل استعمالٍ ناجح يُبطله ويُصدر غيره. فلو انتهت
 * صلاحية رمز الوصول وفي الصفحة خمسة طلبات متوازية، لأرسل كلٌّ منها طلب
 * تجديدٍ بالرمز نفسه — يفوز الأول ويُبطله، وتفشل الأربعة الباقية بـرمزٍ
 * مُبطَل، فتُمحى الجلسة ويُطرد الباحث وهو يعمل.
 *
 * فالوعد الواحد يُنشأ مرّة، وينتظره الجميع، ويُمسح بعد استقراره.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  const token = getRefreshToken();
  if (!token) return false;
  try {
    const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token }),
    });
    if (!response.ok) return false;
    const pair = (await response.json()) as TokenPair;
    if (!pair?.access_token || !pair?.refresh_token) return false;
    // **الرمزان معًا.** حفظ رمز الوصول وحده يترك رمز تحديثٍ مُبطَلًا في
    // المخزن، فينجح التجديد مرّة ثم يفشل أبدًا.
    saveSession(pair);
    return true;
  } catch {
    // الشبكة أو صيغة غير متوقّعة — يُعامَل كفشل تجديد، بلا تفاصيل تُسرَّب.
    return false;
  }
}

function refreshOnce(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/** لا يُعاد التوجيه من صفحة الدخول إلى نفسها — تلك حلقة لا نهاية لها. */
function redirectToLogin(locale: Locale): void {
  if (typeof window === "undefined") return;
  const target = `/${locale}/login`;
  if (window.location.pathname.endsWith("/login")) return;
  window.location.assign(target);
}

/**
 * الرمز يُقرأ من الجلسة تلقائيًّا ما لم يُمرَّر صراحةً.
 *
 * الافتراض المعاكس — أن تتذكّر كل شاشة تمريره — فشل فعلًا: إحدى وعشرون
 * شاشة من اثنتين وعشرين كانت تستدعي الـAPI بلا ترويسة مصادقة، فيردّ
 * الخادم «بيانات الدخول غير صحيحة» وهو محقّ.
 *
 * **وانتهاء رمز الوصول ليس نهاية الجلسة.** كان كل 401 يمحو الجلسة ويقذف
 * الباحث إلى صفحة الدخول — ورمز الوصول يعيش تسعمئة ثانية. فباحثٌ يكتب
 * ورقته يُطرد كل ربع ساعة، ورمز التحديث في المخزن لم يُستعمل قط. فيُجرَّب
 * التجديد **مرّة واحدة**، ويُعاد الطلب الأصلي **مرّة واحدة**، فإن فشل
 * التجديد فحينئذٍ — وحينئذٍ فقط — تُمحى الجلسة.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit & { locale: Locale; token?: string },
): Promise<T> {
  return requestWithRefresh<T>(path, options, false);
}

async function requestWithRefresh<T>(
  path: string,
  options: RequestInit & { locale: Locale; token?: string },
  alreadyRetried: boolean,
): Promise<T> {
  const { locale, token, ...init } = options;

  // يُعلَن الخلل قبل الطلب: محاولة الاتصال بـlocalhost من نطاق منشور تُحجب
  // في المتصفح برسالة CSP غامضة، فيبدو العطب في الخادم لا في الإعداد.
  if (isApiMisconfigured()) {
    throw new AtheraApiError(0, { ...MISCONFIGURED_ERROR, locale });
  }

  const bearer = token ?? getAccessToken();
  // **رفع الملفات يفرض نوعه بنفسه.** `FormData` يحتاج حدًّا فاصلًا
  // (boundary) يولّده المتصفح ويضعه في الترويسة؛ وفرضُ `application/json`
  // فوقه يُنتج طلبًا لا يستطيع الخادم تفكيكه.
  const isMultipart = typeof FormData !== "undefined" && init.body instanceof FormData;
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isMultipart ? {} : { "Content-Type": "application/json" }),
      "Accept-Language": locale,
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
      ...init.headers,
    },
  });

  if (response.status === 401 && !isAuthPath(path)) {
    // رمزٌ مُمرَّر يدويًّا ليس جلسة المتصفح، فلا يُجدَّد نيابةً عن صاحبه.
    const ownsSession = token === undefined;
    if (ownsSession) {
      if (!alreadyRetried && getRefreshToken() && (await refreshOnce())) {
        return requestWithRefresh<T>(path, options, true);
      }
      // **ولا تُمحى جلسة المتصفح لأجل رمزٍ ليس لها.** رفضُ رمزٍ مرّره
      // المستدعي صراحةً خبرٌ عن ذلك الرمز، لا حكمٌ على من يجلس أمام الشاشة.
      clearSession();
      redirectToLogin(locale);
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new AtheraApiError(response.status, body?.error ?? {
      code: "server.error",
      locale,
      message: "Request failed",
      messages: { ar: "فشل الطلب.", en: "Request failed." },
    });
  }
  // **٢٠٤ ليست جسمًا فارغًا، بل لا جسم لها.** و`response.json()` يرمي عليها.
  // والخروج يردّ ٢٠٤ — فبلا هذا السطر يفشل كل خروجٍ ناجح ويبدو عطبًا.
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await response.json()) as T;
}
