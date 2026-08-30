"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { Locale, Messages } from "@/lib/i18n";
import { otherLocale, translator } from "@/lib/i18n";

/**
 * التبديل يحفظ الموضع في الصفحة: /ar/promotion ⇄ /en/promotion.
 * تبديل اللغة لا يعيد المستخدم إلى البداية — وهذا فرق ملموس في منتج عربي أولًا.
 */
export function LocaleSwitcher({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const pathname = usePathname() ?? `/${locale}`;
  const target = otherLocale(locale);
  const nextPath = pathname.replace(new RegExp(`^/${locale}`), `/${target}`);

  return (
    <div className="locale-switch">
      <span>{t("common.language")}: </span>
      <Link href={nextPath} lang={target} hrefLang={target}>
        {target === "ar" ? t("common.arabic") : t("common.english")}
      </Link>
    </div>
  );
}
