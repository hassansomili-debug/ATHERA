/**
 * عميل الـAPI | API client.
 *
 * §38.6.8 — هذا هو المنفذ الوحيد للخارج من المتصفح: خادمنا فقط. لا مزود
 * نموذج، ولا مفتاح، ولا استدعاء مباشر. CSP تمنع غير ذلك، وAT-S0-09 يفشل
 * البناء لو حاول أحد.
 */
import type { Locale } from "./i18n";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

export async function apiFetch<T>(
  path: string,
  { locale, token, ...init }: RequestInit & { locale: Locale; token?: string },
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": locale,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

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
