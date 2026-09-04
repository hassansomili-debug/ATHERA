import Link from "next/link";

import { HomeIntake } from "@/components/HomeIntake";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * الرئيسية — **ابدأ أو أكمل**، لا لوحة مؤشرات ولا محادثة ثانية.
 *
 * ما كان هنا قبلَ ذلك: ستة عدّادات، أربعة منها مقاييس لائحة ترقية، وكلها
 * تعرض شرطة. ولوحةٌ تفتح على أصفار تُعلّم المستخدم أن المنتج فارغ.
 * والسؤال الأول الآن سؤالٌ لا رقم: «ماذا تريد أن تنجز؟»
 *
 * **وكان هنا بعد ذلك مربّع المحادثة نفسه الذي في «بُبريفا AI»** — بحرفه
 * وأزراره وإرساله. فصار للمنتج عقلان في شاشتين، ولا يعرف الباحث أين يجد
 * ما سأله بالأمس. فالرئيسية توجّه، وصفحة الذكاء تنفّذ، ولا تزاحم إحداهما
 * الأخرى.
 *
 * **وبطاقةُ «ابحث عن أوراق علمية» كانت تفتح البابَ المغلق.** كانت تذهب إلى
 * `/search` — وهو ينادي مسارًا يتوقّف عند أوّل فهرس، ويبقى زرُّه معطَّلًا
 * ما دام `LITERATURE_REGISTRY=offline`، وهي حاله في الإنتاج. فبطاقةٌ في
 * أوّل شاشةٍ في المنتج تقود إلى شاشةٍ لا تعمل. وصارت تذهب إلى
 * `/references`: فهرسان يُسألان معًا، بلا مفتاح ولا إعداد.
 */
const ACTIONS = [
  { key: "idea", path: "ai", icon: "✦", tint: "var(--ai-tint)" },
  { key: "search", path: "references", icon: "⌕", tint: "color-mix(in srgb, var(--violet) 12%, transparent)" },
  { key: "thesis", path: "theses", icon: "◈", tint: "color-mix(in srgb, var(--sky) 12%, transparent)" },
  { key: "data", path: "analysis", icon: "▣", tint: "color-mix(in srgb, var(--teal) 12%, transparent)" },
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

      <section
        aria-label={t("home.startLabel")}
        style={{ maxInlineSize: "78ch", marginBlockEnd: 34 }}
      >
        <HomeIntake locale={locale} messages={messages} />
      </section>

      <section aria-label={t("home.actionsLabel")}>
        <h2 className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 12 }}>
          {t("home.actionsLabel")}
        </h2>
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
