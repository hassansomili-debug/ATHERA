"use client";

import Link from "next/link";
import { use } from "react";

import { ThesisJourney } from "@/components/ThesisJourney";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * صفحةُ رحلة الرسالة إلى ورقة.
 *
 * **وصفحةٌ رقيقة عمدًا**: كلُّ المنطق في `ThesisJourney`، وكلُّ القرار في
 * الخادم. وما هنا إلّا حلُّ اللغة والمعرّف وعنوانٌ ورابطُ رجوع.
 */
export default function JourneyPage({
  params,
}: {
  params: Promise<{ locale: string; thesisId: string }>;
}) {
  const { locale: raw, thesisId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const messages = getMessages(locale);
  const t = translator(messages);

  return (
    <>
      <h1>{t("journey.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>
        {t("journey.subtitle")}
      </p>

      <ThesisJourney thesisId={thesisId} locale={locale} messages={messages} />

      <p style={{ marginBlockStart: "calc(var(--space) * 2)" }}>
        <Link href={`/${locale}/theses`} data-testid="journey-back">
          {t("theses.title")}
        </Link>
      </p>
    </>
  );
}
