"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import {
  saveToLibrary,
  searchReferences,
  type ProviderStatus,
  type RankReason,
  type ReferenceCandidate,
  type ReferenceSearchResponse,
} from "@/lib/discovery";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { linkSource, listProjects, type ProjectSummary } from "@/lib/workspace";

/**
 * اكتشاف المراجع.
 *
 * **ثلاث حالات لا تُطوى في واحدة**، والشاشة كلها مبنية على الفصل بينها:
 * نتيجةُ بحثٍ في فهرسٍ خارجي، ومرجعٌ مخزَّن في مكتبة الباحث، ودليلٌ يُبنى
 * عليه ادعاء. فالبطاقة هنا مرشَّح لا مرجع، و«حفظ في مكتبتي» فعلٌ يخلق
 * الثاني، و«إضافة إلى هذا المشروع» تبقيه «محفوظًا فقط» — والثالثة قرار
 * الباحث وحده بعد أن يقرأ.
 *
 * **وأربع حالات عرضٍ لا تُخلط**: قبل البحث، وأثناءه، وجوابٌ فارغ، وفشل.
 * وأخطرها الأخيرة: بحثٌ فشل يُعرض «لا نتائج» يجعل الباحث يظنّ موضوعه بكرًا
 * فيبني عليه — والشبكة وحدها كانت معطوبة. فلكلٍّ منها موضعها ونصّها.
 *
 * **والرقم يُنسب إلى قائله.** Crossref يقول ١٢٠ استشهادًا وOpenAlex يقول
 * ١٣٤ عن الورقة نفسها؛ فلا يُعرض رقمٌ واحد لا يقوله أحد.
 *
 * **ولا نسبة صلة على هذه الشاشة.** «٩٧٪ مرتبطة» رقمٌ بلا وحدة ولا مرجع،
 * يقرؤه الباحث حكمًا كميًّا على ورقةٍ لم يقرأها فيصدّقه. وما يُعرض بدلًا
 * منه أسبابٌ بلغته يستطيع التحقق من كلٍّ منها بعينه — والخادم لا يرسل
 * درجةً أصلًا، فالعقد نفسه يمنع أن تُخترع هنا نسبةٌ يومًا.
 *
 * **والاقتراح ليس تنفيذًا.** المصطلحات المقترحة تُعرض ليقبلها الباحث أو
 * يرفضها، ونصّه يبقى ظاهرًا جوارها. ومن وسّع بحثه نيابةً عنه بدّل سؤاله
 * البحثي ثم أراه نتائج سؤالٍ آخر على أنها نتائج سؤاله.
 */

type Phase = "idle" | "loading" | "ready" | "failed";
type Load = "loading" | "ready" | "failed";

interface Notice {
  kind: "ok" | "error";
  text: string;
}

const WORK_TYPES = [
  "journal-article",
  "conference-paper",
  "book",
  "book-chapter",
  "preprint",
  "thesis",
  "dataset",
  "report",
  "review",
  "other",
] as const;

/** مفتاحٌ ثابت للبطاقة — من معرّفات الفهارس لا من ترتيب العرض. */
function candidateKey(candidate: ReferenceCandidate): string {
  if (candidate.doi) return `doi:${candidate.doi}`;
  return candidate.claims.map((claim) => `${claim.provider}:${claim.provider_id}`).join("|");
}

/** سنةٌ من حقلٍ نصّي، أو `null`. النصّ غير الرقمي لا يصير سنةً بالصدفة. */
function yearOf(raw: string): number | null {
  const trimmed = raw.trim();
  if (!/^\d{4}$/.test(trimmed)) return null;
  return Number(trimmed);
}

/**
 * نصُّ سببٍ واحد: جملةٌ من الكتالوج، ثم ما يُكمّلها من بيانات الخادم.
 *
 * **والاستشهاد لا يُذكر بلا قائله**: «٢٤٠٠ في OpenAlex» جملةٌ يستطيع
 * الباحث التحقق منها في ذلك الفهرس بعينه؛ و«٢٤٠٠ استشهادًا» دعوى منصّةٍ
 * على فهرسٍ لم يقلها، ولا يعرف الباحث أين يراجعها.
 */
function reasonText(reason: RankReason, t: (path: string) => string): string {
  const head = t(`references.reasons.${reason.code}`);
  if (reason.provider !== null && reason.count !== null) {
    return `${head} ${reason.count} ${t("references.reasonIn")} ${reason.provider}`;
  }
  if (reason.year !== null) return `${head} ${reason.year}`;
  if (reason.terms.length > 0) return `${head} ${reason.terms.join("، ")}`;
  return head;
}

export default function ReferencesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [query, setQuery] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [workType, setWorkType] = useState("");
  const [openAccessOnly, setOpenAccessOnly] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [data, setData] = useState<ReferenceSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectsLoad, setProjectsLoad] = useState<Load>("loading");
  const [target, setTarget] = useState("");

  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [notices, setNotices] = useState<Record<string, Notice>>({});

  /**
   * المصطلحات المقبولة — **حالةٌ مستقلة عن نتائج البحث الجارية**.
   *
   * `accepted` ما اختاره الباحث الآن، و`appliedTerms` ما كان مطبَّقًا في
   * النتائج المعروضة. وافتراقُهما هو ما يُظهر «أعد البحث»: بلا هذا الفصل
   * تتغيّر الأسباب تحت البطاقات بنقرةٍ على مصطلح، فيقرأ الباحث تفسيرًا
   * لبحثٍ لم يُجرَ بعد.
   */
  const [accepted, setAccepted] = useState<string[]>([]);
  const [appliedTerms, setAppliedTerms] = useState<string[]>([]);

  /**
   * أبحاث الباحث تُحمَّل مرّة — **ولا حالة تُضبط داخل التأثير مباشرةً**.
   * الضبط المتزامن داخل `useEffect` خطأٌ يمنعه المدقّق، ووعدٌ مؤجّل يجعل
   * الترتيب صريحًا: ثم النتيجة، ثم الحالة.
   */
  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() =>
      listProjects(locale)
        .then((rows) => {
          if (!alive) return;
          setProjects(rows);
          setTarget(rows[0]?.id ?? "");
          setProjectsLoad("ready");
        })
        .catch(() => {
          // تعذّر التحميل يُعلَن؛ ولا يُعرض «لا أبحاث لديك» وهو غير معلوم.
          if (alive) setProjectsLoad("failed");
        }),
    );
    return () => {
      alive = false;
    };
  }, [locale]);

  /**
   * بحثٌ جاء مع الرابط — **`?q=` من الرئيسية أو من رابطٍ محفوظ**.
   *
   * الرئيسية تسأل «ماذا تريد أن تنجز؟»، فمن لصق DOI فيها وصل إلى هنا.
   * وأن يصل الباحث إلى شاشةٍ فيها معرّفه مكتوبٌ في المربّع ثم يُطلب منه
   * أن يضغط «بحث» مرّةً أخرى هو أن تُقسَم نيّةٌ واحدة على فعلين — فيُنفَّذ
   * ما قصده عند وصوله.
   *
   * **ولا حالة تُضبط في جسد التأثير مباشرةً**: `react-hooks/set-state-in-effect`
   * يمنع ذلك، والوعدُ المؤجّل هو النمط المستعمل في هذا الملف أصلًا.
   * والحارس `useRef` لا `useState` — فلا يُعيد تصييرًا ولا يدخل الاعتماديات.
   */
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current) return;
    const seed = new URLSearchParams(window.location.search).get("q")?.trim() ?? "";
    if (!seed) return;
    seeded.current = true;
    let alive = true;
    void Promise.resolve().then(() => {
      if (!alive) return;
      setQuery(seed);
      setPhase("loading");
      setError(null);
      setNotices({});
      setData(null);
      return searchReferences(locale, seed, { acceptedTerms: [] })
        .then((response) => {
          if (!alive) return;
          setData(response);
          setAppliedTerms([]);
          setPhase("ready");
        })
        .catch((err: unknown) => {
          if (!alive) return;
          // فشلُ البحث ليس «لا نتائج» — والفرق بينهما هو الفرق بين شبكةٍ
          // معطوبة وموضوعٍ بكر، وأحدهما يُبنى عليه بحثٌ كامل.
          setError(
            err instanceof AtheraApiError ? err.localized(locale) : t("references.failed"),
          );
          setPhase("failed");
        });
    });
    return () => {
      alive = false;
    };
  }, [locale, t]);

  function runSearch(terms: string[]) {
    setPhase("loading");
    setError(null);
    setNotices({});
    // النتائج السابقة تُمحى قبل الطلب: إبقاؤها تحت استعلامٍ جديد يجعل
    // الباحث يقرأ جواب سؤالٍ سابق جوابًا لسؤاله الحالي.
    setData(null);
    searchReferences(locale, query.trim(), {
      yearFrom: yearOf(yearFrom),
      yearTo: yearOf(yearTo),
      workType: workType || null,
      openAccessOnly,
      acceptedTerms: terms,
    })
      .then((response) => {
        setData(response);
        // ما طُبِّق فعلًا يُسجَّل من الطلب الذي نجح وحده: لو سُجّل قبل
        // الردّ لقالت الشاشة إن التوسيع مطبَّق وهو لم يصل إلى فهرس.
        setAppliedTerms(terms);
        setPhase("ready");
      })
      .catch((err: unknown) => {
        setError(
          err instanceof AtheraApiError ? err.localized(locale) : t("references.failed"),
        );
        setPhase("failed");
      });
  }

  function onSearch(event: React.FormEvent) {
    event.preventDefault();
    runSearch(accepted);
  }

  /** قبول مصطلحٍ أو رفضه — **ولا يُعاد البحث تلقائيًّا**.
   *
   * إعادةُ البحث عند كل نقرة تجعل الباحث يوسّع بحثه وهو يستكشف الخيارات،
   * ثم يقرأ نتائج توسيعٍ لم يقصده. فالقبول اختيارٌ، والتنفيذ نقرةٌ ثانية.
   */
  function toggleTerm(term: string) {
    setAccepted((current) =>
      current.includes(term)
        ? current.filter((one) => one !== term)
        : [...current, term],
    );
  }

  function onSave(candidate: ReferenceCandidate) {
    const key = candidateKey(candidate);
    if (!candidate.doi) return;
    setBusyKey(key);
    saveToLibrary(locale, candidate.doi)
      .then(() => {
        setNotices((current) => ({ ...current, [key]: { kind: "ok", text: t("references.savedOk") } }));
      })
      .catch((err: unknown) => {
        setNotices((current) => ({
          ...current,
          [key]: {
            kind: "error",
            text:
              err instanceof AtheraApiError
                ? err.localized(locale)
                : t("references.saveFailed"),
          },
        }));
      })
      .finally(() => setBusyKey(null));
  }

  /**
   * الحفظ ثم الربط — **والحال الابتدائية تُقرأ من ردّ الخادم لا تُفترض هنا**.
   * فلو قالت الشاشة «محفوظ فقط» من عندها لكانت تصف ما تتمنّاه لا ما وقع.
   */
  function onAdd(candidate: ReferenceCandidate) {
    const key = candidateKey(candidate);
    if (!candidate.doi || !target) return;
    setBusyKey(key);
    saveToLibrary(locale, candidate.doi)
      .then((stored) => linkSource(locale, target, stored.id))
      .then((link) => {
        setNotices((current) => ({
          ...current,
          [key]: {
            kind: "ok",
            text:
              link.use_state === "saved_only"
                ? t("references.addedOk")
                : `${t("references.addedState")} ${link.use_state}`,
          },
        }));
      })
      .catch((err: unknown) => {
        setNotices((current) => ({
          ...current,
          [key]: {
            kind: "error",
            text:
              err instanceof AtheraApiError ? err.localized(locale) : t("references.addFailed"),
          },
        }));
      })
      .finally(() => setBusyKey(null));
  }

  const providersDown: ProviderStatus[] = (data?.providers ?? []).filter((one) => !one.ok);
  const canSubmit = query.trim().length >= 2 && phase !== "loading";

  const understanding = data?.query_understanding ?? null;
  const suggestions = understanding?.suggestions ?? [];
  // ما قبله الباحث ولم يُطبَّق بعد. المقارنة على المجموعة لا على الطول:
  // إزالةُ مصطلحٍ وإضافةُ آخر تُبقي العدد ويتبدّل البحث.
  const pending =
    accepted.length !== appliedTerms.length ||
    accepted.some((term) => !appliedTerms.includes(term));
  // نصّان يُعرضان معًا حين يختلفان وحده — وتساويهما هو الحال الطبيعية.
  const rewritten =
    understanding !== null && understanding.sent.trim() !== understanding.raw.trim();

  return (
    <>
      <div className="page-head">
        <h1>{t("references.title")}</h1>
        <p>{t("references.subtitle")}</p>
      </div>

      <form className="form" style={{ maxInlineSize: "62ch" }} onSubmit={onSearch}>
        <label htmlFor="reference-query">{t("references.searchLabel")}</label>
        <input
          id="reference-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("references.placeholder")}
        />

        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="nav-label" style={{ paddingInline: 0 }}>
            {t("references.filtersLabel")}
          </legend>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}>
            <span style={{ display: "grid", gap: 4 }}>
              <label htmlFor="reference-year-from">{t("references.yearFrom")}</label>
              <input
                id="reference-year-from"
                inputMode="numeric"
                value={yearFrom}
                onChange={(event) => setYearFrom(event.target.value)}
                style={{ inlineSize: "10ch" }}
              />
            </span>
            <span style={{ display: "grid", gap: 4 }}>
              <label htmlFor="reference-year-to">{t("references.yearTo")}</label>
              <input
                id="reference-year-to"
                inputMode="numeric"
                value={yearTo}
                onChange={(event) => setYearTo(event.target.value)}
                style={{ inlineSize: "10ch" }}
              />
            </span>
            <span style={{ display: "grid", gap: 4 }}>
              <label htmlFor="reference-type">{t("references.workType")}</label>
              <select
                id="reference-type"
                value={workType}
                onChange={(event) => setWorkType(event.target.value)}
              >
                <option value="">{t("references.workTypeAny")}</option>
                {WORK_TYPES.map((kind) => (
                  <option key={kind} value={kind}>
                    {t(`references.types.${kind}`)}
                  </option>
                ))}
              </select>
            </span>
            <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input
                id="reference-open-access"
                type="checkbox"
                checked={openAccessOnly}
                onChange={(event) => setOpenAccessOnly(event.target.checked)}
              />
              <label htmlFor="reference-open-access">{t("references.openAccessOnly")}</label>
            </span>
          </div>
          {/* «المفتوح فقط» يُقصي المجهول أيضًا — يُقال قبل أن يُستعمل. */}
          <p className="provenance-note" style={{ marginBlockStart: 6 }}>
            {t("references.openAccessNote")}
          </p>
        </fieldset>

        <button type="submit" disabled={!canSubmit}>
          {phase === "loading" ? t("app.loading") : t("references.submit")}
        </button>
      </form>

      {/* الرابط الممنوع جمعه: يُعلَن أنه رابط وصولٍ فقط وغير متحقَّق. */}
      {data?.external_link ? (
        <div className="gate" style={{ marginBlockStart: 18 }} data-testid="references-external-link">
          <span aria-hidden="true">🔗</span>
          <span>
            <strong>{t("references.externalLinkTitle")}</strong>{" "}
            <span dir="ltr">{data.external_link.url}</span>{" "}
            <em>({t("references.externalLinkUnverified")})</em>
            <br />
            {t("references.externalLinkBody")}
          </span>
        </div>
      ) : null}

      {phase === "failed" ? (
        <p className="error" role="alert" data-testid="references-error" style={{ marginBlockStart: 18 }}>
          {error}
        </p>
      ) : null}

      {phase === "ready" && data && !data.providers_enabled ? (
        <div className="gate" style={{ marginBlockStart: 18 }} data-testid="references-disabled">
          <span aria-hidden="true">⏻</span>
          <span>
            <strong>{t("references.disabledTitle")}</strong> {t("references.disabledBody")}{" "}
            <Link href={`/${locale}/library`}>{t("nav.library")}</Link>
          </span>
        </div>
      ) : null}

      {/* ما فُهم من السؤال، ونصّه كما كُتب. يُعرضان معًا فلا يقع تبديلٌ خفيّ. */}
      {phase === "ready" && understanding ? (
        <section
          aria-label={t("references.understandingLabel")}
          style={{ marginBlockStart: 18 }}
          data-testid="references-understanding"
        >
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 6 }}>
            {t("references.understandingLabel")}
          </p>
          <p className="metric-label" style={{ marginBlock: 0 }}>
            {t("references.queryLabel")}: <span dir="auto">{understanding.raw}</span>
          </p>
          {rewritten ? (
            <p className="metric-label" style={{ marginBlock: 0 }} data-testid="references-query-sent">
              {t("references.querySentLabel")}: <span dir="auto">{understanding.sent}</span>
            </p>
          ) : (
            <p className="provenance-note" style={{ marginBlock: 0 }}>
              {t("references.queryUnchanged")}
            </p>
          )}
          <ul
            style={{ display: "flex", gap: 8, flexWrap: "wrap", listStyle: "none", padding: 0, marginBlockStart: 6 }}
          >
            {understanding.doi ? (
              <li className="chip">
                {t("references.understandingDoi")}: <span dir="ltr">{understanding.doi}</span>
              </li>
            ) : null}
            {understanding.authors.map((name) => (
              <li className="chip" key={`author-${name}`}>
                {t("references.understandingAuthors")}: {name}
              </li>
            ))}
            {understanding.year !== null ? (
              <li className="chip">
                {t("references.understandingYear")}: {understanding.year}
              </li>
            ) : null}
            {understanding.phrase ? (
              <li className="chip">
                {t("references.understandingPhrase")}: {understanding.phrase}
              </li>
            ) : null}
            {understanding.keywords.length > 0 ? (
              <li className="chip">
                {t("references.understandingKeywords")}: {understanding.keywords.join("، ")}
              </li>
            ) : null}
          </ul>
        </section>
      ) : null}

      {/* مصطلحاتٌ مقترحة: تُعرض ولا تُطبَّق حتى يقبلها الباحث ويعيد البحث. */}
      {phase === "ready" && suggestions.length > 0 ? (
        <section
          aria-label={t("references.suggestionsLabel")}
          style={{ marginBlockStart: 18 }}
          data-testid="references-suggestions"
        >
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 6 }}>
            {t("references.suggestionsLabel")}
          </p>
          <p className="provenance-note" style={{ marginBlockStart: 0 }}>
            {t("references.suggestionsNote")}
          </p>
          <ul style={{ display: "flex", gap: 8, flexWrap: "wrap", listStyle: "none", padding: 0 }}>
            {suggestions.map((one) => {
              const on = accepted.includes(one.term);
              return (
                <li key={one.term}>
                  {/* كل زرٍّ مكرَّر يسمّي هدفه: «أضف إلى بحثي: الذكاء الاصطناعي». */}
                  <button
                    type="button"
                    className="chip chip-stage"
                    aria-pressed={on}
                    aria-label={`${on ? t("references.suggestionRemove") : t("references.suggestionAccept")}: ${one.term}`}
                    onClick={() => toggleTerm(one.term)}
                  >
                    {one.term}
                    {" · "}
                    {one.kind === "acronym"
                      ? t("references.suggestionKindAcronym")
                      : t("references.suggestionKindTranslation")}
                    {on ? ` · ${t("references.suggestionAccepted")}` : ""}
                  </button>
                </li>
              );
            })}
          </ul>
          {pending ? (
            <p role="status" data-testid="references-suggestions-pending">
              {t("references.acceptedPending")}{" "}
              <button
                type="button"
                className="chip chip-stage"
                disabled={!canSubmit}
                onClick={() => runSearch(accepted)}
              >
                {t("references.suggestionRerun")}
              </button>
            </p>
          ) : null}
        </section>
      ) : null}

      {/* حال كل فهرس — الفشل يُعلَن باسم صاحبه، ولا يُقرأ رفًّا فارغًا. */}
      {phase === "ready" && data && data.providers.length > 0 ? (
        <section aria-label={t("references.providersLabel")} style={{ marginBlockStart: 18 }}>
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 6 }}>
            {t("references.providersLabel")}
          </p>
          <ul style={{ display: "flex", gap: 10, flexWrap: "wrap", listStyle: "none", padding: 0 }}>
            {data.providers.map((one) => (
              <li key={one.provider} className="chip">
                <span dir="ltr">{one.provider}</span>{" "}
                {one.ok ? t("references.providerOk") : t("references.providerDown")}
              </li>
            ))}
          </ul>
          {data.all_providers_failed ? (
            <p className="error" role="alert" data-testid="references-all-down">
              {t("references.allDown")}
            </p>
          ) : providersDown.length > 0 ? (
            <p className="error" role="status" data-testid="references-partial">
              {t("references.partialWarning")}
            </p>
          ) : null}
        </section>
      ) : null}

      {phase === "loading" ? (
        <p data-testid="references-loading" style={{ color: "var(--muted)", marginBlockStart: 18 }}>
          {t("references.loading")}
        </p>
      ) : null}

      {/* «لا نتائج» لا تُقال إلا حين أجاب فهرسٌ واحد على الأقل ولم يجد شيئًا. */}
      {phase === "ready" &&
      data &&
      data.providers_enabled &&
      !data.all_providers_failed &&
      data.candidates.length === 0 ? (
        <p data-testid="references-empty" style={{ color: "var(--muted)", marginBlockStart: 18 }}>
          {t("references.empty")}
        </p>
      ) : null}

      {phase === "ready" && data && data.candidates.length > 0 ? (
        <section aria-label={t("references.resultsLabel")} style={{ marginBlockStart: 18 }}>
          <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 4 }}>
            {t("references.resultsLabel")}
          </p>
          {/* الباحث يفترض الترتيب الزمني في شاشات البحث، فيقرأ الأولى
              «الأحدث». فيُقال بأيّ شيء رُتِّبت، ويُقال لماذا لا نسبة. */}
          <p className="metric-label" style={{ marginBlock: 0 }} data-testid="references-ordering">
            {t("references.orderedByLabel")}
          </p>
          <p className="provenance-note" style={{ marginBlockStart: 2, marginBlockEnd: 10 }}>
            {t("references.noPercentNote")}
          </p>

          {/* البحث المستهدف يُختار مرّة، فلا يُسأل عنه في كل بطاقة. */}
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBlockEnd: 12 }}>
            {/* الوسم لا يُكتب إلا وله حقلٌ قائم: وسمٌ يشير إلى عنصرٍ غير
                موجود يقرؤه القارئ الصوتي فراغًا، وهو أسوأ من غيابه. */}
            {projectsLoad === "loading" ? (
              <span style={{ color: "var(--muted)" }}>{t("references.projectsLoading")}</span>
            ) : projectsLoad === "failed" ? (
              <span className="error" role="status">
                {t("references.projectsFailed")}
              </span>
            ) : projects.length === 0 ? (
              <span style={{ color: "var(--muted)" }}>
                {t("references.noProjects")}{" "}
                <Link href={`/${locale}/portfolio`}>{t("nav.portfolio")}</Link>
              </span>
            ) : (
              <>
                <label htmlFor="reference-project">{t("references.projectLabel")}</label>
                <select
                  id="reference-project"
                  value={target}
                  onChange={(event) => setTarget(event.target.value)}
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.title_ar}
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>

          <div style={{ display: "grid", gap: 10 }}>
            {data.candidates.map((candidate) => {
              const key = candidateKey(candidate);
              const notice = notices[key];
              const busy = busyKey === key;
              return (
                <article className="card" key={key} data-testid="reference-candidate">
                  {/* **السحب يُقرأ قبل العنوان، لا بعده.**
                      الباحث يمسح العناوين ولا يقرأ كل بطاقة إلى آخرها؛
                      فتحذيرٌ أسفل البطاقة يُرى بعد أن يكون قد قرّر. وهذه
                      الحال تُقرأ من بيانات الفهرس البنيوية (`update-to`
                      و`is_retracted`) لا من لفظةٍ في العنوان. */}
                  {candidate.retraction_status === "retracted" ? (
                    <p
                      className="error"
                      role="alert"
                      data-testid="reference-retracted"
                      style={{ marginBlock: "0 8px", fontWeight: 600 }}
                    >
                      ⛔ {t("references.retracted")}
                    </p>
                  ) : null}

                  <strong>{candidate.title}</strong>

                  <div className="metric-label" style={{ marginBlockStart: 4 }}>
                    {candidate.authors.length > 0
                      ? candidate.authors.join("، ")
                      : t("references.authorsUnknown")}
                  </div>
                  <div className="metric-label" dir="ltr">
                    {[
                      candidate.venue ?? t("references.venueUnknown"),
                      candidate.year ?? t("references.yearUnknown"),
                      candidate.doi ?? t("references.doiUnknown"),
                    ].join(" · ")}
                  </div>

                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 6 }}>
                    {candidate.work_type ? (
                      <span className="chip">{t(`references.types.${candidate.work_type}`)}</span>
                    ) : null}
                    <span className="chip">
                      {candidate.open_access === true
                        ? t("references.openAccess")
                        : t("references.accessUnknown")}
                    </span>
                    <span className="chip">
                      {t("references.matchBasisLabel")}:{" "}
                      {t(`references.matchBasis.${candidate.match_basis}`)}
                    </span>
                  </div>

                  {/* لماذا وقع هنا. أسبابٌ يتحقق منها بعينه — **ولا نسبة**:
                      الخادم لا يرسل درجة، فلا تستطيع الشاشة اختراع واحدة. */}
                  {candidate.reasons.length > 0 ? (
                    <ul
                      aria-label={`${t("references.reasonsLabel")}: ${candidate.title}`}
                      data-testid="reference-reasons"
                      style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "grid", gap: 2 }}
                    >
                      {candidate.reasons.map((reason) => (
                        <li
                          key={reason.code}
                          className={reason.kind === "caution" ? "error" : "metric-label"}
                          style={{ marginBlock: 0 }}
                        >
                          {reason.kind === "caution" ? "⚠ " : "· "}
                          {reasonText(reason, t)}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {/* من قال ماذا: كل فهرسٍ بسطره، وعدّاده باسمه. */}
                  <details style={{ marginBlockStart: 8 }}>
                    <summary className="nav-label" style={{ paddingInline: 0 }}>
                      {t("references.provenanceLabel")}
                    </summary>
                    <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0" }}>
                      {candidate.claims.map((claim) => (
                        <li key={`${claim.provider}:${claim.provider_id}`} className="metric-label">
                          <span dir="ltr">{claim.provider}</span> —{" "}
                          <span dir="ltr">{claim.provider_id}</span>
                          {claim.citation_count !== null ? (
                            <>
                              {" · "}
                              {t("references.citationsLabel")}: {claim.citation_count}
                            </>
                          ) : null}
                          {claim.type ? (
                            <>
                              {" · "}
                              <span dir="ltr">{claim.type}</span>
                            </>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                    <p className="provenance-note">{t("references.citationsNote")}</p>
                    {candidate.abstract ? (
                      <p style={{ marginBlockEnd: 0 }}>
                        <span className="nav-label" style={{ paddingInline: 0 }}>
                          {t("references.abstractLabel")}
                        </span>
                        <br />
                        {candidate.abstract}
                      </p>
                    ) : null}
                    {candidate.url ? (
                      <p style={{ marginBlockEnd: 0 }}>
                        <a href={candidate.url} target="_blank" rel="noreferrer noopener">
                          {t("references.openExternal")}
                        </a>
                      </p>
                    ) : null}
                  </details>

                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 10 }}>
                    <button
                      type="button"
                      className="chip chip-stage"
                      disabled={busy || !candidate.can_be_saved}
                      aria-label={`${t("references.save")}: ${candidate.title}`}
                      onClick={() => onSave(candidate)}
                    >
                      {t("references.save")}
                    </button>
                    <button
                      type="button"
                      className="chip chip-stage"
                      disabled={busy || !candidate.can_be_saved || !target}
                      aria-label={`${t("references.addToProject")}: ${candidate.title}`}
                      onClick={() => onAdd(candidate)}
                    >
                      {t("references.addToProject")}
                    </button>
                  </div>

                  {/* مرشَّحٌ بلا DOI: يُقال لماذا الزرّان معطّلان — ولا يُصنع له معرّف. */}
                  {!candidate.can_be_saved ? (
                    <p className="provenance-note">{t("references.cannotSave")}</p>
                  ) : null}

                  {notice ? (
                    <p
                      className={notice.kind === "error" ? "error" : "provenance-note"}
                      role="status"
                    >
                      {notice.text}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>

          <p className="provenance-note" style={{ marginBlockStart: 12 }}>
            {t("references.notStored")} {t("references.savedOnlyNote")}{" "}
            <Link href={`/${locale}/library`}>{t("nav.library")}</Link>
          </p>
        </section>
      ) : null}
    </>
  );
}
