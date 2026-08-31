"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مختبر الخيط الذهبي (§15).
 *
 * الدرجة معروضة، لكن **البوابة لا تُقرأ منها**: العدّاد الحاجب وقائمة
 * العناصر المفقودة هما ما يفتح البوابة أو يغلقها (§15.3). ولذلك يظهران
 * بجانب الرقم دائمًا، لا خلف نقرة.
 *
 * والعدّاد الحاجب يضم المفقودات: `blocking_count = العيوب + المفقودات`
 * (`score.compute`). فخيط فارغ يعرض تسعة حاجبة و«لا توجد عيوب اتساق» معًا،
 * وهما متسقان لا متناقضان — ولذلك تُسمّى المفقودات بأسمائها تحتهما، فلا
 * يُترك المستخدم أمام رقم أحمر بلا اسم يفسّره.
 */
interface Finding {
  check_key: string;
  kind: string;
  is_blocking: boolean;
  detail: string;
  excerpt: string | null;
}

interface Consistency {
  score: number;
  findings: Finding[];
  missing_elements: string[];
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

  useEffect(() => {
    apiFetch<Project[]>("/api/v1/portfolio/projects", { locale })
      .then((rows) => {
        setProjects(rows);
        if (rows.length > 0) setProjectId(rows[0]!.id);
      })
      .catch(() => setProjects([]));
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
        <select
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
      {!projectId ? <p style={{ color: "var(--muted)" }}>{t("thread.noProject")}</p> : null}

      {data ? (
        <>
          <section className="grid">
            <article className="card">
              <div className="metric-label">{t("thread.score")}</div>
              <div className="metric-value">{data.score}</div>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.blocking")}</div>
              <div className="metric-value" style={{ color: data.blocking_count ? "#b3261e" : undefined }}>
                {data.blocking_count}
              </div>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.advisory")}</div>
              <div className="metric-value" style={{ color: data.advisory_count ? "var(--athera-gold)" : undefined }}>
                {data.advisory_count}
              </div>
            </article>
            <article className="card">
              <div className="metric-label">{t("thread.missing")}</div>
              <div className="metric-value">{data.missing_elements.length}</div>
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

          {data.findings.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>{t("thread.clean")}</p>
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
