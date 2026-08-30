/**
 * ثنائية اللغة | Bilingual routing and message loading (§26.4، §38.4).
 *
 * العربية RTL ليست انعكاسًا لاحقًا للإنجليزية: كلتاهما لغة أولى، ولكل منهما
 * اتجاه ومحاذاة يُحسمان في الـHTML لا بـCSS مرآة.
 */
import ar from "../../messages/ar.json";
import en from "../../messages/en.json";

export const LOCALES = ["ar", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "ar";

const CATALOGS = { ar, en } as const;
export type Messages = typeof ar;

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

export function getMessages(locale: Locale): Messages {
  return CATALOGS[locale];
}

export function direction(locale: Locale): "rtl" | "ltr" {
  return locale === "ar" ? "rtl" : "ltr";
}

/** اللغة المقابلة — للتبديل بنقرة واحدة مع حفظ الموضع في الصفحة. */
export function otherLocale(locale: Locale): Locale {
  return locale === "ar" ? "en" : "ar";
}

/** قراءة مفتاح متداخل بأمان: t("dashboard.title") */
export function translator(messages: Messages) {
  return (path: string): string => {
    const value = path
      .split(".")
      .reduce<unknown>((node, key) => (node as Record<string, unknown>)?.[key], messages);
    return typeof value === "string" ? value : path;
  };
}
