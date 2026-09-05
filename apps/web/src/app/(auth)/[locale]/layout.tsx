import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { FONT_VARIABLES } from "@/lib/fonts";
import { BrandMark } from "@/components/BrandMark";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { DEFAULT_LOCALE, LOCALES, direction, getMessages, isLocale, translator } from "@/lib/i18n";
import "../../../styles/globals.css";

/**
 * قشرةُ الحساب | The auth shell — **ولا قائمةَ منتجٍ فيها**.
 *
 * كانت صفحاتُ الدخول والتسجيل والاستعادة تُصيَّر داخل هيكل التطبيق نفسه:
 * شريطٌ جانبيّ بثلاثة عشر رابطًا، كلُّها خلف مصادقةٍ لم تقع بعد. فيرى من
 * لا حساب له خريطةَ منتجٍ لا يملك منه شيئًا، ويقرأ قارئُ الشاشة ثلاثةَ
 * عشر رابطًا قبل أن يبلغ حقلَ البريد. والزائرُ الذي ينقر واحدًا منها
 * يُقذف إلى الصفحة التي هو فيها.
 *
 * **والفصل بالمسار لا بشرطٍ في التصيير.** مجموعةُ `(auth)` لا تظهر في
 * الرابط — `‎/ar/login` كما كان — ولها تخطيطُ جذرٍ خاصّ بها. فلا يصل
 * الشريطُ الجانبي إلى هنا أصلًا، ولا يُخفى بعد أن يُرسَل: الفرقُ بينهما
 * أنّ الأول لا يُبنى، والثاني يُبنى ثم يُمحى بعد أن رآه من رآه.
 *
 * ولا `AuthGate` هنا: هذه هي الصفحات التي تُنشئ الجلسة، فحراستُها بها
 * دورٌ حول نفسه.
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
    title: `${t("auth.signIn")} — ${t("app.name")}`,
    icons: { icon: "/favicon.svg" },
    // صفحاتُ حسابٍ لا تُفهرَس: لا محتوى فيها لباحثٍ يبحث.
    robots: { index: false, follow: true },
  };
}

export default async function AuthLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();

  const messages = getMessages(locale);
  const t = translator(messages);

  return (
    <html lang={locale} dir={direction(locale)} className={FONT_VARIABLES}>
      <body>
        <a className="skip-link" href="#main-content">
          {t("common.skipToContent")}
        </a>
        <div className="auth-shell">
          {/*
            الخيط يمرّ خلف البطاقة — عنصرُ الهويّة نفسه الذي في الهيكل
            وفي الصفحة العامّة، فلا يشعر الداخل أنه انتقل إلى منتجٍ آخر.
          */}
          <div className="auth-thread" aria-hidden="true" />
          <main className="auth-main" id="main-content" tabIndex={-1}>
            <div className="auth-card">
              <Link className="auth-brand" href="/">
                <BrandMark idSuffix="auth" size={36} />
                <span>
                  <strong>{t("app.name")}</strong>
                  <span>{t("app.promise")}</span>
                </span>
              </Link>
              {children}
            </div>
            <div className="auth-foot">
              <LocaleSwitcher locale={locale} messages={messages} />
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
