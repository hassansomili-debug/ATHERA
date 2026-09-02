/**
 * عميل الـAPI | API client.
 *
 * §38.6.8 — هذا هو المنفذ الوحيد للخارج من المتصفح: خادمنا فقط. لا مزود
 * نموذج، ولا مفتاح، ولا استدعاء مباشر. CSP تمنع غير ذلك، وAT-S0-09 يفشل
 * البناء لو حاول أحد.
 */
import type { Locale } from "./i18n";
import { clearSession, getAccessToken } from "./session";

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
export async function apiFetch<T>(
  path: string,
  { locale, token, ...init }: RequestInit & { locale: Locale; token?: string },
): Promise<T> {
  // يُعلَن الخلل قبل الطلب: محاولة الاتصال بـlocalhost من نطاق منشور تُحجب
  // في المتصفح برسالة CSP غامضة، فيبدو العطب في الخادم لا في الإعداد.
  if (isApiMisconfigured()) {
    throw new AtheraApiError(0, { ...MISCONFIGURED_ERROR, locale });
  }

  const bearer = token ?? getAccessToken();
  // **رفع الملفات يفرض نوعه بنفسه.** `FormData` يحتاج حدًّا فاصلًا
  // (boundary) يولّده المتصفح ويضعه في الترويسة؛ وفرضُ `application/json`
  // فوقه يُنتج طلبًا لا يستطيع الخادم تفكيكه. ولهذا كان الرفع يلتفّ على
  // هذا العميل ويبني `fetch` بنفسه — فيفقد حارس الإعداد وتوحيد الأخطاء.
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

  if (response.status === 401 && !path.startsWith("/api/v1/auth/")) {
    // رمز منتهٍ أو مفقود: تُمحى الجلسة ويُعاد التوجيه إلى الدخول بدل ترك
    // المستخدم أمام «بيانات الدخول غير صحيحة» في شاشة لا علاقة لها بالدخول.
    clearSession();
    if (typeof window !== "undefined") {
      window.location.href = `/${locale}/login`;
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
  return (await response.json()) as T;
}
