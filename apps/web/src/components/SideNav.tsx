import Link from "next/link";

import type { Locale, Messages } from "@/lib/i18n";
import { SessionControl } from "./SessionControl";
import { translator } from "@/lib/i18n";

/**
 * التنقل الرئيسي — **أربعة عناصر**.
 *
 * كانت اثني عشر، وكان كل عنصر منها مدخلًا موازيًا إلى الشيء نفسه: الباحث
 * يفتح «مكتبتي» فيرى ملفاتٍ لا يعرف أيّها لأيّ بحث، و«استوديو الورقة»
 * فيرى مخطوطاتٍ لا يعرف على أيّ دليلٍ بُنيت. فكان الربط بينها في رأسه
 * وحده — والقائمةُ الطويلة تُعلّم أن المنتج نظامٌ يُدار لا أداةٌ تُستعمل.
 *
 * **والبحث هو الشيء المركزي.** فما يخدم بحثًا يُفتح من داخله: أدبياته
 * ومراجعه وملفاته وبياناته ومخرجاته ومخطوطته ونشره. ويبقى في القائمة ما
 * يسبق البحث أو يعلوه: الرئيسية، والمساعد، وأبحاثي، ومكتبتي.
 *
 * والمنقول **لم يُحذف ولم يتغيّر مساره**: ما لم يصر بعدُ مساحةً داخل البحث
 * يبقى مفتوحًا من «أدوات أخرى» أدناه، ومن حفظ رابطًا يعمل رابطه. وإخفاءُ
 * أداةٍ عاملة من كل مدخل ليس تبسيطًا، بل عطبٌ يُسمّى تبسيطًا.
 */
const PRIMARY: Array<{ key: string; path: string }> = [
  { key: "nav.dashboard", path: "" },
  { key: "nav.ai", path: "ai" },
  { key: "nav.portfolio", path: "portfolio" },
  { key: "nav.library", path: "library" },
];

/** ما ينتظر موضعه داخل البحث — مفتوحٌ الآن، غير معروضٍ دائمًا. */
const SECONDARY: Array<{ key: string; path: string }> = [
  { key: "nav.search", path: "search" },
  { key: "nav.theses", path: "theses" },
  { key: "nav.analysis", path: "analysis" },
  { key: "nav.manuscripts", path: "manuscripts" },
  { key: "nav.journals", path: "journals" },
  { key: "nav.review", path: "review" },
  { key: "nav.trends", path: "trends" },
  { key: "nav.settings", path: "settings" },
];

export function SideNav({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const link = (item: { key: string; path: string }) => (
    <li key={item.key}>
      <Link href={`/${locale}${item.path ? `/${item.path}` : ""}`}>
        <span className="nav-dot" aria-hidden="true" />
        {t(item.key)}
      </Link>
    </li>
  );

  return (
    <nav aria-label={t("nav.dashboard")}>
      <ul className="nav-list">{PRIMARY.map(link)}</ul>
      <details>
        <summary className="nav-label">{t("nav.sectionMore")}</summary>
        <ul className="nav-list">{SECONDARY.map(link)}</ul>
      </details>
      <SessionControl locale={locale} messages={messages} />
    </nav>
  );
}
