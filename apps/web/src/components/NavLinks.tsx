"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * روابط التنقّل — **وواحدٌ منها نشط، لا أكثر**.
 *
 * كان في القائمة عيبان يتظاهران بالنشاط:
 *
 *   ١ لم يكن `aria-current` يُضبط إطلاقًا، فلا صفحة تُعلن نفسها موضعَ
 *     الباحث. وقارئ الشاشة يقرأ ثلاثة عشر رابطًا متساوية، والباحث المبصر
 *     يبحث عن موضعه بالذاكرة.
 *   ٢ وكانت الورقة تلوّن `li:nth-child(2)` في **كل** قائمة — فالعنصر
 *     الثاني من القائمة الأولى والعنصر الثاني من الثانية يلبسان لباس
 *     الصفحة الجارية معًا، على أيّ صفحة كان الباحث. فالتمييز البصري الذي
 *     وُضع ليقول «أنت هنا» صار يقوله في موضعين ليس أحدهما هنا.
 *
 * والمطابقة **بالمقطع لا بالسابقة النصّية**: `/ar/theses` و`/ar/thread`
 * يتشاركان الحروف الأربعة الأولى، ومطابقةُ السوابق تجعل «الرسائل» تُضيء
 * على «الخيط الذهبي». فيُقتطع أول مقطع بعد اللغة ويُقارَن بالتساوي.
 *
 * **والمسار المملوك يُعلن صراحةً.** `/ar/profile` ليس عنصرًا في القائمة،
 * لكنه يُفتح من الإعدادات — فتُضيء «الإعدادات» وهو فيها، ولا يُترك بلا
 * موضع. وما لا يملكه أحد (`/ar/login`) لا يُضيء شيئًا: صفرٌ أصدق من واحدٍ
 * مخترَع.
 */
export interface NavItem {
  key: string;
  label: string;
  /** أول مقطع بعد اللغة — `""` للرئيسية. */
  segment: string;
  /** مقاطع أخرى تُعدّ من هذا العنصر. */
  owns?: string[];
}

export interface NavGroup {
  id: string;
  /** عنوان مجموعة دلالية — و`null` لما لا يحتاج عنوانًا. */
  label: string | null;
  items: NavItem[];
}

/** أول مقطع بعد اللغة: `/ar/portfolio/123` ← `portfolio`، و`/ar` ← `""`. */
export function segmentOf(pathname: string, locale: string): string {
  const withoutLocale = pathname.replace(new RegExp(`^/${locale}(?=/|$)`), "");
  return withoutLocale.split("/").filter(Boolean)[0] ?? "";
}

/** مفتاحُ العنصر النشط — أو `null` إن لم يملك المسارَ أحد. */
export function activeKey(groups: NavGroup[], segment: string): string | null {
  for (const group of groups) {
    for (const item of group.items) {
      if (item.segment === segment) return item.key;
      if (item.owns?.includes(segment)) return item.key;
    }
  }
  return null;
}

export function NavLinks({
  locale,
  groups,
  label,
}: {
  locale: string;
  groups: NavGroup[];
  label: string;
}) {
  const pathname = usePathname() ?? `/${locale}`;
  const active = activeKey(groups, segmentOf(pathname, locale));

  return (
    <nav aria-label={label}>
      {groups.map((group) => (
        <div className="nav-group" key={group.id}>
          {group.label ? (
            <h2 className="nav-label" id={`nav-${group.id}`}>
              {group.label}
            </h2>
          ) : null}
          <ul
            className="nav-list"
            aria-labelledby={group.label ? `nav-${group.id}` : undefined}
          >
            {group.items.map((item) => {
              const current = item.key === active;
              return (
                <li key={item.key}>
                  <Link
                    href={`/${locale}${item.segment ? `/${item.segment}` : ""}`}
                    // **الدلالة قبل اللون.** `aria-current` هو ما يقرؤه
                    // قارئ الشاشة؛ والخلفية والوزن والشريط الجانبي تتبعه
                    // في الورقة، فلا يبقى اللون حاملَ المعنى وحده.
                    aria-current={current ? "page" : undefined}
                    data-active={current ? "true" : undefined}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
