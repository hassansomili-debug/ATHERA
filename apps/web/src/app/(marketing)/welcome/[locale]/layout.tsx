import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";
import { DEFAULT_LOCALE, LOCALES, direction, getMessages, isLocale, otherLocale, translator } from "@/lib/i18n";
import "../../../../styles/globals.css";

/**
 * قشرةُ الموقع العام | The public marketing shell — **القشرة الثالثة**.
 *
 * **الجذرُ كان أربعمئة وأربعة.** لا صفحةَ عند `/` أصلًا؛ والوسيط يحوّل كلَّ
 * ما لا يحمل لغةً إلى `‎/ar`، و`‎/ar` تطبيقٌ محميّ يقذف من لا جلسة له إلى
 * الدخول. فمن كتب اسم النطاق في متصفّحه بلغ نموذجَ دخولٍ لمنتجٍ لا يعرف ما
 * هو — ولا سبيل له إلى معرفته.
 *
 * وهذه قشرةٌ مستقلّة عن الهيكل وعن قشرة الحساب: لا شريطَ جانبيّ، ولا
 * `AuthGate`، ولا نداءَ واجهةٍ برمجية. صفحةٌ تُقرأ بلا حساب وبلا شبكةٍ إلى
 * خادمنا.
 *
 * **واللغة في المسار لا في استعلام.** `‎/welcome/ar` و`‎/welcome/en`
 * مستندان مستقلّان، لكلٍّ `lang` و`dir` صحيحان على `<html>` نفسه — وهو ما
 * لا يقدر عليه تخطيطٌ يقرأ لغتَه من `?lang`: التخطيط لا يرى الاستعلام.
 * والوسيطُ **يُعيد كتابة** `/` إلى هذا المسار بلا تحويل، فيبقى ما يراه
 * الباحث في شريط العنوان هو النطاق وحده.
 */
export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ locale: string }> },
): Promise<Metadata> {
  const { locale } = await params;
  const active = isLocale(locale) ? locale : DEFAULT_LOCALE;
  const t = translator(getMessages(active));
  return {
    metadataBase: new URL("https://pubriva.com"),
    title: `${t("app.name")} — ${t("app.tagline")}`,
    description: t("landing.body"),
    icons: { icon: "/favicon.svg" },
    // **الأصل هو الجذر.** الصفحة تُخدَم من `/` بإعادة كتابة، فلو أعلنت
    // مسارَها الداخلي أصلًا لنفسها لفُهرِس رابطٌ لا يكتبه أحد.
    alternates: {
      canonical: active === DEFAULT_LOCALE ? "/" : `/welcome/${active}`,
      languages: { ar: "/", en: "/welcome/en" },
    },
  };
}

export default async function MarketingLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();

  const t = translator(getMessages(locale));
  const other = otherLocale(locale);
  const otherHref = other === DEFAULT_LOCALE ? "/" : `/welcome/${other}`;

  return (
    <html lang={locale} dir={direction(locale)}>
      <body>
        <a className="skip-link" href="#main-content">
          {t("common.skipToContent")}
        </a>
        <div className="site">
          <header className="site-head">
            <a className="site-brand" href="/">
              <BrandMark idSuffix="head" size={34} />
              <span>
                <strong>{t("app.name")}</strong>
                <span>{t("app.promise")}</span>
              </span>
            </a>
            <nav className="site-nav" aria-label={t("landing.siteNavLabel")}>
              <a href={otherHref} lang={other} hrefLang={other}>
                {other === "ar" ? t("common.arabic") : t("common.english")}
              </a>
              <a href={`/${locale}/login`}>{t("auth.signIn")}</a>
              <a className="site-cta" href={`/${locale}/register`}>
                {t("landing.primaryCta")}
              </a>
            </nav>
          </header>

          <main className="site-main" id="main-content" tabIndex={-1}>
            {children}
          </main>

          <footer className="site-foot">
            <div className="site-brand">
              <BrandMark idSuffix="foot" size={28} />
              <span>
                <strong>{t("app.name")}</strong>
                <span>{t("landing.footerNote")}</span>
              </span>
            </div>
            <nav aria-label={t("landing.footerLabel")}>
              <a href={`/${locale}/login`}>{t("auth.signIn")}</a>
              <a href={`/${locale}/register`}>{t("landing.primaryCta")}</a>
              <a href={otherHref} lang={other} hrefLang={other}>
                {other === "ar" ? t("common.arabic") : t("common.english")}
              </a>
            </nav>
          </footer>
        </div>
      </body>
    </html>
  );
}
