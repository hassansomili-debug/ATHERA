import Link from "next/link";

import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * المجلات والنشر.
 *
 * ثلاثة أشياء تُعرض معًا: ملاءمة هدف النشر، وطبقة المجلة المستهدفة، وأسباب
 * المطابقة. ولا رابع: **لا احتمال قبول** — لا يقدّره النظام ولا يملك حقلًا
 * له، وإظهار رقم مكانه أسوأ من عدم إظهار شيء.
 */
const POINTS = [
  { key: "publicationFit", tint: "color-mix(in srgb, var(--aqua) 13%, transparent)", icon: "◎" },
  { key: "targetTier", tint: "color-mix(in srgb, var(--sky) 13%, transparent)", icon: "▲" },
  { key: "reasons", tint: "color-mix(in srgb, var(--violet) 12%, transparent)", icon: "☰" },
];

export default async function JournalsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  return (
    <>
      <div className="page-head">
        <h1>{t("journalsPage.title")}</h1>
        <p>{t("journalsPage.subtitle")}</p>
      </div>

      <div className="actions" style={{ marginBlockEnd: 22 }}>
        {POINTS.map((point) => (
          <article className="action" key={point.key} style={{ cursor: "default" }}>
            <span className="action-icon" aria-hidden="true" style={{ background: point.tint }}>
              {point.icon}
            </span>
            <strong>{t(`journalsPage.${point.key}`)}</strong>
            <span>{t(`journalsPage.${point.key}Hint`)}</span>
          </article>
        ))}
      </div>

      <p>
        <Link href={`/${locale}/manuscripts`}>{t("journalsPage.openStudio")} →</Link>
      </p>
      <p className="provenance-note">{t("journalsPage.note")}</p>
    </>
  );
}
