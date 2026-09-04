"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مختبر الخيط الذهبي (§15).
 *
 * **«درجة الاتساق: ٠» لا تُعرض هنا.** والحساب يخصم عن كل عنصرٍ مفقود، فخيطٌ
 * في أوّله تنقصه العناصر التسعة يهبط إلى صفر — ويقرأ الباحث «بحثُك في أقصى
 * درجات التناقض» والحقيقةُ «لا نملك ما يكفي للحكم». والفرق ليس فرق درجةٍ بل
 * فرقُ نوع: الاتساق صفةُ علاقاتٍ بين عناصر موجودة، ولا علاقة تُفحص بين عنصرٍ
 * وغياب. فالخادم يرسل `presented_score` فارغةً ما دامت العناصر ناقصة، وتُعرض
 * مكانها جملةُ السبب بنصّها.
 *
 * **والصفحة لا تُظهر عددين متناقضين.** «تسعة عيوب حاجبة» فوق «لا توجد عيوب
 * اتساق» تناقضٌ في عين الباحث مهما استقام في الحساب: الأول يجمع المفقودات
 * والعيوب، والثاني يعدّ العيوب وحدها. فالأعداد تُعرض بأسمائها الأربعة —
 * عناصر مفقودة · عيوب بنيوية · تنبيهات منهجية · تعارضات — ولا يُجمع صنفان
 * في رقم.
 *
 * **وصفرُ التعارضات يُقال لماذا.** الكشوفات التسعة تقارن عنصرًا بغيابِ ما
 * يصله، لا صفًّا بصفٍّ يناقضه، فلا تُنتج تعارضًا — وصفرٌ صامت هنا يُقرأ
 * شهادةَ سلامةٍ عن مقارنةٍ لم تقع.
 */
interface Finding {
  check_key: string;
  kind: string;
  is_blocking: boolean;
  detail: string;
  excerpt: string | null;
}

interface Consistency {
  /** الدرجة الآلية للبوابة — **لا تُعرض**؛ المعروضة `presented_score`. */
  score: number;
  /** `null` تعني «لا تُعرض درجة»، ولا تعني صفرًا. */
  presented_score: number | null;
  is_computable: boolean;
  not_computed_reason: string | null;
  findings: Finding[];
  missing_elements: string[];
  missing_count: number;
  structural_count: number;
  linguistic_count: number;
  conflict_count: number;
  conflict_note: string | null;
  blocking_count: number;
  advisory_count: number;
  can_pass_gate: boolean;
  note: string;
}

interface Project {
  id: string;
  working_title: string;
}

/** §15.1 — التسعة التي يحتاجها خيط مكتمل، بترتيبها من المشكلة إلى التحليل. */
const REQUIRED_TYPES: string[] = [
  "problem", "gap", "question", "objective", "theory", "variable",
  "method", "instrument", "analysis",
];

/** أنواع يقبلها العقد ولا تحجب البوابة — تكمل الخيط إلى التوصية. */
const EXTRA_TYPES: string[] = [
  "phenomenon", "construct", "hypothesis", "result", "discussion", "recommendation",
];

const ALL_TYPES: string[] = [...REQUIRED_TYPES, ...EXTRA_TYPES];

export default function ThreadPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [data, setData] = useState<Consistency | null>(null);
  const [error, setError] = useState<string | null>(null);
  // يزداد بعد كل إضافة ناجحة، فتُعاد قراءة الاتساق من الخادم لا من الذاكرة:
  // الدرجة والبوابة يحسبهما الخادم، والواجهة لا تخمّنهما.
  const [revision, setRevision] = useState(0);

  const [elementType, setElementType] = useState<string>(REQUIRED_TYPES[0]!);
  const [labelAr, setLabelAr] = useState("");
  const [labelEn, setLabelEn] = useState("");
  const [detailAr, setDetailAr] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  // **«لا بحث مختار» كانت تُعرض على من له أبحاث.** `projectId` يبدأ `null`
  // ولا يُملأ إلا بعد عودة قائمة الأبحاث، فكانت الرسالة تظهر في تلك النافذة
  // — وهي دعوى عن محفظة الباحث لم تُقرأ بعد.
  const [projectsLoaded, setProjectsLoaded] = useState(false);

  useEffect(() => {
    apiFetch<Project[]>("/api/v1/portfolio/projects", { locale })
      .then((rows) => {
        setProjects(rows);
        if (rows.length > 0) setProjectId(rows[0]!.id);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      .finally(() => setProjectsLoaded(true));
  }, [locale]);

  useEffect(() => {
    if (!projectId) return;
    apiFetch<Consistency>(`/api/v1/projects/${projectId}/thread/consistency`, { locale })
      .then((next) => {
        setData(next);
        // النموذج يقترح أول عنصر مفقود، فيمشي المستخدم في الترتيب بلا اختيار
        // يدوي في كل مرة. إن اكتمل الخيط بقي الاختيار على آخر ما اختاره.
        if (next.missing_elements.length > 0) setElementType(next.missing_elements[0]!);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale, projectId, revision, t]);

  async function onAddElement(event: React.FormEvent) {
    event.preventDefault();
    if (!projectId) return;
    setBusy(true);
    setFormError(null);
    try {
      await apiFetch(`/api/v1/projects/${projectId}/thread/elements`, {
        method: "POST",
        locale,
        body: JSON.stringify({
          element_type: elementType,
          label_ar: labelAr,
          label_en: labelEn.trim() === "" ? null : labelEn.trim(),
          detail_ar: detailAr.trim() === "" ? null : detailAr.trim(),
          ordinal: ALL_TYPES.indexOf(elementType) + 1,
        }),
      });
      setLabelAr("");
      setLabelEn("");
      setDetailAr("");
      setRevision((n) => n + 1);
    } catch (err) {
      setFormError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>{t("thread.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("thread.subtitle")}</p>

      {projects.length > 1 ? (
        // قائمةُ اختيارٍ بلا اسمٍ مُعلَن: قارئ الشاشة يقول «قائمة» ولا يقول
        // قائمةَ ماذا — والصفحة كلّها تتغيّر بها.
        <select
          aria-label={t("thread.chooseProject")}
          value={projectId ?? ""}
          onChange={(e) => setProjectId(e.target.value)}
          style={{
            padding: "8px 12px",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            background: "var(--surface)",
            color: "inherit",
            font: "inherit",
            marginBlockEnd: "var(--space)",
          }}
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.working_title}
            </option>
          ))}
        </select>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
      {!projectsLoaded || (projectId && !data && !error) ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : !projectId ? (
        <p style={{ color: "var(--muted)" }}>{t("thread.noProject")}</p>
      ) : null}

      {data ? (
        <>
          {/* **الدرجة أو سببُ غيابها — ولا صفر.** والشرط على `is_computable`
              لا على `presented_score !== null` وحدها: درجةٌ صفرٌ مشروعة على
              خيطٍ مكتمل تنقصه الوصلات، وهي تُعرض. */}
          <section className="card" style={{ marginBlockEnd: "var(--space)" }}>
            <div className="metric-label">{t("thread.score")}</div>
            {data.is_computable && data.presented_score !== null ? (
              <div className="metric-value" data-testid="thread-score">
                {data.presented_score}
              </div>
            ) : (
              <p data-testid="thread-score-not-computed" style={{ margin: "4px 0 0" }}>
                {data.not_computed_reason ?? t("thread.scoreNotComputed")}
              </p>
            )}
          </section>

          {/* **أربعة أصناف بأسمائها، ولا رقمٌ يجمع صنفين.** */}
          <section className="grid">
            <article className="card">
              <div className="metric-label">{t("thread.missing")}</div>
              <div className="metric-value" data-testid="thread-missing-count">
                {data.missing_count}
              </div>
              <p className="metric-label" style={{ margin: 0 }}>{t("thread.missingHint")}</p>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.countStructural")}</div>
              <div
                className="metric-value"
                data-testid="thread-structural-count"
                style={{ color: data.structural_count ? "#b3261e" : undefined }}
              >
                {data.structural_count}
              </div>
              <p className="metric-label" style={{ margin: 0 }}>{t("thread.structuralHint")}</p>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.countLinguistic")}</div>
              <div
                className="metric-value"
                data-testid="thread-linguistic-count"
                style={{ color: data.linguistic_count ? "var(--athera-gold)" : undefined }}
              >
                {data.linguistic_count}
              </div>
              <p className="metric-label" style={{ margin: 0 }}>{t("thread.linguisticHint")}</p>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.conflicts")}</div>
              <div className="metric-value" data-testid="thread-conflict-count">
                {data.conflict_count}
              </div>
              {/* **صفرٌ صامت يُقرأ شهادةَ سلامة.** فيُقال لماذا لا تُنتج
                  هذه الكشوفات تعارضًا أصلًا. */}
              <p className="metric-label" style={{ margin: 0 }}>
                {data.conflict_note ?? t("thread.conflictsHint")}
              </p>
            </article>
          </section>

          <p className="provenance-note">
            {data.can_pass_gate ? t("thread.gateOpen") : t("thread.gateBlocked")} — {t("thread.gateNote")}
          </p>

          {data.missing_elements.length > 0 ? (
            <section style={{ marginBlockEnd: "var(--space)" }}>
              <p style={{ color: "var(--muted)", fontSize: 14, marginBlockEnd: 8 }}>
                {t("thread.missingList")}
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {data.missing_elements.map((type) => (
                  <span
                    key={type}
                    style={{
                      padding: "4px 10px",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius)",
                      background: "var(--surface)",
                      fontSize: 13,
                    }}
                  >
                    {t(`thread.elementTypes.${type}`)}
                  </span>
                ))}
              </div>
            </section>
          ) : (
            <p style={{ color: "var(--muted)" }}>{t("thread.allPresent")}</p>
          )}

          {/* **«لا توجد عيوب اتساق» وحدها تُقرأ شهادةَ سلامة.** وخيطٌ تنقصه
              ثمانيةُ عناصر لم تُفحص علاقاتُه أصلًا، فالجملة تصير حكمًا لم
              يقع. فيُقال المدى: فُحص الموجود ولم يُفحص الغائب. */}
          {data.findings.length === 0 ? (
            <p style={{ color: "var(--muted)" }} data-testid="thread-clean">
              {data.is_computable ? t("thread.clean") : t("thread.cleanPartial")}
            </p>
          ) : null}

          <div style={{ display: "grid", gap: 8 }}>
            {data.findings.map((finding, index) => (
              <article className="card" key={`${finding.check_key}-${index}`}>
                <div className="metric-label" style={{ color: finding.is_blocking ? "#b3261e" : "var(--athera-gold)" }}>
                  {finding.is_blocking ? t("thread.structural") : t("thread.linguistic")}
                </div>
                <p style={{ marginBlock: 6, fontSize: 14 }}>{finding.detail}</p>
                {finding.excerpt ? (
                  <blockquote
                    style={{
                      margin: 0,
                      paddingInlineStart: 12,
                      borderInlineStart: "3px solid var(--border)",
                      color: "var(--muted)",
                      fontSize: 13,
                    }}
                  >
                    {t("thread.excerpt")}: «{finding.excerpt}»
                  </blockquote>
                ) : null}
              </article>
            ))}
          </div>

          <h2 style={{ marginBlockStart: "calc(var(--space) * 1.5)", fontSize: 18 }}>
            {t("thread.addTitle")}
          </h2>
          <form className="form" onSubmit={onAddElement}>
            <label>
              {t("thread.addType")}
              <select value={elementType} onChange={(e) => setElementType(e.target.value)}>
                <optgroup label={t("thread.groupRequired")}>
                  {REQUIRED_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`thread.elementTypes.${type}`)}
                    </option>
                  ))}
                </optgroup>
                <optgroup label={t("thread.groupExtra")}>
                  {EXTRA_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`thread.elementTypes.${type}`)}
                    </option>
                  ))}
                </optgroup>
              </select>
            </label>
            <label>
              {t("thread.addLabelAr")}
              <input
                value={labelAr}
                onChange={(e) => setLabelAr(e.target.value)}
                required
                minLength={2}
              />
            </label>
            <label>
              {t("thread.addLabelEn")}
              <input value={labelEn} onChange={(e) => setLabelEn(e.target.value)} />
            </label>
            <label>
              {t("thread.addDetail")}
              <textarea rows={3} value={detailAr} onChange={(e) => setDetailAr(e.target.value)} />
            </label>
            {formError ? <p className="error">{formError}</p> : null}
            <button type="submit" disabled={busy || !projectId}>
              {busy ? t("app.loading") : t("thread.addSubmit")}
            </button>
          </form>
          <p className="provenance-note">{t("thread.addNote")}</p>

          <p className="provenance-note">{data.note}</p>
        </>
      ) : null}
    </>
  );
}
