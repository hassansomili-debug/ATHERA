"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  decideSource,
  decideSources,
  describe,
  loadScreening,
  type ScreeningCard,
  type ScreeningQuery,
  type ScreeningView,
} from "@/lib/screening";

/**
 * فرز الأدبيات — **ثلاثة معانٍ لا تُطوى في واحد**.
 *
 * نتيجةُ بحثٍ في فهرسٍ خارجي ليست مرجعًا مخزَّنًا، والمرجعُ المخزَّن ليس
 * دليلًا مُدرَجًا. وهذه الشاشة تخصّ الحدّ الثالث وحده: أن يقول الباحث في
 * كل دراسةٍ حفظها ماذا يفعل بها. و«مُدرَجة» تعني أنه اختارها للأدلة — **لا
 * أن ادعاءاتها صحيحة**، ولا أن المنصّة تحقّقت منها.
 *
 * **والاستبعاد لا يقع بلا سبب.** حكمٌ بلا سببٍ مسجَّل لا يُراجَع بعد شهر
 * ولا يُكتب في قسم المنهجية: يقرأ الباحث اسم الدراسة ولا يذكر لماذا تركها،
 * فيعيد قراءتها — أو يخترع لها سببًا من ذاكرته الآن، وهو أسوأ. فالضغط على
 * «استبعاد» يفتح نموذج السبب ولا يُنفّذ شيئًا بعد.
 *
 * **والبحث الجادّ فيه ألفُ مرجعٍ لا عشرون.** فلا تُحمَّل كلُّها: الصفحة
 * تُطلب صفحةً، والتصفية تقع في الخادم **قبل** القطع، والأعداد تأتي منه
 * كذلك. وتصفيةٌ تقع هنا تجعل الشاشة تقول «ثلاث دراسات» وهي ثلاثمائة.
 *
 * **والقرار الجماعي يقع كلُّه أو لا يقع منه شيء.** تسعةَ عشرَ قرارًا وقعت
 * وواحدٌ فشل أسوأ من عشرين فشلت: الباحث يعيد الأمر فيقع بعضه مرّتين، ولا
 * يعرف أيُّها وقع. فالطلب واحدٌ إلى الخادم، لا حلقةٌ من عشرين طلبًا.
 *
 * **وأربع حالات عرضٍ لا تُخلط**: قبل الجواب، وأثناءه، وجوابٌ فارغ، وفشل.
 * وأخطرها الأخيرة: طلبٌ فشل يُعرض «لا مراجع» يجعل الباحث يظنّ بحثه خاليًا
 * فيذهب يستورد ما هو عنده — والشبكة وحدها كانت معطوبة.
 */

type Load = "loading" | "ready" | "failed";

/** التبويبات — و«المراجع» كلُّها، لا حالٌ رابعة. */
const TABS = ["all", "saved_only", "included", "excluded"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABEL: Record<Tab, string> = {
  all: "screening.tabAll",
  saved_only: "screening.tabQueue",
  included: "screening.tabIncluded",
  excluded: "screening.tabExcluded",
};

const USE_LABEL: Record<ScreeningCard["use_state"], string> = {
  included: "screening.actionInclude",
  saved_only: "screening.actionSaveOnly",
  excluded: "screening.actionExclude",
};

const SCOPE_LABEL: Record<ScreeningCard["reading_scope"], string> = {
  metadata_only: "screening.scopeMetadata",
  abstract_only: "screening.scopeAbstract",
  full_text: "screening.scopeFullText",
};

/** الرمز الذي يلزمه نصّ — والباقي نصُّه اختياري. */
const FREE_TEXT_REASON = "other";

const PAGE_SIZE = 25;

/**
 * مرشّحٌ ثلاثيّ: بلا تحديد، أو نعم، أو لا.
 *
 * **و«بلا تحديد» ليست «لا».** ولو طُويتا في قيمةٍ منطقية واحدة لاختفت من
 * الشاشة دراساتٌ لم يستبعدها أحد — والباحث لا يرى شرطًا لم يضعه.
 */
type Tri = "" | "yes" | "no";

/** المرشّحات الثلاثية في سجلٍّ واحد متجانس — فيُكتب المفتاح مرّة لا أربعًا. */
type TriKey = "openAccess" | "hasAbstract" | "hasFullText" | "duplicate";

interface Filters {
  yearFrom: string;
  yearTo: string;
  registry: string;
  documentType: string;
  tri: Record<TriKey, Tri>;
}

const NO_FILTERS: Filters = {
  yearFrom: "",
  yearTo: "",
  registry: "",
  documentType: "",
  tri: { openAccess: "", hasAbstract: "", hasFullText: "", duplicate: "" },
};

/**
 * نسخةٌ من المرشّحات الثلاثية بمفتاحٍ واحد مُبدَّل.
 *
 * ومفتاحٌ محسوب داخل حرفيّةِ كائن يجعل النوع فضفاضًا، فيمرّ خطأُ إملاءٍ في
 * اسم المفتاح بلا أن يقوله المدقّق — والمرشّح يبقى معطَّلًا ولا يُعرف لماذا.
 */
function withTri(
  current: Record<TriKey, Tri>,
  key: TriKey,
  value: Tri,
): Record<TriKey, Tri> {
  const next = { ...current };
  next[key] = value;
  return next;
}

const TRI_FILTERS: readonly (readonly [string, string, TriKey])[] = [
  ["filter-open-access", "screening.filterOpenAccess", "openAccess"],
  ["filter-has-abstract", "screening.filterHasAbstract", "hasAbstract"],
  ["filter-has-full-text", "screening.filterHasFullText", "hasFullText"],
  ["filter-duplicate", "screening.filterDuplicate", "duplicate"],
];

/** استبعادٌ ينتظر سببه — لدراسةٍ واحدة أو لمجموعةٍ مختارة. */
interface Pending {
  cards: ScreeningCard[];
  code: string;
  note: string;
}

export default function ScreeningPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [tab, setTab] = useState<Tab>("saved_only");
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [data, setData] = useState<ScreeningView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  /**
   * الاستعلام كما يُرسَل — **وما لم يُختَر لا يُرسَل**.
   *
   * ومرشّحٌ يُرسَل فارغًا ليس حيادًا: الخادم يقرؤه شرطًا فتختفي دراساتٌ لم
   * يستبعدها أحد.
   */
  const query = useMemo<ScreeningQuery>(() => {
    const tri = (value: Tri) => (value === "" ? undefined : value === "yes");
    const year = (value: string) => {
      const parsed = Number.parseInt(value, 10);
      return Number.isFinite(parsed) ? parsed : undefined;
    };
    return {
      use_state: tab === "all" ? undefined : tab,
      page,
      page_size: PAGE_SIZE,
      year_from: year(filters.yearFrom),
      year_to: year(filters.yearTo),
      registry: filters.registry || undefined,
      document_type: filters.documentType || undefined,
      open_access: tri(filters.tri.openAccess),
      has_abstract: tri(filters.tri.hasAbstract),
      has_full_text: tri(filters.tri.hasFullText),
      possible_duplicate: tri(filters.tri.duplicate),
    };
  }, [tab, page, filters]);

  /**
   * **لا تُضبط حالةٌ داخل التأثير مباشرةً** — قاعدةٌ يفرضها المدقّق خطأً لا
   * تحذيرًا. والوعد المؤجّل يجعل الترتيب صريحًا: ثم الجواب، ثم الحالة.
   */
  const refresh = useCallback(
    (which: ScreeningQuery) => {
      setLoad("loading");
      setError(null);
      return loadScreening(locale, projectId, which)
        .then((view) => {
          setData(view);
          setLoad("ready");
        })
        .catch((err: unknown) => {
          // الفشل يُعلَن فشلًا، ولا يُعرض قائمةً فارغة: «لا مراجع» دعوى عن
          // حال البحث لم تُفحص، والباحث يقرؤها حكمًا.
          setError(say(err));
          setLoad("failed");
        });
    },
    [locale, projectId, say],
  );

  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh(query);
    });
    return () => {
      alive = false;
    };
  }, [refresh, query]);

  const cards = data?.cards ?? [];
  const chosenCards = cards.filter((card) => chosen.includes(card.source_id));

  const reload = () => refresh(query);

  /** «إدراج» و«حفظ فقط» يقعان مباشرة؛ و«استبعاد» يفتح سببه أولًا. */
  const decide = (card: ScreeningCard, next: ScreeningCard["use_state"]) => {
    if (next === "excluded") {
      setPending({ cards: [card], code: "", note: "" });
      return;
    }
    setBusy(card.source_id);
    setError(null);
    setNotice(null);
    void decideSource(locale, projectId, card.source_id, { use_state: next })
      .then(() => reload())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /**
   * قرارٌ على المختار — **طلبٌ واحد إلى الخادم لا حلقة**.
   *
   * والخادم يفحص المجموعة كلَّها قبل أن يكتب حرفًا، فإن تعذّر واحدٌ لم يقع
   * منها شيء. وحلقةٌ هنا كانت ستترك بعضها واقعًا وبعضها لا، ولا يعرف
   * الباحث أيُّها.
   */
  const decideChosen = (next: ScreeningCard["use_state"]) => {
    if (chosenCards.length === 0) return;
    if (next === "excluded") {
      setPending({ cards: chosenCards, code: "", note: "" });
      return;
    }
    setBusy("batch");
    setError(null);
    setNotice(null);
    void decideSources(locale, projectId, chosenCards.map((card) => card.source_id), {
      use_state: next,
    })
      .then(() => {
        setChosen([]);
        setNotice(t("screening.batchApplied"));
        return reload();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const confirmExclusion = () => {
    if (!pending || !reasonIsComplete(pending)) return;
    const { cards: targets, code, note } = pending;
    setBusy("batch");
    setError(null);
    setNotice(null);
    void decideSources(locale, projectId, targets.map((card) => card.source_id), {
      use_state: "excluded",
      reason_code: code,
      reason_ar: note.trim() ? note.trim() : undefined,
    })
      .then(() => {
        setPending(null);
        setChosen([]);
        setNotice(t("screening.batchApplied"));
        return reload();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /** تغييرُ مرشّحٍ يعيد إلى الصفحة الأولى: صفحةٌ سابعة من نتيجةٍ من ثلاث فارغة. */
  const changeFilter = (patch: Partial<Filters>) => {
    setFilters({ ...filters, ...patch });
    setPage(1);
    setChosen([]);
  };

  const changeTab = (next: Tab) => {
    setTab(next);
    setPage(1);
    setChosen([]);
  };

  const facets = data?.facets;

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("nav.portfolio")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("screening.title")}</h1>
      <p className="metric-label">{t("screening.meaningNote")}</p>

      <nav aria-label={t("screening.tabsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          {TABS.map((key) => (
            <li key={key}>
              <button
                type="button"
                aria-pressed={tab === key}
                className={tab === key ? "chip chip-stage" : "chip chip-muted"}
                onClick={() => changeTab(key)}
              >
                {t(TAB_LABEL[key])}
                {data ? ` · ${countOf(data, key)}` : ""}
              </button>
            </li>
          ))}
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/matrix`}>
              {t("screening.matrixLink")}
            </Link>
          </li>
        </ul>
      </nav>

      {/* **التصفية تقع في الخادم قبل تقسيم الصفحات.** ولو وقعت هنا لعرضت
          الصفحة ثلاثة من خمسةٍ وعشرين جُلبت، وقالت «ثلاث دراسات» وهي
          ثلاثمائة. والخيارات من مراجع هذا البحث وحده: قائمةٌ لا يقابل
          أكثرَها شيء تُعلّم الباحث ألّا يجرّب. */}
      <section aria-label={t("screening.filtersLabel")} className="card">
        <strong>{t("screening.filtersTitle")}</strong>
        <p className="metric-label">{t("screening.filtersNote")}</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBlockStart: 8 }}>
          <span>
            <label htmlFor="filter-year-from" style={{ display: "block" }}>
              {t("screening.filterYearFrom")}
            </label>
            <input
              id="filter-year-from"
              inputMode="numeric"
              size={6}
              value={filters.yearFrom}
              onChange={(event) => changeFilter({ yearFrom: event.target.value })}
            />
          </span>
          <span>
            <label htmlFor="filter-year-to" style={{ display: "block" }}>
              {t("screening.filterYearTo")}
            </label>
            <input
              id="filter-year-to"
              inputMode="numeric"
              size={6}
              value={filters.yearTo}
              onChange={(event) => changeFilter({ yearTo: event.target.value })}
            />
          </span>
          <span>
            <label htmlFor="filter-registry" style={{ display: "block" }}>
              {t("screening.filterRegistry")}
            </label>
            <select
              id="filter-registry"
              value={filters.registry}
              onChange={(event) => changeFilter({ registry: event.target.value })}
            >
              <option value="">{t("screening.filterAny")}</option>
              {(facets?.registries ?? []).map((name) => (
                <option key={name} value={name}>
                  {t(`screening.origin_${name}`)}
                </option>
              ))}
            </select>
          </span>
          <span>
            <label htmlFor="filter-doc-type" style={{ display: "block" }}>
              {t("screening.filterDocumentType")}
            </label>
            <select
              id="filter-doc-type"
              value={filters.documentType}
              onChange={(event) => changeFilter({ documentType: event.target.value })}
            >
              <option value="">{t("screening.filterAny")}</option>
              {(facets?.document_types ?? []).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </span>
          {TRI_FILTERS.map(([id, label, key]) => (
            <span key={id}>
              <label htmlFor={id} style={{ display: "block" }}>
                {t(label)}
              </label>
              <select
                id={id}
                value={filters.tri[key]}
                onChange={(event) =>
                  changeFilter({
                    tri: withTri(filters.tri, key, event.target.value as Tri),
                  })
                }
              >
                <option value="">{t("screening.filterAny")}</option>
                <option value="yes">{t("common.yes")}</option>
                <option value="no">{t("common.no")}</option>
              </select>
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 8 }}>
          <button
            type="button"
            className="chip chip-muted"
            onClick={() => changeFilter(NO_FILTERS)}
          >
            {t("screening.filterClear")}
          </button>
          {data ? (
            <span className="metric-label">
              {t("screening.resultsLabel")}: {data.total}
              {data.duplicates > 0
                ? ` · ${data.duplicates} ${t("screening.duplicateCount")}`
                : ""}
            </span>
          ) : null}
        </div>
      </section>

      {/* الفشل يُعلَن ومعه طريقُ الخروج منه — رسالةٌ بلا إعادةِ محاولة طريقٌ مسدود. */}
      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void reload()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}

      {load === "loading" ? (
        <p data-testid="screening-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="screening-failed" style={{ color: "var(--muted)" }}>
          {t("screening.loadFailedNote")}
        </p>
      ) : cards.length === 0 ? (
        <p data-testid="screening-empty" style={{ color: "var(--muted)" }}>
          {t(tab === "saved_only" ? "screening.queueEmpty" : "screening.emptyForTab")}
        </p>
      ) : (
        <>
          {/* **القرار الجماعي يقع كلُّه أو لا يقع منه شيء** — والشاشة تقول
              ذلك قبل الضغط لا بعده. */}
          <section aria-label={t("screening.batchTitle")} className="card">
            <strong>{t("screening.batchTitle")}</strong>
            <p className="metric-label">{t("screening.batchNote")}</p>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
              <button
                type="button"
                className="chip chip-muted"
                onClick={() => setChosen(cards.map((card) => card.source_id))}
              >
                {t("screening.selectAll")}
              </button>
              <button
                type="button"
                className="chip chip-muted"
                disabled={chosen.length === 0}
                onClick={() => setChosen([])}
              >
                {t("screening.clearSelection")}
              </button>
              <span className="metric-label">
                {chosenCards.length > 0
                  ? `${chosenCards.length} ${t("screening.selectedCount")}`
                  : t("screening.nothingSelected")}
              </span>
              {(["included", "saved_only", "excluded"] as const).map((next) => (
                <button
                  key={next}
                  type="button"
                  className="chip chip-stage"
                  /* الاسم يسمّي هدفه: «إدراج» بجانب «إدراج» في الصفحة نفسها
                     لا يُميَّز بالسمع، فيُلحق به أنه للمختار. */
                  aria-label={`${t(USE_LABEL[next])}: ${t("screening.batchTitle")}`}
                  disabled={chosenCards.length === 0 || busy !== null}
                  onClick={() => decideChosen(next)}
                >
                  {t(USE_LABEL[next])}
                </button>
              ))}
            </div>
          </section>

          <div style={{ display: "grid", gap: 10 }}>
            {cards.map((card) => (
              <article className="card" key={card.source_id}>
                <label style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                  <input
                    type="checkbox"
                    checked={chosen.includes(card.source_id)}
                    aria-label={`${t("screening.selectLabel")}: ${describe(card)}`}
                    onChange={(event) =>
                      setChosen(
                        event.target.checked
                          ? [...chosen, card.source_id]
                          : chosen.filter((id) => id !== card.source_id),
                      )
                    }
                  />
                  <strong>{card.title}</strong>
                </label>

                {card.authors.length > 0 ? (
                  <div className="metric-label" style={{ marginBlockStart: 4 }}>
                    {card.authors.join(" · ")}
                  </div>
                ) : (
                  <div className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("screening.authorsUnknown")}
                  </div>
                )}

                <div className="metric-label" style={{ marginBlockStart: 4 }}>
                  {[
                    card.publication_year ? String(card.publication_year) : t("screening.yearUnknown"),
                    card.venue ?? t("screening.venueUnknown"),
                  ].join(" · ")}
                </div>

                {/* **المعرّف يُعرض متحقَّقًا أو لا يُعرض.** معرّفٌ لم يُحلّ في
                    فهرسٍ معروضًا بجانب دراسةٍ يُقرأ إثباتًا فيُنسخ في قائمة
                    المراجع بلا فحص. وغيابه يُقال صراحةً ولا يُترك فراغًا. */}
                {card.doi ? (
                  <div className="metric-label" style={{ marginBlockStart: 4 }} dir="ltr">
                    {card.doi}
                  </div>
                ) : (
                  <div className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("screening.doiUnverified")}
                  </div>
                )}

                <div className="metric-label" style={{ marginBlockStart: 4 }}>
                  {t("screening.originLabel")}:{" "}
                  {card.registry ? t(`screening.origin_${card.registry}`) : t("screening.originUnknown")}
                  {" · "}
                  {t(SCOPE_LABEL[card.reading_scope])}
                  {card.document_type ? (
                    <>
                      {" · "}
                      {t("screening.documentTypeLabel")}: {card.document_type}
                    </>
                  ) : null}
                </div>

                {/* **دعوى الفهرس تُقال دعوى.** «مفتوح الوصول» حالُ حقوقٍ
                    يعلنها فهرس، وليست نصًّا في يد الباحث — ومن خلط بينهما
                    ادّعى قراءةً لم تقع. */}
                {card.index_says_open_access && card.reading_scope !== "full_text" ? (
                  <p className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("screening.openAccessClaim")}
                  </p>
                ) : null}

                {card.possible_duplicate ? (
                  <p className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("screening.duplicateHint")}
                  </p>
                ) : null}

                {/* فهرسان أرسلا ملخّصين مختلفين — يُقال ولا يُحسم بغلبة أحدهما. */}
                {card.abstracts_disagree ? (
                  <p className="error" style={{ marginBlockStart: 4 }}>
                    {t("screening.abstractsDisagree")}
                  </p>
                ) : null}

                {card.retraction_status === "retracted" ? (
                  <p className="error" style={{ marginBlockStart: 6 }}>
                    {t("screening.retracted")}
                  </p>
                ) : null}

                <div className="metric-label" style={{ marginBlockStart: 6 }}>
                  {t("screening.currentState")}: {t(USE_LABEL[card.use_state])}
                  {card.use_state === "excluded" && card.exclusion_reason_code ? (
                    <> — {t(`screening.reason_${card.exclusion_reason_code}`)}</>
                  ) : null}
                </div>
                {card.use_state === "excluded" && card.reason_ar ? (
                  <p style={{ marginBlock: 4 }}>{card.reason_ar}</p>
                ) : null}

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
                  {(["included", "saved_only", "excluded"] as const).map((next) => (
                    <button
                      key={next}
                      type="button"
                      /* **الاسم يسمّي هدفه.** في الصفحة عشرات الأزرار المتطابقة
                         الاسم؛ ومن يسمع الشاشة لا يميّز «إدراج» عن «إدراج».
                         فيُلحق بكلٍّ منها عنوان دراسته — والعين ترى الاسم
                         القصير كما كان. */
                      aria-label={`${t(USE_LABEL[next])}: ${describe(card)}`}
                      aria-pressed={card.use_state === next}
                      disabled={busy !== null || card.use_state === next}
                      className={card.use_state === next ? "chip chip-stage" : "chip chip-muted"}
                      onClick={() => decide(card, next)}
                    >
                      {t(USE_LABEL[next])}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>

          {/* التصفيح يقول أين أنت من كم — لا سهمين بلا عدد. */}
          <nav
            aria-label={t("common.page")}
            style={{ display: "flex", gap: 8, alignItems: "center", marginBlockStart: 12 }}
          >
            <button
              type="button"
              className="chip chip-muted"
              disabled={(data?.page ?? 1) <= 1 || busy !== null}
              onClick={() => setPage(Math.max(1, (data?.page ?? 1) - 1))}
            >
              {t("common.previous")}
            </button>
            <span className="metric-label">
              {t("common.page")} {data?.page ?? 1} {t("common.of")} {data?.pages ?? 1}
            </span>
            <button
              type="button"
              className="chip chip-muted"
              disabled={(data?.page ?? 1) >= (data?.pages ?? 1) || busy !== null}
              onClick={() => setPage((data?.page ?? 1) + 1)}
            >
              {t("common.next")}
            </button>
          </nav>
        </>
      )}

      {pending ? (
        <div
          className="card"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="exclusion-title"
          style={{ marginBlockStart: 16 }}
        >
          <strong id="exclusion-title">
            {t("screening.reasonTitle")}:{" "}
            {pending.cards.length === 1
              ? describe(pending.cards[0])
              : `${pending.cards.length} ${t("screening.selectedCount")}`}
          </strong>
          <p className="metric-label">{t("screening.reasonWhy")}</p>

          <label htmlFor="exclusion-reason" style={{ display: "block", marginBlockStart: 8 }}>
            {t("screening.reasonLabel")}
          </label>
          <select
            id="exclusion-reason"
            value={pending.code}
            onChange={(event) => setPending({ ...pending, code: event.target.value })}
          >
            <option value="">{t("screening.reasonPlaceholder")}</option>
            {(data?.reason_codes ?? []).map((code) => (
              <option key={code} value={code}>
                {t(`screening.reason_${code}`)}
              </option>
            ))}
          </select>

          <label htmlFor="exclusion-note" style={{ display: "block", marginBlockStart: 8 }}>
            {pending.code === FREE_TEXT_REASON
              ? t("screening.noteRequired")
              : t("screening.noteOptional")}
          </label>
          <textarea
            id="exclusion-note"
            rows={3}
            value={pending.note}
            onChange={(event) => setPending({ ...pending, note: event.target.value })}
          />

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 8 }}>
            <button
              type="button"
              className="chip chip-stage"
              /* زرٌّ مُفعَّل لا يفعل شيئًا يُعلّم الباحث ألّا يثق بالأزرار.
                 فيبقى معطَّلًا حتى يكتمل السبب. */
              disabled={!reasonIsComplete(pending) || busy !== null}
              onClick={confirmExclusion}
            >
              {t("screening.confirmExclusion")}
            </button>
            <button type="button" className="chip chip-muted" onClick={() => setPending(null)}>
              {t("project.cancel")}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}

/** سببٌ مكتمل: رمزٌ مُختار، ونصٌّ معه إن كان الرمز «سبب آخر». */
function reasonIsComplete(pending: Pending): boolean {
  if (!pending.code) return false;
  if (pending.code === FREE_TEXT_REASON) return pending.note.trim().length > 0;
  return true;
}

/**
 * أعداد التبويبات تأتي من الخادم، لا من طول القائمة المعروضة.
 *
 * **وهي محسوبة بكل المرشّحات إلا حال الفرز نفسها**: التبويب يسأل «كم
 * مُدرَجة ضمن ما أراه الآن»، فلو أُسقطت بقيّة المرشّحات لأجاب عن سؤالٍ آخر.
 */
function countOf(view: ScreeningView, tab: Tab): number {
  switch (tab) {
    case "saved_only":
      return view.saved_only;
    case "included":
      return view.included;
    case "excluded":
      return view.excluded;
    default:
      return view.all;
  }
}
