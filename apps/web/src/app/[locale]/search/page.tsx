"use client";

import { use, useState } from "react";
import Link from "next/link";

import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * البحث العلمي.
 *
 * لا نتائج مُصطنعة. سجل الأدبيات مضبوط على «بلا شبكة»، فالبحث الخارجي
 * معطّل ويُعلَن — ويُوجَّه المستخدم إلى ما يعمل فعلًا اليوم: الاستيراد
 * اليدوي بـDOI إلى مكتبته.
 */
export default function SearchPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const { literatureOnline, loading } = usePosture(locale);
  const [query, setQuery] = useState("");
  const disabled = loading || !literatureOnline;

  return (
    <>
      <div className="page-head">
        <h1>{t("search.title")}</h1>
        <p>{t("search.subtitle")}</p>
      </div>

      <form className="form" style={{ maxInlineSize: "56ch" }} onSubmit={(e) => e.preventDefault()}>
        <label>
          {t("search.title")}
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("search.placeholder")}
            disabled={disabled}
          />
        </label>
        <button type="submit" disabled={disabled || query.trim() === ""}>
          {t("search.submit")}
        </button>
      </form>

      {!loading && !literatureOnline ? (
        <div className="gate" style={{ marginBlockStart: 18 }}>
          <span aria-hidden="true">⏻</span>
          <span>
            <strong>{t("search.gateTitle")}</strong> {t("search.gateBody")}{" "}
            <Link href={`/${locale}/library`}>{t("nav.library")}</Link>
          </span>
        </div>
      ) : null}
    </>
  );
}
