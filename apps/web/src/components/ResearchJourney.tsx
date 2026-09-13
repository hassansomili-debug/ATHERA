"use client";

import Link from "next/link";

import type { Locale } from "@/lib/i18n";
import {
  type JourneyStage,
  type MissingItem,
  type ProjectJourney,
  completedStages,
  currentStage,
  localeRoute,
  missingByGrade,
} from "@/lib/researchBrain";

/**
 * رحلةُ البحث — **أين أنت، وماذا أُنجز، وما الناقص، وما التالي، ولماذا**.
 *
 * وهذه الأسئلةُ الخمسة هي المنتج: الباحثُ لا يحتاج أن يعرف أنّ للمنصّة
 * «مساحةَ عمل» و«عقلًا» و«خيطًا ذهبيًّا» — يحتاج أن يعرف أين يقف وما
 * الخطوة.
 *
 * ## ولا منطقَ رحلةٍ هنا
 *
 * الحالُ والسببُ والفعلُ والمسار تأتي من الخادم كما هي. وكلُّ شرطٍ يُكتب
 * في هذا الملفّ نسخةٌ ثانية من قاعدةٍ تفترق عن أصلها بأول تعديل، ثمّ تعرض
 * الشاشةُ حكمًا لا يقوله الخادم. فما هنا ترتيبُ عرضٍ وترجمةُ رموز.
 *
 * ## ولا نسبةَ إنجاز
 *
 * لا «٧٣٪». والبحثُ ليس له مقامٌ كونيّ، والنسبةُ تُخفي الفرقَ بين بحثٍ
 * ينقصه سطرٌ وبحثٍ ينقصه منهج. فتُعرض الحالاتُ بأسمائها، وعددُ ما اكتمل
 * من تسعةٍ **عدًّا لا نسبة**.
 *
 * ## والمنعُ يُسمّى
 *
 * مرحلةٌ متوقّفة تُعرض ومعها سببُها وما يلزم لرفعه. وزرٌّ مطفأٌ بلا سببٍ
 * مكتوب طريقٌ مسدود — وهو الدرسُ المدفوع ثمنُه في رحلةٍ سابقة.
 */

type Translate = (key: string) => string;

/** حالُ القراءة — ثلاثٌ، **والفرقُ بين الثانية والثالثة هو المسألة**. */
export type JourneyLoad = "loading" | "ready" | "failed";

const GRADES: readonly MissingItem["severity"][] = [
  "blocking",
  "recommended",
  "optional",
] as const;

const GRADE_LABEL: Record<MissingItem["severity"], string> = {
  blocking: "researchJourney.missingBlocking",
  recommended: "researchJourney.missingRecommended",
  optional: "researchJourney.missingOptional",
};

/** شارةُ الحال — **نصٌّ لا لونٌ وحده** (§105): اللونُ لا يُقرأ بلا بصر. */
function StageBadge({ stage, t }: { stage: JourneyStage; t: Translate }) {
  const label = stage.is_current
    ? t("researchJourney.st_current")
    : t(`researchJourney.st_${stage.status}`);
  const tone =
    stage.is_current || stage.status === "completed" ? "chip chip-stage" : "chip chip-muted";
  return (
    <span className={tone} data-testid={`stage-badge-${stage.key}`}>
      {label}
    </span>
  );
}

function StageCard({
  stage,
  locale,
  t,
}: {
  stage: JourneyStage;
  locale: Locale;
  t: Translate;
}) {
  const href = localeRoute(locale, stage.route);
  return (
    <li
      className="card"
      data-testid={`stage-${stage.key}`}
      data-status={stage.status}
      data-current={stage.is_current ? "true" : "false"}
      /* **الحاليّةُ تُعلَن للقارئ الآليّ** لا بالتلوين وحده. */
      aria-current={stage.is_current ? "step" : undefined}
      style={{ display: "grid", gap: 4, minWidth: 0 }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <strong style={{ minWidth: 0, overflowWrap: "anywhere" }}>
          {href ? (
            <Link href={href} data-testid={`stage-link-${stage.key}`}>
              {stage.title}
            </Link>
          ) : (
            stage.title
          )}
        </strong>
        <StageBadge stage={stage} t={t} />
      </div>

      {stage.summary ? (
        <p className="metric-label" style={{ margin: 0, overflowWrap: "anywhere" }}>
          {stage.summary}
        </p>
      ) : null}

      {/* **والمنعُ يقول لمَ وما يلزم** — لا ضابطٌ مطفأٌ صامت (§44). */}
      {stage.status === "blocked" ? (
        <p style={{ margin: 0, fontSize: 14 }} data-testid={`stage-blocked-${stage.key}`}>
          {stage.reason}{" "}
          <span className="metric-label">
            {t("researchJourney.blockedNeeds")}:{" "}
            {stage.blocking_reasons.map((code) => t(`blocker.${code}`)).join(" ")}
          </span>
        </p>
      ) : null}
    </li>
  );
}

/**
 * الرحلةُ بحالاتها الثلاث — **والمكوّنُ يملكها كلَّها**.
 *
 * وكانت الصفحةُ تملك «جارٍ» و«تعذّر» ويملك المكوّنُ المحتوى وحده. فأمسك
 * حارسٌ قائم (`test_every_screen_that_claims_emptiness_can_first_say_it_is_loading`)
 * أنّ ملفًّا يقول «لم يُنجَز شيءٌ بعد» لا يملك ما يقول به «لم يصل الجواب» —
 * وهما لا يُفرَّق بينهما بالنظر.
 *
 * والعلاجُ جمعُ الثلاث هنا لا تليينُ الحارس: مَن يقول «خالٍ» يجب أن
 * يستطيع قولَ «أنتظر».
 */
export function ResearchJourney({
  journey,
  load,
  locale,
  t,
  onRetry,
}: {
  journey: ProjectJourney | null;
  load: JourneyLoad;
  locale: Locale;
  t: Translate;
  onRetry: () => void;
}) {
  if (load === "loading") {
    return (
      <p data-testid="journey-loading" style={{ color: "var(--muted)" }}>
        {t("researchJourney.loading")}
      </p>
    );
  }
  if (load === "failed" || journey === null) {
    // **والسقوطُ ليس فراغًا**: شاشةٌ بلا خطوةٍ تُقرأ «لا شيء مطلوب».
    return (
      <p data-testid="journey-failed" className="gate">
        {t("researchJourney.failed")}{" "}
        <button type="button" className="chip chip-muted" onClick={onRetry}>
          {t("common.retry")}
        </button>
      </p>
    );
  }

  const here = currentStage(journey);
  const done = completedStages(journey);
  const next = journey.recommended;
  const nextHref = localeRoute(locale, next?.route ?? null);

  return (
    <section
      aria-labelledby="research-journey-heading"
      data-testid="research-journey"
      style={{ display: "grid", gap: 12, minWidth: 0 }}
    >
      <div>
        <h2 id="research-journey-heading" style={{ marginBlockEnd: 2 }}>
          {t("researchJourney.title")}
        </h2>
        <p className="metric-label" style={{ margin: 0 }}>
          {t("researchJourney.lead")}
        </p>
      </div>

      {/* ═══ أين أنت؟ والخطوة التالية ولماذا — في بطاقةٍ واحدة ═══ */}
      <article className="card" data-testid="journey-here" style={{ minWidth: 0 }}>
        <div className="metric-label">{t("researchJourney.whereAreYou")}</div>
        <p
          style={{ margin: "2px 0 0", fontSize: 17, fontWeight: 560 }}
          data-testid="journey-current-stage"
        >
          {here ? here.title : t("researchJourney.noNextStep")}
        </p>

        <div className="metric-label" style={{ marginBlockStart: 10 }}>
          {t("researchJourney.nextStep")}
        </div>
        {next ? (
          <>
            <p
              style={{ margin: "2px 0 0", fontSize: 15 }}
              data-testid="journey-next-title"
            >
              {next.title}
            </p>
            {/* **وكلُّ فعلٍ يقول لمَ** (§43) — لا «الذكاء الاصطناعي يقترح». */}
            <p style={{ margin: "6px 0 0" }} data-testid="journey-next-why">
              <span className="metric-label">{t("researchJourney.why")} </span>
              {next.reason}
            </p>
            {/* **فعلٌ رئيسٌ واحد** (§42، §58) — لا خمسةَ عشرَ اقتراحًا متساوية. */}
            {nextHref ? (
              <p style={{ margin: "10px 0 0" }}>
                <Link
                  className="chip chip-stage"
                  href={nextHref}
                  data-testid="journey-primary-cta"
                >
                  {t("researchJourney.open")}
                </Link>
              </p>
            ) : null}
          </>
        ) : (
          <p style={{ margin: "2px 0 0" }} data-testid="journey-next-none">
            {t("researchJourney.noNextStep")}
          </p>
        )}
      </article>

      {/* ═══ ماذا أُنجز؟ — عددٌ لا نسبة ═══ */}
      <div data-testid="journey-done">
        <div className="metric-label">{t("researchJourney.whatIsDone")}</div>
        {done.length === 0 ? (
          <p style={{ margin: "2px 0 0" }} data-testid="journey-done-none">
            {t("researchJourney.nothingDone")}
          </p>
        ) : (
          <p style={{ margin: "2px 0 0" }}>
            {done.map((row) => row.title).join(" · ")}
          </p>
        )}
      </div>

      {/* ═══ المراحلُ التسع ═══ */}
      <nav aria-label={t("researchJourney.stagesLabel")}>
        <ol
          data-testid="journey-stages"
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            display: "grid",
            /* **ويطوي الشريطُ نفسه على الجوّال** (§53): عمودٌ واحد تحت
               ٤٢٠px، فلا يحتاج الفهمُ تمريرًا أفقيًّا. */
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))",
            gap: 8,
          }}
        >
          {journey.stages.map((stage) => (
            <StageCard key={stage.key} stage={stage} locale={locale} t={t} />
          ))}
        </ol>
      </nav>

      {/* ═══ ما الناقص؟ — ثلاثُ رتبٍ لا قائمةٌ حمراء ═══ */}
      <div data-testid="journey-missing">
        <div className="metric-label">{t("researchJourney.whatIsMissing")}</div>
        <div style={{ display: "grid", gap: 4, marginBlockStart: 4 }}>
          {GRADES.map((grade) => {
            const rows = missingByGrade(journey, grade);
            if (rows.length === 0) return null;
            return (
              <p
                key={grade}
                style={{ margin: 0, fontSize: 14 }}
                data-testid={`journey-missing-${grade}`}
              >
                <span className="metric-label">{t(GRADE_LABEL[grade])}: </span>
                {rows.map((row) => row.label).join(" · ")}
              </p>
            );
          })}
        </div>
      </div>

      {/* ═══ ما يعرفه PUBRIVA — و«غير مسجَّل» جوابٌ صحيح ═══ */}
      <details data-testid="journey-known">
        <summary>{t("researchJourney.knownTitle")}</summary>
        <ul style={{ margin: "6px 0 0", paddingInlineStart: 18 }}>
          {journey.known.map((fact) => (
            <li key={fact.key} data-testid={`known-${fact.key}`}>
              {fact.label}:{" "}
              {fact.known ? (
                fact.value
              ) : (
                /* **والمجهولُ يبقى مجهولًا** (§51) — لا يُملأ باستنباط. */
                <span className="metric-label">{t("researchJourney.notRecorded")}</span>
              )}
            </li>
          ))}
        </ul>
      </details>

      {/* ═══ والتعارضُ يُعرض ولا يُحسم ═══ */}
      {journey.conflict_count > 0 ? (
        <p className="gate" data-testid="journey-conflicts" style={{ margin: 0 }}>
          {t("researchJourney.conflictTitle")} ({journey.conflict_count})
        </p>
      ) : null}
    </section>
  );
}
