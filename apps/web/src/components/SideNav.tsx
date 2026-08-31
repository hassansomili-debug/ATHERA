import Link from "next/link";

import type { Locale, Messages } from "@/lib/i18n";
import { SessionControl } from "./SessionControl";
import { translator } from "@/lib/i18n";

/**
 * التنقل الرئيسي — اثنا عشر عنصرًا.
 *
 * ما سقط من المستوى الأول لم يُحذف: الأجنتات وأثر التشغيل وسجل التدقيق
 * وصندوق القرارات والخيط الذهبي وسجل الادعاءات والفريق والنشرات وفرص
 * النشر — كلها تبقى بمساراتها كما هي، وتُبلَغ من قسمين أدنى. الباحث لا
 * يبدأ يومه من سجل تدقيق.
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

/** ما كان في القائمة الرئيسية وصار داخل سياق البحث — بمساراته نفسها. */
const WORKSPACE: Array<{ key: string; path: string }> = [
  { key: "nav.thread", path: "thread" },
  { key: "nav.claims", path: "claims" },
  { key: "nav.opportunities", path: "opportunities" },
  { key: "nav.team", path: "team" },
  { key: "nav.approvals", path: "approvals" },
  { key: "nav.briefs", path: "briefs" },
];

/** الحساب والشفافية: ما يخص هوية الباحث وما يفسّر تصرّف النظام. */
const ACCOUNT: Array<{ key: string; path: string }> = [
  { key: "nav.profile", path: "profile" },
  { key: "nav.facts", path: "facts" },
  { key: "nav.memory", path: "memory" },
  { key: "nav.agents", path: "agents" },
  { key: "nav.traces", path: "traces" },
  { key: "nav.audit", path: "audit" },
];

function Item({ locale, item, t, ai }: {
  locale: Locale;
  item: { key: string; path: string };
  t: (k: string) => string;
  ai?: boolean;
}) {
  return (
    <li className={ai ? "nav-ai" : undefined}>
      <Link href={`/${locale}${item.path ? `/${item.path}` : ""}`}>
        <span className="nav-dot" aria-hidden="true" />
        {t(item.key)}
      </Link>
    </li>
  );
}

export function SideNav({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  return (
    <nav aria-label={t("nav.dashboard")}>
      <ul className="nav-list">
        {PRIMARY.map((item) => (
          <Item key={item.key} locale={locale} item={item} t={t} ai={item.path === "ai"} />
        ))}
      </ul>

      <div className="nav-section">
        <p className="nav-label">{t("nav.sectionWorkspace")}</p>
        <ul className="nav-list">
          {WORKSPACE.map((item) => <Item key={item.key} locale={locale} item={item} t={t} />)}
        </ul>
      </div>

      <div className="nav-section">
        <p className="nav-label">{t("nav.sectionAccount")}</p>
        <ul className="nav-list">
          {ACCOUNT.map((item) => <Item key={item.key} locale={locale} item={item} t={t} />)}
        </ul>
      </div>

      <SessionControl locale={locale} messages={messages} />
    </nav>
  );
}
