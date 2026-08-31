import Link from "next/link";

import { type Locale, type Messages, translator } from "@/lib/i18n";

/**
 * روابط سياقية — ما لا يستحق موضعًا دائمًا في القائمة.
 *
 * القاعدة التي تحكم الموضع: أداةٌ يفتحها الباحث **وهو داخل مشروع** تنتمي
 * إلى المشروع؛ وأداةٌ تصف النظام لنفسه تنتمي إلى الإعدادات. وكلتاهما تبقى
 * على مسارها الأصلي بلا إعادة توجيه — النقل تنظيمٌ لا هجرة.
 */
export function ContextLinks({
  locale, messages, label, items, note,
}: {
  locale: Locale;
  messages: Messages;
  label: string;
  items: Array<{ key: string; path: string; hint?: string }>;
  note?: string;
}) {
  const t = translator(messages);
  return (
    <section style={{ marginBlockStart: 30 }}>
      <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 12 }}>{t(label)}</p>
      <div className="grid">
        {items.map((item) => (
          <Link className="action" key={item.key} href={`/${locale}/${item.path}`}>
            <strong>{t(item.key)}</strong>
            {item.hint ? <span>{t(item.hint)}</span> : null}
          </Link>
        ))}
      </div>
      {note ? <p className="note" style={{ marginBlockStart: 12 }}>{t(note)}</p> : null}
    </section>
  );
}
