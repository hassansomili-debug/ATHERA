import Link from "next/link";

import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * المراجعة والتحكيم.
 *
 * أربعة أنماط مراجعة يفهمها الباحث، لا خمسة أسماء أجنتات داخلية. والمجلس
 * القائم في استوديو الورقة هو ما ينفّذها فعلًا — فهذه الصفحة مدخل يشرح
 * ويحيل، لا واجهة ثانية تكرّر منطقًا.
 */
const MODES = [
  { key: "scientific", icon: "◎", tint: "color-mix(in srgb, var(--aqua) 13%, transparent)" },
  { key: "method", icon: "◇", tint: "color-mix(in srgb, var(--sky) 13%, transparent)" },
  { key: "statistical", icon: "▤", tint: "color-mix(in srgb, var(--violet) 12%, transparent)" },
  { key: "editorial", icon: "✎", tint: "color-mix(in srgb, var(--mint) 45%, transparent)" },
];

export default async function ReviewPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  return (
    <>
      <div className="page-head">
        <h1>{t("review.title")}</h1>
        <p>{t("review.subtitle")}</p>
      </div>

      <div className="actions" style={{ marginBlockEnd: 22 }}>
        {MODES.map((mode) => (
          <article className="action" key={mode.key} style={{ cursor: "default" }}>
            <span className="action-icon" aria-hidden="true" style={{ background: mode.tint }}>
              {mode.icon}
            </span>
            <strong>{t(`review.${mode.key}`)}</strong>
            <span>{t(`review.${mode.key}Hint`)}</span>
          </article>
        ))}
      </div>

      <p>
        <Link href={`/${locale}/manuscripts`}>{t("review.open")} →</Link>
      </p>
      <p className="provenance-note">{t("review.note")}</p>
    </>
  );
}
