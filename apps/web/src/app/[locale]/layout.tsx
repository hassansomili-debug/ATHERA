import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { SideNav } from "@/components/SideNav";
import { DEFAULT_LOCALE, LOCALES, direction, getMessages, isLocale, translator } from "@/lib/i18n";
import "../../styles/globals.css";

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ locale: string }> },
): Promise<Metadata> {
  const { locale } = await params;
  const active = isLocale(locale) ? locale : DEFAULT_LOCALE;
  const t = translator(getMessages(active));
  return { title: `${t("app.name")} — ${t("app.tagline")}` };
}

export default async function LocaleLayout({
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
    // الاتجاه يُحسم على عنصر <html> — لا مرآة CSS لاحقة (§38.4).
    <html lang={locale} dir={direction(locale)}>
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand">
              <span className="brand-mark" aria-hidden="true" />
              {/*
                **الوعد تحت الاسم، لا اسمٌ ثانٍ مكتوب بيده.**

                كان السطر الثاني اسم اللغة الأخرى مكتوبًا حرفيًّا:
                `locale === "ar" ? "ATHERA" : "أثيرا"`. فلمّا صار الاسم
                «بُبريفا · PUBRIVA» بقي الحرفان على حالهما — فالقائمة تقول
                الاسم الجديد والشعار يقول القديم في الشاشة نفسها. وهو الخطأ
                المتكرر: قيمةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.

                فيقول السطر الثاني ما تفعله المنصّة لا اسمها بلغةٍ أخرى —
                واسمها يعرفه من قرأ السطر الأول.
              */}
              <span>
                <strong>{t("app.name")}</strong>
                <span>{t("app.promise")}</span>
              </span>
            </div>
            <SideNav locale={locale} messages={messages} />
            <LocaleSwitcher locale={locale} messages={messages} />
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
