"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  decideSource,
  describe,
  loadScreening,
  type ScreeningCard,
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

interface Pending {
  card: ScreeningCard;
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
  const [data, setData] = useState<ScreeningView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  /**
   * **لا تُضبط حالةٌ داخل التأثير مباشرةً** — قاعدةٌ يفرضها المدقّق خطأً لا
   * تحذيرًا. والوعد المؤجّل يجعل الترتيب صريحًا: ثم الجواب، ثم الحالة.
   */
  const refresh = useCallback(
    (which: Tab) => {
      setLoad("loading");
      setError(null);
      return loadScreening(locale, projectId, which === "all" ? undefined : which)
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
      if (alive) void refresh(tab);
    });
    return () => {
      alive = false;
    };
  }, [refresh, tab]);

  /** «إدراج» و«حفظ فقط» يقعان مباشرة؛ و«استبعاد» يفتح سببه أولًا. */
  const decide = (card: ScreeningCard, next: ScreeningCard["use_state"]) => {
    if (next === "excluded") {
      setPending({ card, code: "", note: "" });
      return;
    }
    setBusy(card.source_id);
    setError(null);
    void decideSource(locale, projectId, card.source_id, { use_state: next })
      .then(() => refresh(tab))
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const confirmExclusion = () => {
    if (!pending || !reasonIsComplete(pending)) return;
    const { card, code, note } = pending;
    setBusy(card.source_id);
    setError(null);
    void decideSource(locale, projectId, card.source_id, {
      use_state: "excluded",
      reason_code: code,
      reason_ar: note.trim() ? note.trim() : undefined,
    })
      .then(() => {
        setPending(null);
        return refresh(tab);
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const cards = data?.cards ?? [];

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
                onClick={() => setTab(key)}
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

      {/* الفشل يُعلَن ومعه طريقُ الخروج منه — رسالةٌ بلا إعادةِ محاولة طريقٌ مسدود. */}
      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh(tab)}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

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
        <div style={{ display: "grid", gap: 10 }}>
          {cards.map((card) => (
            <article className="card" key={card.source_id}>
              <strong>{card.title}</strong>

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
              </div>

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
                    disabled={busy === card.source_id || card.use_state === next}
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
            {t("screening.reasonTitle")}: {describe(pending.card)}
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
              disabled={!reasonIsComplete(pending) || busy === pending.card.source_id}
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

/** أعداد التبويبات تأتي من الخادم، لا من طول القائمة المعروضة. */
function countOf(view: ScreeningView, tab: Tab): number {
  switch (tab) {
    case "saved_only":
      return view.saved_only;
    case "included":
      return view.included;
    case "excluded":
      return view.excluded;
    default:
      return view.saved_only + view.included + view.excluded;
  }
}
