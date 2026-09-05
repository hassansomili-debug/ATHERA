"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  ASSESSMENT_CATEGORIES,
  type AssessmentCategory,
  type AssessmentItem,
  type ProjectAssessment,
  type ScientificRule,
  projectAssessment,
  ruleIndex,
  scientificRules,
  totalItems,
} from "@/lib/researchBrain";
import {
  type SuggestedAction,
  type TaskPreview,
  actionsFor,
  suggestedActionPreview,
  suggestedActions,
} from "@/lib/suggestedActions";

/**
 * العقل البحثي — **خمس خانات، ولا نسبة**.
 *
 * «بحثك جاهز بنسبة ٨٢٪» لا تُعرض هنا ولا تُحسب. والنسبة تخفي الفرق بين
 * بحثٍ ينقصه سطرٌ وبحثٍ ينقصه منهج، وتحوّل حالًا مركّبة إلى رقمٍ يطمئن —
 * والقرار نفسه متّخذ في شاشة الحال العامة وفي `research_assessment/view.py`،
 * ولا يُنقض من بابٍ ثالث. فما يُعرض هنا **أعداد وحالات وأسطر بأسمائها**.
 *
 * **والتنبيه يصل برتبة قاعدته أو لا يصل.** سطرٌ يقول «ادّعاءٌ بلا دليل»
 * بمعرّفٍ مجرّد يقرؤه الباحث حكمًا معتمَدًا، وكلّ قواعد السجل مسوّدة لم
 * يراجعها مختصّ. فسجل القواعد يُقرأ مع التقييم، ويُقال صراحةً حين لا يصل.
 *
 * **وبحثٌ فارغ ليس بحثًا سليمًا.** التحميل والفشل والفراغ ثلاث حالات
 * مفترقة: خانةٌ فارغة على شاشةٍ لم تسأل بعد تُقرأ براءةً، وتقييمٌ سقط
 * يُعرض «لا شيء يُذكر» هو الكذبة نفسها في أسوأ لحظاتها.
 *
 * **والكشفُ لا يُنشئ التزامًا.** والسلسلة أربع حلقات لا حلقتان:
 *
 *     كشف → فعلٌ مقترح → معاينة → يقبل الباحث → تُنشأ مهمة
 *
 * وقائمةُ مهامّ الباحث لا يكتب فيها محرّكٌ قرأ نصًّا: كلُّ قواعد السجل
 * مسوّدة لم يراجعها مختصّ، ومن يجد في قائمته عشر مهامّ لم يطلبها يتوقّف
 * عن قراءة القائمة كلها — فيسقط التنبيه الصحيح مع الزائد. فالمعاينة تُري
 * **ما سيصير** لو قَبِل، والقبولُ فعلُه هو. والحلقة الرابعة لم تصل بعد
 * (نموذجُ المهمّة للمسار «ب»)، فزرّ القبول معطَّل ويُقال لماذا بنصّه بدل
 * أن يُعرض زرٌّ يَعِد بما لا يقع.
 */

type Load = "loading" | "ready" | "failed";

const CATEGORY_LABEL: Record<AssessmentCategory, string> = {
  known: "brain.cat_known",
  missing: "brain.cat_missing",
  needs_review: "brain.cat_needs_review",
  conflicts: "brain.cat_conflicts",
  methodological_alerts: "brain.cat_methodological_alerts",
};

const CATEGORY_HINT: Record<AssessmentCategory, string> = {
  known: "brain.hint_known",
  missing: "brain.hint_missing",
  needs_review: "brain.hint_needs_review",
  conflicts: "brain.hint_conflicts",
  methodological_alerts: "brain.hint_methodological_alerts",
};

/** الوسم يتبع معنى الخانة لا ذوق الشاشة: التعارض ليس خبرًا محايدًا. */
/**
 * **الحالُ لها لونٌ واحد في المنتج كلّه.**
 *
 * كان «التعارض» كهرمانيًّا هنا وأحمر في شاشةٍ أخرى، و«ما نعرفه» فيروزيًّا
 * هنا وأخضر هناك — فيتعلّم الباحث الخريطةَ في شاشةٍ ثمّ تكذبه في التي
 * بعدها. فصارت الأصنافُ الدلاليّة الأربعة هي المرجع: المقترَح بنفسجيّ،
 * وما ينتظر مراجعةً كهرمانيّ، والمتحقَّق أخضر، والمتعارض أحمر.
 *
 * **واللونُ لا يحمل المعنى وحده**: اسمُ الخانة مكتوبٌ فوق الشارة، وعددُها
 * مكتوبٌ فيها، والحدُّ المصمت يبقى بعد إطفاء الألوان.
 */
const CATEGORY_CHIP: Record<AssessmentCategory, string> = {
  known: "chip chip-verified",
  missing: "chip chip-muted",
  needs_review: "chip chip-review",
  conflicts: "chip chip-conflict",
  methodological_alerts: "chip chip-review",
};

/**
 * الفعل المقترح **بحسب باب القاعدة**، لا بحسب معرّفها.
 *
 * والقاعدة لا تحمل عمود «علاج» في المحرّك، فاشتقاقُ فعلٍ لكل معرّفٍ على
 * حدة كان سيصير جدولًا يتقادم في أول قاعدة تُضاف. والباب ثابت ومعلَن
 * (`RuleCategory`)، والفعل المقترح على مستواه صادق: يقول للباحث أين ينظر
 * ولا يدّعي أنه يعرف نصّه.
 */
function actionKey(rule: ScientificRule | undefined): string {
  if (!rule) return "brain.action_default";
  const known = ["causality", "fabrication", "design_fit", "evidence", "provenance", "lineage"];
  return known.includes(rule.category)
    ? `brain.action_${rule.category}`
    : "brain.action_default";
}

export default function ResearchBrainPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [assessment, setAssessment] = useState<ProjectAssessment | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [rules, setRules] = useState<ScientificRule[]>([]);
  // **سجل القواعد رايةٌ مستقلّة.** التقييم قد يصل والسجل يسقط، فتُعرض
  // التنبيهات بلا رتبها — وهذا يُقال بنصّه بدل أن يُترك الباحث يظنّها
  // معتمَدة.
  const [rulesLoad, setRulesLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  // **الاقتراحات رايةٌ ثالثة مستقلّة.** التقييم قد يصل وهي تسقط، فتُعرض
  // الكشوف بلا أفعالها — ويُقال ذلك بنصّه بدل أن يُقرأ «لا فعل مطلوب».
  const [actions, setActions] = useState<SuggestedAction[]>([]);
  const [actionsLoad, setActionsLoad] = useState<Load>("loading");
  // المعاينة المفتوحة — واحدةٌ في كل مرّة، بمفتاح اقتراحها.
  const [openPreview, setOpenPreview] = useState<string | null>(null);
  const [preview, setPreview] = useState<TaskPreview | null>(null);
  const [previewLoad, setPreviewLoad] = useState<Load>("ready");

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setRulesLoad("loading");
    setActionsLoad("loading");
    setError(null);
    setOpenPreview(null);
    setPreview(null);
    const one = projectAssessment(locale, projectId)
      .then((view) => {
        setAssessment(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setLoad("failed");
        setError(say(err));
      });
    const two = scientificRules(locale)
      .then((rows) => {
        setRules(rows);
        setRulesLoad("ready");
      })
      .catch(() => setRulesLoad("failed"));
    const three = suggestedActions(locale, projectId)
      .then((response) => {
        setActions(response.actions);
        setActionsLoad("ready");
      })
      .catch(() => setActionsLoad("failed"));
    return Promise.all([one, two, three]);
  }, [locale, projectId, say]);

  /**
   * يفتح معاينةَ اقتراح — **ويقرأها من الخادم ولا يبنيها هنا**.
   *
   * وبناءُ المعاينة في المتصفّح من حقول الاقتراح يجعل الشاشة تَعِد بمهمّةٍ
   * لم يوافق عليها الخادم، ثمّ تختلف المعاينةُ عمّا يُنشأ فعلًا يوم تصل
   * حلقةُ الإنشاء.
   */
  const togglePreview = useCallback(
    (actionKey: string) => {
      if (openPreview === actionKey) {
        setOpenPreview(null);
        setPreview(null);
        return;
      }
      setOpenPreview(actionKey);
      setPreview(null);
      setPreviewLoad("loading");
      void suggestedActionPreview(locale, projectId, actionKey)
        .then((view) => {
          setPreview(view);
          setPreviewLoad("ready");
        })
        .catch(() => setPreviewLoad("failed"));
    },
    [locale, openPreview, projectId],
  );

  // **لا حالة تُضبط داخل التأثير مباشرةً** — والوعد المؤجّل يجعل الترتيب صريحًا.
  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  const rulesById = ruleIndex(rules);
  const readNotes = assessment?.read_notes ?? [];

  /** الشاهد والمواضع — يُعرضان لكل سطر، بقاعدةٍ كان أو بلا قاعدة. */
  const renderEvidence = (item: AssessmentItem) => (
    <>
      {item.excerpt ? (
        <blockquote style={{ margin: "4px 0" }}>«{item.excerpt}»</blockquote>
      ) : null}
      {item.entity_ids.length > 0 ? (
        <p className="metric-label" style={{ margin: 0 }}>
          {t("brain.alertEntities")}: {item.entity_ids.join(" · ")}
        </p>
      ) : null}
    </>
  );

  /**
   * سطرٌ جاء من قاعدة — **بثمانية أجزاء لا بجملةٍ واحدة**.
   *
   * فـ«ادّعاءٌ بلا دليل» وحدها لا تُصحَّح: لا يعرف الباحث ما رُصد بالضبط،
   * ولا لِمَ يهمّ، ولا أين ينظر، ولا أَمِن قاعدةٍ اعتمدها مختصّ جاءت.
   * والعنوان شرطُ القاعدة، والسبب رسالتُها العلمية — وهما حقلان مختلفان
   * في المحرّك، وخلطهما يجعل الشرط يُقرأ حكمًا.
   */
  const renderAlert = (item: AssessmentItem,
                       rule: ScientificRule | undefined) => (
    <>
      <p style={{ margin: 0, fontWeight: 560 }}>
        {rule ? rule.condition : (item.rule_id ?? item.key)}
      </p>

      <p className="metric-label" style={{ margin: "8px 0 2px" }}>{t("brain.alertDetected")}</p>
      <p style={{ margin: 0 }}>{item.detail}</p>

      {rule ? (
        <>
          <p className="metric-label" style={{ margin: "8px 0 2px" }}>{t("brain.alertWhy")}</p>
          <p style={{ margin: 0 }}>{rule.message}</p>
        </>
      ) : null}

      <p className="metric-label" style={{ margin: "8px 0 2px" }}>{t("brain.alertEvidence")}</p>
      {item.excerpt || item.entity_ids.length > 0 ? (
        renderEvidence(item)
      ) : (
        <p style={{ margin: 0, color: "var(--muted)" }}>{t("brain.alertNoEvidence")}</p>
      )}

      {/* «ما ينقص لإتمام الفحص» ليس اختراعًا هنا: هي ملاحظات القراءة نفسها
          التي أرسلها الخادم عمّا لم يستطع قراءته. ولأنها واحدة لكل البحث،
          تُطوى في كل بطاقة ولا تُكرّر مفتوحةً عشر مرّات — والملخّص يسمّي
          ما تحته، فلا سهمٌ بلا اسم. */}
      <details style={{ marginBlockStart: 8 }}>
        <summary className="metric-label">
          {t("brain.alertMissingInfo")}
          {readNotes.length > 0 ? ` (${readNotes.length})` : ""}
        </summary>
        {readNotes.length > 0 ? (
          <ul style={{ margin: "4px 0 0", paddingInlineStart: 18 }}>
            {readNotes.map((note) => (
              <li key={note.key} style={{ color: "var(--muted)" }}>{note.detail}</li>
            ))}
          </ul>
        ) : (
          <p style={{ margin: "4px 0 0", color: "var(--muted)" }}>
            {t("brain.alertNoMissingInfo")}
          </p>
        )}
      </details>

      <p className="metric-label" style={{ margin: "8px 0 2px" }}>{t("brain.alertAction")}</p>
      <p style={{ margin: 0 }}>{t(actionKey(rule))}</p>

      <p style={{ margin: "8px 0 0", display: "flex", gap: 6, flexWrap: "wrap" }}>
        <span className="chip chip-muted">
          {t("brain.alertRule")}: {item.rule_id}
        </span>
        {rule ? (
          <>
            <span className="chip chip-stage">{t(`brain.ruleStatus_${rule.status}`)}</span>
            {/* **الرتبة وحدها لا تكفي.** «مسوّدة» مفردةُ حوكمة، و«لا توقف
                عملًا» هي ما يريد الباحث أن يعرفه — ويُقرأ من الخادم لا
                يُشتقّ هنا. */}
            <span className={rule.is_enforceable ? "chip chip-warn" : "chip chip-ok"}>
              {rule.is_enforceable ? t("brain.ruleEnforceable") : t("brain.ruleNotEnforceable")}
            </span>
          </>
        ) : (
          <span className="chip chip-muted">{t("brain.ruleUnknown")}</span>
        )}
      </p>
      {rule ? (
        <p className="metric-label" style={{ margin: "4px 0 0" }}>
          {t("brain.alertProvenance")}: {rule.provenance}
        </p>
      ) : null}
    </>
  );

  /** سطرٌ لا قاعدة خلفه — واقعةٌ مقروءة من صفوف البحث، تُعرض بنصّها. */
  const renderFact = (item: AssessmentItem) => (
    <>
      {item.detail}
      {renderEvidence(item)}
    </>
  );

  /**
   * الأفعال المقترحة على سطرٍ بعينه — **معاينةٌ تُفتح، ولا مهمّة تُنشأ**.
   *
   * وزرّ القبول معطَّل ويُقال لماذا: زرٌّ يَعِد بما لا يقع أسوأ من غيابه،
   * والباحث الذي ضغطه مرّةً بلا أثرٍ لا يضغطه حين يعمل.
   */
  const renderActions = (item: AssessmentItem) => {
    if (actionsLoad === "failed") {
      return (
        <p className="gate" data-testid="brain-actions-failed" style={{ margin: "8px 0 0" }}>
          {t("brain.actionsFailed")}
        </p>
      );
    }
    if (actionsLoad === "loading") return null;
    const mine = actionsFor(actions, item.key, item.entity_ids);
    if (mine.length === 0) return null;
    return (
      <div style={{ marginBlockStart: 8 }}>
        {mine.map((action) => (
          <div key={action.key} data-testid={`brain-action-${action.key}`}>
            <p style={{ margin: "0 0 4px" }}>{action.title}</p>
            <p style={{ margin: "0 0 4px", display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span className="chip chip-muted">
                {t("brain.actionState")}: {t(`brain.state_${action.state}`)}
              </span>
            </p>
            <button
              type="button"
              className="chip chip-stage"
              aria-expanded={openPreview === action.key}
              onClick={() => togglePreview(action.key)}
            >
              {openPreview === action.key
                ? t("brain.previewClose")
                : t("brain.previewButton")}
            </button>

            {openPreview === action.key ? (
              <section
                className="note"
                style={{ marginBlockStart: 8 }}
                data-testid="brain-preview"
                aria-label={t("brain.previewTitle")}
              >
                <p style={{ margin: 0, fontWeight: 560 }}>{t("brain.previewTitle")}</p>
                {previewLoad === "loading" ? (
                  <p style={{ margin: "4px 0 0", color: "var(--muted)" }}>
                    {t("app.loading")}
                  </p>
                ) : previewLoad === "failed" || preview === null ? (
                  // **الفشل ليس معاينةً فارغة.** ومعاينةٌ خالية تُقرأ
                  // «المهمّة بلا محتوى»، وهي دعوى عن مهمّةٍ لم تصل.
                  <p className="gate" style={{ margin: "4px 0 0" }}
                     data-testid="brain-preview-failed">
                    {t("brain.previewFailed")}
                  </p>
                ) : (
                  <>
                    <p style={{ margin: "6px 0 0" }}>
                      <strong>{preview.title}</strong>
                    </p>
                    <p style={{ margin: "4px 0 0" }}>{preview.detail}</p>

                    <p className="metric-label" style={{ margin: "8px 0 2px" }}>
                      {t("brain.previewSource")}
                    </p>
                    <p style={{ margin: 0 }}>{preview.source}</p>
                    {preview.excerpt ? (
                      <blockquote style={{ margin: "4px 0" }}>«{preview.excerpt}»</blockquote>
                    ) : null}

                    {/* ما لا يعرفه هذا المسار عن المهمّة يُسمَّى ولا يُملأ. */}
                    {preview.undetermined_fields.length > 0 ? (
                      <>
                        <p className="metric-label" style={{ margin: "8px 0 2px" }}>
                          {t("brain.previewUndetermined")}
                        </p>
                        <p style={{ margin: 0, display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {preview.undetermined_fields.map((field) => (
                            <span key={field.key} className="chip chip-muted">
                              {field.label}
                            </span>
                          ))}
                        </p>
                      </>
                    ) : null}

                    {/* **«لم تُنشأ مهمّة» يُقال بنصّه.** والمعاينة التي تصمت
                        عن ذلك تُقرأ إقرارًا بأنّ شيئًا سُجّل. */}
                    <p style={{ margin: "8px 0 0" }} data-testid="brain-preview-not-created">
                      <span className="chip chip-ok">{t("brain.previewNotCreated")}</span>{" "}
                      {preview.not_created_note}
                    </p>
                    <p className="metric-label" style={{ margin: "6px 0 0" }}>
                      {preview.pending_contract_note}
                    </p>
                    <button
                      type="button"
                      className="chip chip-muted"
                      disabled
                      data-testid="brain-accept-disabled"
                    >
                      {t("brain.acceptDisabled")}
                    </button>
                  </>
                )}
              </section>
            ) : null}
          </div>
        ))}
      </div>
    );
  };

  // **الـ`li` يملكه هذا المُنتِج وحده.** والقائمة تبقى قائمةً لقارئ الشاشة:
  // عنصرٌ غير `li` داخل `ul` يسقط من عدّ العناصر الذي يُعلنه، فيسمع الباحث
  // «قائمة من صفر» فوق خمسة أسطر.
  const renderItem = (item: AssessmentItem, category: AssessmentCategory) => (
    <li
      key={`${category}-${item.key}-${item.detail.slice(0, 24)}`}
      className={item.rule_id ? "card" : undefined}
      style={{ marginBlockEnd: item.rule_id ? 10 : 6 }}
    >
      {item.rule_id
        ? renderAlert(item, rulesById.get(item.rule_id))
        : renderFact(item)}
      {renderActions(item)}
    </li>
  );

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("brain.backToProject")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("brain.title")}</h1>
      <p className="metric-label">{t("brain.lead")}</p>
      <p style={{ marginBlockEnd: 12 }}>
        <Link href={`/${locale}/portfolio/${projectId}/thread`}>{t("brain.openThread")}</Link>
      </p>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="brain-loading" style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : load === "failed" || assessment === null ? (
        // **الفشل ليس فراغًا.** ولو عُرضت الخانات خاليةً هنا لقرأ الباحث
        // «لا شيء يُذكر» عن تقييمٍ لم يصل أصلًا.
        <p data-testid="brain-failed" className="gate">{t("brain.loadFailedNote")}</p>
      ) : (
        <>
          <section className="note" style={{ marginBlockEnd: 14 }}>
            <p style={{ margin: 0, fontWeight: 560 }}>{t("brain.advisoryTitle")}</p>
            <p style={{ margin: "4px 0 0" }}>{assessment.advisory_note}</p>
            <p style={{ margin: "4px 0 0" }}>{assessment.note}</p>
            <p style={{ margin: "6px 0 0" }} data-testid="brain-blocking">
              {t("brain.blockingLabel")}:{" "}
              {assessment.blocking_count === 0
                ? t("brain.blockingNone")
                : assessment.blocking_count}
            </p>
            {/* **الاقتراح يُقال اقتراحًا قبل أن يُقرأ.** والسطرُ الذي يقول
                «راجع كذا» بلا هذه الجملة يُقرأ مهمّةً أُسندت. */}
            {actionsLoad === "ready" ? (
              <p className="metric-label" style={{ margin: "6px 0 0" }}
                 data-testid="brain-actions-hint">
                {t("brain.actionsHint")}
              </p>
            ) : null}
          </section>

          <section aria-labelledby="brain-read-notes" style={{ marginBlockEnd: 14 }}>
            <h2 id="brain-read-notes">{t("brain.readNotesTitle")}</h2>
            <p className="metric-label">{t("brain.readNotesHint")}</p>
            {assessment.read_notes.length === 0 ? (
              <p data-testid="brain-read-notes-empty" style={{ color: "var(--muted)" }}>
                {t("brain.readNotesNone")}
              </p>
            ) : (
              <ul>
                {assessment.read_notes.map((note) => (
                  <li key={note.key}>{note.detail}</li>
                ))}
              </ul>
            )}
          </section>

          {rulesLoad === "failed" ? (
            <p className="gate" data-testid="brain-rules-failed">{t("brain.rulesUnavailable")}</p>
          ) : null}

          {totalItems(assessment) === 0 ? (
            <p data-testid="brain-empty" className="note">{t("brain.emptyKnown")}</p>
          ) : null}

          {ASSESSMENT_CATEGORIES.map((category) => (
            <section key={category} aria-labelledby={`brain-${category}`}
                     style={{ marginBlockEnd: 18 }}>
              <h2 id={`brain-${category}`} style={{ marginBlockEnd: 2 }}>
                {t(CATEGORY_LABEL[category])}{" "}
                <span className={CATEGORY_CHIP[category]} data-state={category}
                      data-testid={`brain-count-${category}`}>
                  {assessment[category].length} {t("brain.itemsCount")}
                </span>
              </h2>
              <p className="metric-label">{t(CATEGORY_HINT[category])}</p>
              {assessment[category].length === 0 ? (
                <p style={{ color: "var(--muted)" }}>{t("brain.emptyCategory")}</p>
              ) : (
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {assessment[category].map((item) => renderItem(item, category))}
                </ul>
              )}
            </section>
          ))}
        </>
      )}
    </>
  );
}
