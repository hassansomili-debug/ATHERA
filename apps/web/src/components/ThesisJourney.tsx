"use client";

import { useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { type Commit, useDeferredLoad } from "@/lib/useDeferredLoad";

/**
 * رحلةُ الرسالة إلى ورقة | The thesis-to-paper journey.
 *
 * **ولا نسبةَ مئوية هنا إطلاقًا.** «٦٠٪ مكتمل» رقمٌ بلا قياسٍ خلفه يقرؤه
 * الباحثُ وعدًا. فالشاشةُ تعرض الحالَ التي يقولها الخادم، والخطوةَ التي
 * تقابلها — لا أكثر. والخريطةُ أدناه صريحةٌ ومقروءة، لا حسابَ تقدّمٍ فيها.
 *
 * **ولا مفرداتِ نظامٍ في وجه الباحث**: لا «مرشّح واقعة» ولا «تنقيب» ولا
 * «استخراج» ولا «كنسيّ». الباحثُ يقرأ عن رسالته وورقته وحدهما.
 */

/**
 * **أربعُ خطواتٍ يقرؤها الباحث** — ورحلةُ MVP هي هذه وحدها:
 *
 *     رفعُ الرسالة → أفكارُ الأوراق → بناءُ الورقة → استوديو الورقة
 *
 * **ولا خطوةَ حقوقٍ وتأليف** (قرارُ منتج): لم تكن خطوةً في الرحلة، بل
 * حدًّا للإرسال عُرض في طريقها — فوقف الباحثُ أمام «أنت هنا» لا فعلَ
 * تحتها. وحارسُها باقٍ في القاعدة عند `ready_to_submit`، والإرسالُ ليس
 * من هذه الرحلة.
 *
 * **وتحديثُ الأدبيات خرج من الشريط أيضًا**: حدٌّ يقع داخل «بناء الورقة»
 * ويُقال في موضعه، لا خطوةٌ سادسة يعدّها الباحثُ ولا يفعل فيها شيئًا.
 */
const STEP_KEYS = [
  "analysis",
  "ideas",
  "build",
  "studio",
] as const;

/**
 * أيُّ خطوةٍ تقابل كلَّ حال — **خريطةٌ صريحة لا حسابُ نسبة**.
 *
 * والحالُ مصدرُها الخادم. وحالٌ لا تُعرف هنا تُعرض عند الخطوة الأولى ولا
 * تكسر الشاشة: العقدُ قد يسبق الواجهة، وسقوطُ الشاشة على حالٍ جديدة أسوأ
 * من عرضها في غير موضعها.
 */
const STEP_OF_STATE: Record<string, number> = {
  uploaded: 0,
  extracting: 0,
  analysed: 0,
  failed: 0,
  opportunities_ready: 1,
  researcher_decision_required: 1,
  overlap_review_required: 1,
  awaiting_ai_consent: 2,
  project_created: 2,
  thread_ready: 2,
  outline_ready: 2,
  manuscript_created: 2,
  drafting: 2,
  literature_pending: 4,
  ready_for_paper_studio: 5,
};

interface Journey {
  thesis_id: string;
  state: string;
  blocking_reasons: string[];
  /** ما يمنع الخطوةَ التالية بعينها — يحسبه الخادمُ ولا تشتقّه الشاشة. */
  current_blocking_reasons: string[];
  can_build_paper: boolean;
  /**
   * **الخيطُ الذهبيّ خطوةٌ في الرحلة، لا نقطةُ نهايةٍ تُكتشف.**
   *
   * كان الخادمُ يبنيه بنقطةٍ قائمة، ولا شيءَ في الشاشة ينادِيها — فحالُ
   * `thread_ready` واقعةٌ لا تقع إلّا لمن قرأ الشيفرة. والواقعةُ والفعلُ
   * كلاهما من الخادم: الشاشةُ لا تجتهد في البوّابات.
   */
  thread_ready: boolean;
  can_build_thread: boolean;
  opportunities: number;
  states: string[];
}

interface Opportunity {
  id: string;
  working_title: string;
  paper_kind_label: string;
  research_question_ar: string | null;
  readiness_outcome_label: string | null;
  salami_alert: boolean;
  provenance_count: number;
  /** قرارُ الباحث: `proposed` | `selected` | `excluded` — لا دورةُ الإنتاج. */
  planning_status: string;
  /** `null` = لم يُسجَّل اكتشافٌ لهذه الفرصة — ولا تُقرأ «مكتملة». */
  context_complete: boolean | null;
  missing_context: string[];
}

interface BuildResult {
  manuscript_id: string;
  state: string;
}

export function ThesisJourney({
  thesisId,
  locale,
  messages,
}: {
  thesisId: string;
  locale: Locale;
  messages: Messages;
}) {
  const t = translator(messages);

  const [journey, setJourney] = useState<Journey | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // ── **قفلٌ أثناء العمل، لا منعٌ من ورقةٍ ثانية** ──
  //
  // كان التعطيلُ مقصورًا على البطاقة العاملة (`busy === opportunity.id`)،
  // فتُعرض الشاشةُ وفيها بطاقةٌ تقول «نبني الخيط الذهبيّ…» وأخرى زرُّها
  // «ابدأ هذه الورقة» مضيءٌ يُنقر. فيبدأ الباحثُ ورقتين معًا بلا قصد،
  // ويرى نتيجتين متداخلتين لا يعرف أيَّهما لأيّ.
  //
  // **وهو قفلُ لحظةٍ لا سياسة**: ينتهي بانتهاء الطلب، ولا يمنع إنشاء
  // ورقةٍ أخرى بعده.
  const anyInFlight = busy !== null;
  /**
   * **مخطوطةٌ لكلِّ فرصة، لا واحدةٌ للصفحة.**
   *
   * كانت `manuscriptId` واحدةً للمكوّن كلِّه، فبناءُ ورقةٍ من البطاقة
   * الأولى يجعل **كلَّ** البطاقات تعرض «افتح في استوديو الورقة» وتشير
   * كلُّها إلى تلك المخطوطة بعينها — وهو درسُ مركز الرسائل نفسه: ما يخصّ
   * بطاقةً يُعرض في بطاقتها.
   */
  const [manuscripts, setManuscripts] =
    useState<Record<string, string>>({});

  const load = useCallback(async (commit: Commit) => {
    try {
      const state = await apiFetch<Journey>(
        `/api/v1/theses/${thesisId}/journey`, { locale });
      commit(() => setJourney(state));
      if (state.opportunities > 0) {
        const map = await apiFetch<{ opportunities: Opportunity[] }>(
          `/api/v1/theses/${thesisId}/publication-map`, { locale });
        commit(() => setOpportunities(map.opportunities ?? []));
      }
    } catch (err) {
      commit(() => setError(
        err instanceof AtheraApiError
          ? err.localized(locale)
          : t("common.loadFailed")));
    }
  }, [locale, thesisId, t]);

  const refresh = useDeferredLoad(load);

  /**
   * سببُ التوقّف المحدَّد، من `context.reasons` — **لا الجملةَ الجامعة**.
   *
   * و`thesis.journey_blocked` نصُّها «التفاصيل في أسباب التوقّف»، وأسبابُ
   * الرحلة المعروضة تُشتقّ من وقائعَ لا تحمل بياتَ البصمة: فبصمةٌ بائتة
   * تُردّ بجملةٍ تحيل إلى قائمةٍ لا تذكرها — طريقٌ مسدود. والرموزُ تسافر
   * في `context`، ولها نصُّها المترجَم أصلًا.
   */
  function refusalText(err: AtheraApiError): string {
    const codes = (err.payload.context?.reasons ?? "")
      .split(",")
      .map((code) => code.trim())
      .filter(Boolean);
    if (codes.length === 0) return err.localized(locale);
    return codes.map((code) => t(`journey.blocked.${code}`)).join(" ");
  }

  async function act(opportunityId: string, run: () => Promise<void>) {
    setBusy(opportunityId);
    setError(null);
    try {
      await run();
      await refresh();
    } catch (err) {
      setError(err instanceof AtheraApiError
        ? refusalText(err)
        : t("common.loadFailed"));
    } finally {
      setBusy(null);
    }
  }

  /**
   * بناءُ الخيط الذهبيّ — **بنقطةِ النهاية القائمة، ولا منطقَ يُعاد هنا**.
   *
   * والباحثُ لا يُطلب منه أن يزور شاشةَ الخيط بنفسه ويجمع مشروعَه: الفعلُ
   * حيث الرحلة. وما يمنعه يقوله الخادمُ رمزًا (`ai_consent_required`،
   * `ai_consent_stale`) وتترجمه القائمةُ فوق البطاقات.
   */
  function buildThread(opportunityId: string) {
    return act(opportunityId, async () => {
      await apiFetch(
        `/api/v1/theses/${thesisId}/opportunities/${opportunityId}/thread`,
        { method: "POST", locale });
    });
  }

  /**
   * **ابدأ هذه الورقة — فعلٌ واحد يقطع الطريقَ المسدود.**
   *
   * وكان على الباحث أن يختار، ثمّ يعود إلى لوحةِ الرحلة، ثمّ يجد زرَّ
   * البناء معطّلًا يقول «استكمل الحقوق والتأليف» — ولا مخرجَ منه. وذاك
   * حدٌّ في غير موضعه: الهيكلُ حتميّ، ولا يُرسل حرفًا ولا يُعلن جاهزيةً.
   *
   * فالنقرةُ الواحدة تفعل ما كان يُطلب في ثلاث: تختار إن لم تكن مختارة،
   * ثمّ تبني. **ولا يُفترض قرارٌ علميّ**: الاختيارُ يُسجَّل كما يسجّله
   * المسارُ الصريح، بفاعله وسببه، ويبقى قرارَ الباحث لأنّه هو من نقر.
   */
  function startPaper(opportunityId: string, alreadySelected: boolean) {
    return act(opportunityId, async () => {
      // **والقرارُ العلميُّ يُسجَّل كما يسجّله المسارُ الصريح** — نقطةُ
      // النهاية نفسُها، بفاعلها وقرارها. ولا يُفترض: الباحثُ هو من نقر.
      if (!alreadySelected) {
        await apiFetch(
          `/api/v1/theses/${thesisId}/opportunities/${opportunityId}/select`,
          { method: "POST", locale, body: JSON.stringify({ decision: "select" }) });
      }
      const result = await apiFetch<BuildResult>(
        `/api/v1/theses/${thesisId}/opportunities/${opportunityId}/build-paper`,
        { method: "POST", locale });
      setManuscripts((current) => ({
        ...current, [opportunityId]: result.manuscript_id,
      }));
    });
  }

  /** مخطوطةُ **هذه** الفرصة — أو لا شيء. ولا تُقرأ مخطوطةُ جارتها. */
  function manuscriptOf(opportunityId: string): string | undefined {
    return manuscripts[opportunityId];
  }

  const current = journey ? (STEP_OF_STATE[journey.state] ?? 0) : 0;
  // ── ما يمنع الآن: **يقوله الخادمُ، ولا تستنتجه الشاشة** ──
  //
  // وكانت الشاشةُ تحمل قائمةَ بوّاباتٍ «لاحقة» ترشّح بها القائمةَ العامّة —
  // أي أنّها تقرّر أيُّ حدٍّ يسري الآن. فتصير سياسةُ البوّابات في طرفين
  // يفترقان يومًا، ويسري في وجه الباحث ما لم يقرّره الخادم.
  //
  // فالقرارُ صار حقلًا في العقد: `current_blocking_reasons`.
  const blockingNow = journey?.current_blocking_reasons ?? [];

  const canBuildThread = journey?.can_build_thread === true;
  const threadReady = journey?.thread_ready === true;

  return (
    <section
      className="card"
      data-testid="thesis-journey"
      style={{ display: "grid", gap: 12 }}
    >
      <div>
        <strong style={{ fontSize: 17 }}>{t("journey.title")}</strong>
        <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>
          {t("journey.subtitle")}
        </p>
      </div>

      {/* ── الخطواتُ الست: موضعٌ يُقال، لا شريطُ تقدّمٍ يُحسب ── */}
      <ol
        data-testid="journey-steps"
        style={{
          display: "flex", gap: 8, flexWrap: "wrap", listStyle: "none",
          padding: 0, margin: 0,
        }}
      >
        {STEP_KEYS.map((key, index) => {
          const status =
            index < current ? "done" : index === current ? "current" : "waiting";
          return (
            <li
              key={key}
              data-testid={`journey-step-${key}`}
              data-status={status}
              style={{
                padding: "6px 12px",
                borderRadius: "var(--radius)",
                border: "1px solid var(--border, #ddd)",
                fontWeight: status === "current" ? 600 : 400,
                opacity: status === "waiting" ? 0.55 : 1,
              }}
            >
              {t(`journey.steps.${key}`)}
              <span className="metric-label" style={{ display: "block", fontSize: 12 }}>
                {t(`journey.${status}`)}
              </span>
            </li>
          );
        })}
      </ol>

      {/* ── ما ينتظر **الآن**: رمزُ الخادم يُترجَم إلى لغة الباحث ──
          **وقائمةٌ تقول «استكمل الحقوق أولًا» فوق زرٍّ يعمل تناقض.**
          فالحقوقُ والإذنُ لا يمنعان الفعلَ الرئيس، وموضعُهما أدناه مع
          سببِ لزومهما ووقتِه. ويبقى هنا ما يمنع الآن فعلًا. */}
      {blockingNow.length > 0 ? (
        <ul
          data-testid="journey-blocked"
          className="metric-label"
          style={{ margin: 0, paddingInlineStart: 18 }}
        >
          {blockingNow.map((reason) => (
            <li key={reason}>{t(`journey.blocked.${reason}`)}</li>
          ))}
        </ul>
      ) : null}

      {error ? (
        <p data-testid="journey-error" className="metric-label">{error}</p>
      ) : null}

      {/* **الخلوّ والإخفاق حالان لا تُجمعان.**
          «لا فرص أوراق بعد» دعوى معرفة، و«تعذّر التحميل» إعلانُ أنّ
          المعرفة لم تُتَح. وقائمةٌ تبدأ فارغةً وتبقى فارغةً بعد الإخفاق
          لا يفرّق شرطُها بينهما إلّا بذكر الخطأ صراحةً. */}
      {opportunities.length === 0 && !error ? (
        <p data-testid="journey-empty" className="metric-label">
          {t("journey.empty")}
        </p>
      ) : null}

      {/* ── بطاقاتُ الأوراق المقترحة ── */}
      {opportunities.map((opportunity) => (
        <article
          key={opportunity.id}
          className="card"
          data-testid={`opportunity-card-${opportunity.id}`}
          style={{ display: "grid", gap: 6 }}
        >
          <strong>{opportunity.working_title}</strong>

          <span className="metric-label">
            {t("journey.paperType")}: {opportunity.paper_kind_label}
          </span>

          <span className="metric-label" data-testid="opportunity-contribution">
            {t("journey.contribution")}:{" "}
            {opportunity.research_question_ar ?? t("journey.noContribution")}
          </span>

          <span className="metric-label">
            {t("journey.evidenceReadiness")}:{" "}
            {opportunity.readiness_outcome_label ?? t("journey.notScored")}
          </span>

          {/* **عددُ ما هو مُسنَد فعلًا** — لا درجةً ولا نسبة. */}
          <span className="metric-label" data-testid="opportunity-provenance">
            {opportunity.provenance_count} {t("journey.provenance")}
          </span>

          {opportunity.salami_alert ? (
            <span className="metric-label" data-testid="opportunity-overlap">
              {t("journey.overlapWarning")}
            </span>
          ) : null}

          {/* **والمقترحُ يُعلن أنّه مقترحُ آلة** — لا يُقرأ حكمًا علميًّا. */}
          {/* ── اكتمالُ السياق: يُقال ولا يُخفى ──
              **وفكرةٌ ناقصةُ السياق تُعرض ناقصةً معلنة.** الباحثُ يقرّر
              على بيّنة: هذه مؤصَّلةٌ ومكتملةُ السياق، وتلك مؤصَّلةٌ ينقصها
              وصفُ عيّنةٍ أو بُنًى. ولا يُخترع ما نقص ولا يُجمَّل.

              و`null` تعني «لم يُسجَّل» لا «ناقصة»: فرصةٌ من قبل ترحيل
              الاكتشاف لم يُحسب لها مستوًى، فلا يُقال عنها شيء. */}
          {opportunity.context_complete === true ? (
            <span className="metric-label" data-testid="opportunity-context">
              {t("journey.contextComplete")}
            </span>
          ) : opportunity.context_complete === false ? (
            <span className="metric-label" data-testid="opportunity-context">
              {t("journey.contextNeeds")}{" "}
              {(opportunity.missing_context ?? [])
                .map((gap) => gap === "sample"
                  ? t("journey.needsSample")
                  : gap === "constructs"
                    ? t("journey.needsConstructs")
                    : gap)
                .join(" · ")}
            </span>
          ) : null}

          <p
            className="provenance-note"
            data-testid="opportunity-ai-notice"
            style={{ margin: 0 }}
          >
            {t("journey.aiNotice")}
          </p>

          <div
            style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 6 }}
          >
            {manuscriptOf(opportunity.id) ? (
              /* **وترتيبُ الفعلين هو ترتيبُ الرحلة**: الخيطُ الذهبيّ قبل
                 الاستوديو. والخيطُ لا يُخفى حتى يُكتشف: إمّا زرٌّ يبنيه،
                 وإمّا إعلانٌ أنّه قائم. */
              <>
                {threadReady ? (
                  <span
                    data-testid="journey-thread-ready"
                    className="metric-label"
                    style={{ alignSelf: "center" }}
                  >
                    {t("journey.threadReady")}
                  </span>
                ) : (
                  <button
                    type="button"
                    data-testid="journey-build-thread"
                    disabled={!canBuildThread || anyInFlight}
                    onClick={() => void buildThread(opportunity.id)}
                    style={{
                      padding: "8px 16px", borderRadius: "var(--radius)",
                      border: "none",
                      background: "var(--athera-aqua, var(--athera-teal))",
                      color: "#04302c", font: "inherit", fontWeight: 600,
                      cursor: canBuildThread ? "pointer" : "not-allowed",
                      opacity: canBuildThread ? 1 : 0.5,
                    }}
                  >
                    {busy === opportunity.id
                      ? t("journey.threadBuilding")
                      : t("journey.threadCta")}
                  </button>
                )}

                {/* **والاستوديو بعد الخيط، لا بجواره.**
                    كانت الحاشيةُ تقول «الخيطُ الذهبيّ قبل الاستوديو»
                    ويُعرض الزرّان معًا — فيصيران فعلين متكافئين، ويمضي
                    الباحثُ إلى الاستوديو ببنيةٍ بحثيّةٍ لم تُبنَ.

                    **والمسارُ يقصد الاستوديو بعينه.** كان يقصد
                    `‎/manuscripts/<id>` ولا صفحةَ هناك — فيبلغ الباحثُ
                    ٤٠٤ بأوّلِ زرٍّ بعد بناء ورقته. */}
                {threadReady ? (
                  <a
                    data-testid="journey-open-studio"
                    href={`/${locale}/manuscripts/${manuscriptOf(opportunity.id)}/studio`}
                    style={{
                      padding: "8px 16px", borderRadius: "var(--radius)",
                      background: "var(--athera-teal)", color: "#fff",
                      textDecoration: "none",
                    }}
                  >
                    {t("journey.openStudio")}
                  </a>
                ) : null}
              </>
            ) : (
              /* **فعلٌ رئيسٌ واحد: «ابدأ هذه الورقة».**
                 يختار إن لم تكن مختارة، ثمّ يبني الهيكلَ الحتميّ. ولا
                 لوحةَ وسيطةٍ يُطلب المرورُ بها، ولا زرَّ معطّلًا يقف
                 أمام الباحث بلا فعلٍ يُنقر. */
              <button
                type="button"
                data-testid="journey-start-paper"
                disabled={anyInFlight}
                onClick={() => void startPaper(
                  opportunity.id, opportunity.planning_status === "selected")}
                style={{
                  padding: "8px 16px", borderRadius: "var(--radius)", border: "none",
                  background: "var(--athera-aqua, var(--athera-teal))",
                  color: "#04302c", font: "inherit", fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {busy === opportunity.id
                  ? t("journey.starting")
                  : t("journey.startPaper")}
              </button>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}
