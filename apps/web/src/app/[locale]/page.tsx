import Link from "next/link";

import { AtheraAiInput } from "@/components/AtheraAiInput";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * الرئيسية — مركز أفعال بحثية، لا لوحة مؤشرات.
 *
 * ما كان هنا: ستة عدّادات، أربعة منها مقاييس لائحة ترقية، وكلها تعرض شرطة.
 * لوحة تفتح على أصفار تُعلّم المستخدم أن المنتج فارغ. والسؤال الأول الآن
 * سؤال لا رقم: «ماذا تريد أن تنجز؟»
 *
 * ولا عدّاد أجنتات ولا تشغيلات ولا أحداث تدقيق — تلك أعداد تصف النظام
 * لنفسه، والباحث لم يأتِ ليقرأ عن النظام.
 */
const ACTIONS = [
  { key: "idea", path: "ai", icon: "✦", tint: "var(--ai-tint)" },
  { key: "thesis", path: "theses", icon: "◈", tint: "color-mix(in srgb, var(--sky) 12%, transparent)" },
  { key: "data", path: "analysis", icon: "▣", tint: "color-mix(in srgb, var(--teal) 12%, transparent)" },
  { key: "search", path: "search", icon: "⌕", tint: "color-mix(in srgb, var(--violet) 12%, transparent)" },
  { key: "continue", path: "portfolio", icon: "◑", tint: "color-mix(in srgb, var(--mint) 45%, transparent)" },
];

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const messages = getMessages(locale);
  const t = translator(messages);

  return (
    <>
      <div className="page-head">
        <h1>{t("home.title")}</h1>
        <p>{t("home.subtitle")}</p>
      </div>

      <section aria-label={t("ai.title")} style={{ maxInlineSize: "78ch", marginBlockEnd: 34 }}>
        <AtheraAiInput locale={locale} messages={messages} />
      </section>

      <section aria-label={t("home.actionsLabel")}>
        <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 12 }}>
          {t("home.actionsLabel")}
        </p>
        <div className="actions">
          {ACTIONS.map((action) => (
            <Link className="action" key={action.key} href={`/${locale}/${action.path}`}>
              <span className="action-icon" aria-hidden="true" style={{ background: action.tint }}>
                {action.icon}
              </span>
              <strong>{t(`home.${action.key}Title`)}</strong>
              <span>{t(`home.${action.key}Hint`)}</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
