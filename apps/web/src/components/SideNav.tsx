import Link from "next/link";

import type { Locale, Messages } from "@/lib/i18n";
import { SessionControl } from "./SessionControl";
import { translator } from "@/lib/i18n";

const ITEMS: Array<{ key: string; path: string }> = [
  { key: "nav.dashboard", path: "" },
  { key: "nav.profile", path: "profile" },
  { key: "nav.facts", path: "facts" },
  { key: "nav.memory", path: "memory" },
  { key: "nav.promotion", path: "promotion" },
  { key: "nav.portfolio", path: "portfolio" },
  { key: "nav.team", path: "team" },
  { key: "nav.thread", path: "thread" },
  { key: "nav.library", path: "library" },
  { key: "nav.claims", path: "claims" },
  { key: "nav.theses", path: "theses" },
  { key: "nav.opportunities", path: "opportunities" },
  { key: "nav.manuscripts", path: "manuscripts" },
  { key: "nav.analysis", path: "analysis" },
  { key: "nav.trends", path: "trends" },
  { key: "nav.briefs", path: "briefs" },
  { key: "nav.approvals", path: "approvals" },
  { key: "nav.agents", path: "agents" },
  { key: "nav.traces", path: "traces" },
  { key: "nav.audit", path: "audit" },
  { key: "nav.settings", path: "settings" },
];

export function SideNav({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  return (
    <nav aria-label={t("nav.dashboard")}>
      <ul className="nav-list">
        {ITEMS.map((item) => (
          <li key={item.key}>
            <Link href={`/${locale}${item.path ? `/${item.path}` : ""}`}>{t(item.key)}</Link>
          </li>
        ))}
      </ul>
      <SessionControl locale={locale} messages={messages} />
    </nav>
  );
}
