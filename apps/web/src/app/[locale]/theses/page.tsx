"use client";

import Link from "next/link";
import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { ThesisIntake } from "@/components/ThesisIntake";

/**
 * مكتبة الرسائل (§23).
 *
 * «أساس حق الاستخدام» يُعرض بوصفه ادعاءً سجّله الباحث، لا اعتمادًا: الاعتماد
 * قرار مستقل عند بوابة GT1 (§23.2 مقابل §23.9). الخلط بينهما هو ما يجعل
 * منصةً تظن أنها حصلت على الحقوق لأن أحدهم كتب أنه يملكها.
 *
 * ## وثلاثةُ عيوبٍ في الصدق أُصلحت هنا (Wave 1-C)
 *
 * **١ — رصّةُ بطاقاتٍ لا يفرّق بينها شيء.** خمسُ رسائل مرفوعة كانت تُعرض
 * خمسَ بطاقاتٍ متطابقة تقول «لم يُستخرَج العنوان بعد» — بلا اسم ملفّ، فلا
 * يعرف الباحث أيَّها ملفُّه. فصار العرضُ `display_title`: العنوان المستخرَج
 * إن وُجد، وإلّا **اسمُ الملفّ** ومعه سطرٌ يقول صراحةً إنّه اسم ملفّ لا
 * عنوان — فلا هويّةَ ضائعة، ولا عنوانٌ مختلَق.
 *
 * **٢ — «٠ أقسام · ٠ فرص» بلا سبب.** ستُّ حالاتٍ تُنتج هذا السطر ومعناها
 * مختلف تمامًا. **والفشل ليس فراغًا، وما لم يبدأ ليس نتيجةً صفرية.** فصار
 * كلُّ عددٍ يُعرض مع سببه من الخادم (`sections_outcome_label`)، ولا يُعرض
 * الرقمُ أصلًا إلّا حين يكون العدُّ قد وقع فعلًا.
 *
 * **٣ — رصّةٌ بلا نهاية.** القائمة كانت تقرأ كلّ رسائل المستأجر بلا حدّ.
 * فصارت صفحةً بمؤشّرٍ مفتاحيّ، ومعها بحثٌ وعروضٌ مسمّاة.
 *
 * **ولا نسبةٌ مئوية في هذه الشاشة.** خطُّ الأنابيب لا يقيس تقدّمًا، ورقمٌ
 * يُعرض بلا قياسٍ خلفه اختلاقٌ صغير يتكرّر في كلّ بطاقة.
 */
interface Thesis {
  id: string;
  /** `null` تعني «لم يُستخرَج بعد» — ولا تُملأ باسم ملف ولا بتخمين. */
  title: string | null;
  degree: string | null;

  /** هويّةُ البطاقة: اسمُ الملفّ، وما يُعرض، وهل هو عنوانٌ مستخرَج. */
  source_filename: string | null;
  display_title: string | null;
  title_is_extracted: boolean;

  /** حالٌ محفوظةٌ في القاعدة — لا مشتقّةٌ من آخر تشغيلة. */
  processing_state: string;
  processing_state_label: string;
  processing_attempts: number;

  failure_code: string | null;
  failure_message: string | null;
  can_retry: boolean;
  retry_blocked_reason: string | null;

  text_layer_state: string;
  ocr_state: string;
  ocr_available: boolean;

  defended_on: string | null;
  data_collected_on: string | null;
  rights_basis: string | null;
  parsed_at: string | null;

  sections_extracted: number;
  sections_outcome: string;
  sections_outcome_label: string;

  opportunities_found: number;
  opportunities_outcome: string;
  opportunities_outcome_label: string;
  opportunities_are_candidates: boolean;
}

const PAGE = 25;

/** العروض كما يقبلها الخادم — **قائمةٌ واحدة، فلا يرسل الزرّ ما يُردّ**. */
const VIEWS = [
  ["all", "theses.viewAll"],
  ["recent", "theses.viewRecent"],
  ["awaiting_action", "theses.viewAwaitingAction"],
  ["failed", "theses.viewFailed"],
  ["completed", "theses.viewCompleted"],
] as const;

/** الحالات التي يجوز عندها فتحُ المراجعة — **لا كلُّ حالٍ غير فارغة**. */
const REVIEWABLE: ReadonlySet<string> = new Set([
  "ready_for_review", "completed", "awaiting_consent",
]);

/** الحالات التي تعني «عملٌ يجري الآن» — فيُعرض التحديث لا إعادةُ المحاولة. */
const IN_FLIGHT: ReadonlySet<string> = new Set(["queued", "parsing", "extracting"]);

export default function ThesesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [theses, setTheses] = useState<Thesis[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // ── الصفحة والتصفية والبحث ──
  const [view, setView] = useState<string>("all");
  const [query, setQuery] = useState("");
  // `applied` هو ما سُئل عنه الخادم فعلًا؛ و`query` ما يكتبه الباحث الآن.
  // وفصلُهما يمنع طلبًا عند كل حرف، ويجعل «لا نتائج» تصف بحثًا وقع.
  const [applied, setApplied] = useState("");
  const [hasMore, setHasMore] = useState(false);

  // **«لا رسائل مسجّلة» بعد رفعٍ ناجح رسالةٌ تُفزع.** القائمة تبدأ فارغة،
  // فكانت تُقال قبل عودة الطلب — ومن رفع رسالته للتوّ يقرأ أنها ليست هناك.
  const [loaded, setLoaded] = useState(false);

  const [titleAr, setTitleAr] = useState("");
  const [titleEn, setTitleEn] = useState("");
  const [degree, setDegree] = useState("masters");
  const [defendedOn, setDefendedOn] = useState("");
  const [dataCollectedOn, setDataCollectedOn] = useState("");
  const [institutionAr, setInstitutionAr] = useState("");
  const [rightsBasis, setRightsBasis] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [supervisorName, setSupervisorName] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  /**
   * يقرأ صفحةً واحدة. `after` معرّفُ آخر رسالةٍ في الشاشة — **مؤشّرٌ
   * مفتاحيّ لا إزاحة**: الإزاحة تُكرّر صفًّا أو تُسقطه حين تُرفع رسالةٌ
   * بين صفحتين.
   */
  const fetchPage = useCallback(
    async (after: string | null, nextView: string, needle: string) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (nextView !== "all") params.set("view", nextView);
      if (needle.trim() !== "") params.set("q", needle.trim());
      if (after) params.set("after", after);
      return apiFetch<Thesis[]>(`/api/v1/theses?${params.toString()}`, { locale });
    },
    [locale],
  );

  const load = useCallback(async () => {
    try {
      const rows = await fetchPage(null, view, applied);
      setTheses(rows);
      // صفحةٌ ممتلئة تعني أنّ بعدها المزيد **احتمالًا** — ولا يُدّعى عددٌ
      // كلّيّ لم يُحسب: عدُّ كلّ الرسائل عبارةٌ ثانية ورحلةٌ ثانية إلى
      // مومباي في كلّ فتحةِ شاشة، ثمنُها لا يشتري شيئًا يقرؤه الباحث.
      setHasMore(rows.length === PAGE);
      setError(null);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [fetchPage, locale, t, view, applied]);

  useDeferredLoad(load);

  async function more() {
    const last = theses[theses.length - 1];
    if (!last) return;
    try {
      const rows = await fetchPage(last.id, view, applied);
      setTheses((current) => [...current, ...rows]);
      setHasMore(rows.length === PAGE);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }

  function chooseView(next: string) {
    setView(next);
    setLoaded(false);
    setTheses([]);
  }

  /** خانة فارغة تُرسل `null` لا سلسلة فارغة: العقد يميّز «غير مذكور» عن «فارغ». */
  function orNull(value: string): string | null {
    return value.trim() === "" ? null : value.trim();
  }

  async function onRegister(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await apiFetch("/api/v1/theses", {
        method: "POST",
        locale,
        body: JSON.stringify({
          title_ar: titleAr.trim(),
          title_en: orNull(titleEn),
          degree,
          defended_on: orNull(defendedOn),
          data_collected_on: orNull(dataCollectedOn),
          institution_ar: orNull(institutionAr),
          // §23.2 — الأساس ادعاء يُسجَّل، والاعتماد قرار مستقل عند GT1.
          rights_basis: orNull(rightsBasis),
          owner_name: orNull(ownerName),
          supervisor_name: orNull(supervisorName),
        }),
      });
      setTitleAr("");
      setTitleEn("");
      setDefendedOn("");
      setDataCollectedOn("");
      setInstitutionAr("");
      setRightsBasis("");
      setOwnerName("");
      setSupervisorName("");
      await load();
    } catch (err) {
      setFormError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setSaving(false);
    }
  }

  async function run(id: string, action: "parse" | "mine-opportunities" | "reprocess") {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/theses/${id}/${action}`, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("theses.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("theses.subtitle")}</p>
      {/* الرفع أولًا: الباحث يرفع رسالته فتُقرأ — لا يملأ نموذجًا عنها. */}
      <div style={{ marginBlock: "18px 24px" }}>
        <ThesisIntake locale={locale} messages={getMessages(locale)} />
      </div>
      <p className="provenance-note">{t("theses.rightsNote")}</p>
      {/* §23 — الفرص مرشَّحات، ويُقال ذلك حيث تُعدّ لا في حاشيةٍ بعيدة. */}
      <p className="provenance-note">{t("theses.candidatesOnly")}</p>

      {/* ── البحث والعروض: حدُّ الرصّة، وطريقُ الباحث إلى ما يريده ── */}
      <form
        className="form"
        style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}
        onSubmit={(event) => {
          event.preventDefault();
          setApplied(query);
          setLoaded(false);
          setTheses([]);
        }}
      >
        {/* **النائبُ ليس اسمًا** — يختفي بأوّل حرفٍ يُكتب، فيبقى الحقل بلا
            اسمٍ مُعلَن لقارئ الشاشة. فالاسمُ صريحٌ ومقرونٌ بمعرّف. */}
        <label htmlFor="thesis-search" style={{ flex: "1 1 240px" }}>
          {t("theses.searchLabel")}
          <input
            id="thesis-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("theses.searchPlaceholder")}
          />
        </label>
        <label htmlFor="thesis-view">
          {t("theses.viewLabel")}
          <select
            id="thesis-view"
            value={view}
            onChange={(event) => chooseView(event.target.value)}
          >
            {VIEWS.map(([value, key]) => (
              <option key={value} value={value}>
                {t(key)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">{t("theses.searchCta")}</button>
      </form>

      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : theses.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>
          {view !== "all" || applied.trim() !== "" ? t("theses.noMatches") : t("theses.empty")}
        </p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {theses.map((thesis) => (
          <article className="card" key={thesis.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              {/* **هويّةٌ لا تضيع.** العنوان المستخرَج، وإلّا اسمُ الملفّ. */}
              <strong>
                {thesis.display_title ?? (
                  <span style={{ color: "var(--muted)", fontWeight: 400 }}>
                    {t("theses.noFileNoTitle")}
                  </span>
                )}
              </strong>
              <span className="metric-label">
                {t("theses.degree")}:{" "}
                {thesis.degree === null
                  ? t("theses.noDegreeYet")
                  : t(`theses.${thesis.degree === "phd" ? "phd" : "masters"}`)}
              </span>
            </div>

            {/* **واسمُ الملفّ يُقال اسمَ ملفّ، لا عنوانَ رسالة.** فالبطاقة
                تحمل هويّةً ولا تدّعي استخراجًا لم يقع. */}
            {!thesis.title_is_extracted && thesis.display_title ? (
              <div className="provenance-note" style={{ marginBlockStart: 2 }}>
                {t("theses.identifiedByFilename")}
              </div>
            ) : null}

            {/* ── الحال: محفوظةٌ في القاعدة، ونصُّها من الخادم بلغة الباحث ── */}
            <div className="metric-label" style={{ marginBlockStart: 6 }}>
              {t("theses.stateLabel")}: {thesis.processing_state_label}
              {thesis.processing_attempts > 1
                ? ` · ${t("theses.attemptsLabel")}: ${thesis.processing_attempts}`
                : ""}
            </div>

            {/* **الفشل يُقال بسببه — ولا يُعرض صفرًا صامتًا.** */}
            {thesis.failure_message ? (
              <p className="error" style={{ margin: "6px 0 0" }}>
                {thesis.failure_message}
              </p>
            ) : null}

            <div className="metric-label" style={{ marginBlockStart: 6 }}>
              {t("theses.rightsBasis")}:{" "}
              {thesis.rights_basis ? t(`theses.basis.${thesis.rights_basis}`) : t("theses.noRights")}
              {thesis.defended_on ? ` · ${t("theses.defended")}: ${thesis.defended_on}` : ""}
            </div>

            {/* ── الرقمُ مع سببه، أو السببُ وحده ──
                «٠ أقسام» بلا سبب جملةٌ تُقال في ستّ حالاتٍ معناها مختلف؛
                فالرقم لا يُعرض إلّا حين يكون العدُّ قد وقع فعلًا. */}
            <div className="metric-label">
              {thesis.sections_outcome === "found"
                ? `${t("theses.sections")}: ${thesis.sections_extracted}`
                : thesis.sections_outcome_label}
            </div>
            <div className="metric-label">
              {thesis.opportunities_outcome === "found"
                ? `${t("theses.opportunities")}: ${thesis.opportunities_found}`
                : thesis.opportunities_outcome_label}
            </div>

            <div style={{ display: "flex", gap: 8, marginBlockStart: 12, flexWrap: "wrap" }}>
              {REVIEWABLE.has(thesis.processing_state) ? (
                <Link
                  href={`/${locale}/theses/${thesis.id}/review`}
                  style={{
                    padding: "8px 16px", borderRadius: "var(--radius)",
                    background: "var(--athera-teal)", color: "#fff", textDecoration: "none",
                  }}
                >
                  {t("theses.reviewCta")}
                </Link>
              ) : null}

              {/* **إعادةُ المحاولة حيث تنفع وحدها**، وسببُ منعها حيث تُمنع —
                  لا زرٌّ مطفأ بلا تفسير، ولا زرٌّ يَعِد بما لن يقع. */}
              {thesis.can_retry ? (
                <button
                  type="button"
                  onClick={() => run(thesis.id, "reprocess")}
                  disabled={busyId === thesis.id}
                  style={{
                    padding: "8px 16px", border: "1px solid var(--border)",
                    borderRadius: "var(--radius)", background: "transparent",
                    color: "inherit", font: "inherit", cursor: "pointer",
                  }}
                >
                  {t("theses.retryCta")}
                </button>
              ) : thesis.retry_blocked_reason && !IN_FLIGHT.has(thesis.processing_state) ? (
                <span className="provenance-note">{thesis.retry_blocked_reason}</span>
              ) : null}

              <button
                type="button"
                onClick={() => run(thesis.id, "parse")}
                disabled={busyId === thesis.id}
                style={{
                  padding: "8px 16px", border: "1px solid var(--border)",
                  borderRadius: "var(--radius)", background: "transparent",
                  color: "inherit", font: "inherit", cursor: "pointer",
                }}
              >
                {t("theses.parse")}
              </button>
              <button
                type="button"
                onClick={() => run(thesis.id, "mine-opportunities")}
                disabled={busyId === thesis.id || !thesis.parsed_at}
                style={{
                  padding: "8px 16px", border: "none", borderRadius: "var(--radius)",
                  background: "var(--athera-teal)", color: "#fff", font: "inherit",
                  cursor: thesis.parsed_at ? "pointer" : "not-allowed",
                  opacity: thesis.parsed_at ? 1 : 0.5,
                }}
              >
                {t("theses.mine")}
              </button>
            </div>
          </article>
        ))}
      </div>

      {loaded && theses.length > 0 ? (
        hasMore ? (
          <button
            type="button"
            onClick={() => void more()}
            style={{
              marginBlockStart: 12, padding: "8px 16px", border: "1px solid var(--border)",
              borderRadius: "var(--radius)", background: "transparent", color: "inherit",
              font: "inherit", cursor: "pointer",
            }}
          >
            {t("theses.loadMore")}
          </button>
        ) : (
          <p className="provenance-note">{t("theses.endOfList")}</p>
        )
      ) : null}

      <h2 style={{ marginBlockStart: "calc(var(--space) * 1.5)", fontSize: 18 }}>
        {t("theses.addTitle")}
      </h2>
      <form className="form" onSubmit={onRegister}>
        <label>
          {t("theses.addTitleAr")}
          <input value={titleAr} onChange={(e) => setTitleAr(e.target.value)} required minLength={3} />
        </label>
        <label>
          {t("theses.addTitleEn")}
          <input value={titleEn} onChange={(e) => setTitleEn(e.target.value)} />
        </label>
        <label>
          {t("theses.addDegree")}
          <select value={degree} onChange={(e) => setDegree(e.target.value)}>
            <option value="masters">{t("theses.masters")}</option>
            <option value="phd">{t("theses.phd")}</option>
          </select>
        </label>
        <label>
          {t("theses.addDefendedOn")}
          <input type="date" value={defendedOn} onChange={(e) => setDefendedOn(e.target.value)} />
        </label>
        <label>
          {t("theses.addDataCollectedOn")}
          <input
            type="date"
            value={dataCollectedOn}
            onChange={(e) => setDataCollectedOn(e.target.value)}
          />
        </label>
        <label>
          {t("theses.addInstitution")}
          <input value={institutionAr} onChange={(e) => setInstitutionAr(e.target.value)} />
        </label>
        <label>
          {t("theses.addRightsBasis")}
          <select value={rightsBasis} onChange={(e) => setRightsBasis(e.target.value)}>
            <option value="">{t("theses.noRights")}</option>
            <option value="thesis_owner">{t("theses.basis.thesis_owner")}</option>
            <option value="supervisor_with_consent">
              {t("theses.basis.supervisor_with_consent")}
            </option>
            <option value="institution_policy">{t("theses.basis.institution_policy")}</option>
          </select>
        </label>
        <label>
          {t("theses.addOwner")}
          <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} />
        </label>
        <label>
          {t("theses.addSupervisor")}
          <input value={supervisorName} onChange={(e) => setSupervisorName(e.target.value)} />
        </label>
        {formError ? <p className="error">{formError}</p> : null}
        <button type="submit" disabled={saving}>
          {saving ? t("app.loading") : t("theses.addSubmit")}
        </button>
      </form>
      <p className="provenance-note">{t("theses.addNote")}</p>
    </>
  );
}
