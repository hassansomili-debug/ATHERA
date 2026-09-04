"use client";

import { use, useState } from "react";
import Link from "next/link";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * البحث العلمي.
 *
 * **والزرّ كان يَعِد ولا يفعل.** النموذج كان `onSubmit={(e) => e.preventDefault()}`
 * وحده: لا نداء، ولا نتيجة، ولا رسالة. وكان العيب مستورًا لأن البوابة
 * تُعطّل الزرّ ما دام سجل الأدبيات «بلا شبكة» — فمتى فُتح السجل صار زرًّا
 * حيًّا لا يفعل شيئًا، والباحث يضغطه فلا يحدث شيء ولا يعرف لماذا.
 *
 * والمسار قائمٌ في الخادم منذ البداية: `POST /literature/sources/search` —
 * فيُنادى. ولا نتائج مُصطنعة: ما يُعرض هو ما ردّه السجل، وإن لم يردّ شيئًا
 * قيلت «لا نتائج» **بعد** أن يعود الجواب لا قبله.
 *
 * **والمرشّح ليس مصدرًا مخزَّنًا.** يُقال ذلك صراحةً تحت النتائج: الاستيراد
 * فعلٌ مستقل يقع في المكتبة، لا أثرٌ جانبي لبحث.
 */
interface SourceCandidate {
  registry: string;
  registry_id: string;
  doi: string | null;
  title: string;
  publication_year: number | null;
  journal_name: string | null;
  authors: string[];
  retraction_status: string;
  access_state: string;
}

export default function SearchPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));
  const { literatureOnline, loading } = usePosture(locale);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SourceCandidate[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const disabled = loading || !literatureOnline;

  async function onSearch(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    // **والنتائج السابقة تُمحى قبل الطلب.** إبقاؤها تحت استعلامٍ جديد يجعل
    // الباحث يقرأ جواب سؤالٍ سابق جوابًا لسؤاله الحالي.
    setResults(null);
    try {
      setResults(
        await apiFetch<SourceCandidate[]>("/api/v1/literature/sources/search", {
          method: "POST",
          locale,
          body: JSON.stringify({ query: query.trim(), limit: 20 }),
        }),
      );
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("search.title")}</h1>
        <p>{t("search.subtitle")}</p>
      </div>

      <form className="form" style={{ maxInlineSize: "56ch" }} onSubmit={onSearch}>
        <label htmlFor="literature-query">{t("search.title")}</label>
        <input
          id="literature-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("search.placeholder")}
          disabled={disabled}
        />
        <button type="submit" disabled={disabled || busy || query.trim().length < 2}>
          {busy ? t("app.loading") : t("search.submit")}
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

      {error ? (
        <p className="error" role="alert" data-testid="search-error" style={{ marginBlockStart: 18 }}>
          {error}
        </p>
      ) : null}

      {/* ثلاث حالات مفصولة: جارٍ، ثم لا نتائج، ثم النتائج — ولا واحدة منها
          تُعرض في موضع الأخرى. و«لا نتائج» لا تُقال قبل أوّل بحث أصلًا. */}
      {busy ? (
        <p data-testid="search-loading" style={{ color: "var(--muted)", marginBlockStart: 18 }}>
          {t("app.loading")}
        </p>
      ) : results && results.length === 0 ? (
        <p data-testid="search-empty" style={{ color: "var(--muted)", marginBlockStart: 18 }}>
          {t("search.empty")}
        </p>
      ) : null}

      {results && results.length > 0 ? (
        <section aria-label={t("search.resultsLabel")} style={{ marginBlockStart: 18 }}>
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 10 }}>
            {t("search.resultsLabel")}
          </p>
          <div style={{ display: "grid", gap: 8 }}>
            {results.map((candidate) => (
              <article className="card" key={`${candidate.registry}:${candidate.registry_id}`}>
                <strong>{candidate.title}</strong>
                <div className="metric-label" style={{ marginBlockStart: 4 }} dir="ltr">
                  {[candidate.journal_name, candidate.publication_year, candidate.doi]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </div>
                {candidate.authors.length > 0 ? (
                  <div className="metric-label">{candidate.authors.join("، ")}</div>
                ) : null}
                {/* السحب حالٌ تُعلَن قبل الاستيراد لا بعده. */}
                {candidate.retraction_status !== "none" ? (
                  <p className="error" style={{ marginBlock: "6px 0" }}>
                    {t("search.retracted")}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
          <p className="provenance-note" style={{ marginBlockStart: 12 }}>
            {t("search.notStoredNote")}{" "}
            <Link href={`/${locale}/library`}>{t("nav.library")}</Link>
          </p>
        </section>
      ) : null}
    </>
  );
}
