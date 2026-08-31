import Link from "next/link";

import type { Locale, Messages } from "@/lib/i18n";
import { SessionControl } from "./SessionControl";
import { translator } from "@/lib/i18n";

/**
 * التنقل الرئيسي — اثنا عشر عنصرًا، ولا شيء غيرها.
 *
 * ما كان هنا وسقط لم يُحذف ولم يتغيّر مساره: الخيط الذهبي والادعاءات وفرص
 * النشر والفريق وصندوق القرارات والنشرات انتقلت إلى **أدوات المشروع** في
 * «أبحاثي»؛ والملف والحقائق والذاكرة وقدرات أثيرا AI إلى **الإعدادات**؛
 * وسجل التشغيل وسجل التدقيق إلى قسم **متقدّم** داخل الإعدادات، ولا يظهر
 * إلا لمن يحمل دورًا إداريًا.
 *
 * والمبدأ الذي فرض ذلك: الباحث يفتح المنصة ليبحث، لا ليقرأ عن بنيتها.
 * قائمة تعرض «سجل التشغيل» و«الأجنتات» دائمًا تُعلّم المستخدم أن المنتج
 * نظامٌ يُدار، لا أداةٌ تُستعمل.
 */
const PRIMARY: Array<{ key: string; path: string }> = [
  { key: "nav.dashboard", path: "" },
  { key: "nav.ai", path: "ai" },
  { key: "nav.portfolio", path: "portfolio" },
  { key: "nav.library", path: "library" },
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
  return (
    <nav aria-label={t("nav.dashboard")}>
      <ul className="nav-list">
        {PRIMARY.map((item) => (
          <li key={item.key}>
            <Link href={`/${locale}${item.path ? `/${item.path}` : ""}`}>
              <span className="nav-dot" aria-hidden="true" />
              {t(item.key)}
            </Link>
          </li>
        ))}
      </ul>
      <SessionControl locale={locale} messages={messages} />
    </nav>
  );
}
