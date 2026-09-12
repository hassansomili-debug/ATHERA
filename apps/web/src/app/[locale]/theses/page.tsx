"use client";

import Link from "next/link";
import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad, type Commit } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { ThesisIntake } from "@/components/ThesisIntake";

/**
 * مركز الرسائل (§23).
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
 * ## وأربعةٌ أُصلحت في هذه الموجة (Wave 1.1)
 *
 * **٤ — معماريّتان تُعرضان سيرَ عملٍ واحدًا.** «تفكيك الرسالة» يكتب
 * `thesis_sections`، والقراءة التلقائية تكتب مرشّحاتِ وقائع ولا تكتب أقسامًا،
 * والمنقّب لا يقرأ إلّا الأقسام والنتائج. فكان زرُّ «استخراج الفرص» مشروطًا
 * بـ`parsed_at` — ختمِ المسار القديم وحده — فيبقى مطفأً أبدًا على كلّ رسالةٍ
 * قرأها الخطُّ الحديث. **والحكمُ صار في الخادم**: `thesis.actions` تقول ما
 * يُعرض، والشاشة تعرضه ولا تعيد بناء الشروط.
 *
 * **٥ — أزرارٌ يردّها الخادم.** «تفكيك الرسالة» كان يُعرض على كلّ بطاقة —
 * ومنها رسالةٌ بلا ملفّ تردّ `thesis.no_file` بـ422، وبطاقةٌ يجري عليها عملٌ
 * تردّ 409. فلا يُعرض اليوم فعلٌ إلّا وهو مقبول.
 *
 * **٦ — ضغطةٌ صامتة.** كانت حالُ الانشغال واحدةً للصفحة كلّها ورسالةُ الخطأ
 * في أعلاها. فمن ضغط البطاقة الخامسة عشرة لم يرَ شيئًا، وصعد ليقرأ خطأً لا
 * يعرف أيَّ بطاقةٍ يخصّ. **فصار لكلّ بطاقةٍ حالُها**: انشغالُها، وخبرُها،
 * وخطؤها — داخلها.
 *
 * **٧ — لا مخرج.** لم يكن في المنتج طريقٌ لإزالة رسالة. فصارت في قائمة «⋯»،
 * ومعها **معاينةُ تبعات** تُحسب قبل السؤال: ما يقوم على الرسالة يُعرض بأسمائه
 * وأعداده، وإن كان فيه حكمُ إنسانٍ **رُفضت الإزالة** ولم تقع بصمت.
 *
 * **ولا نسبةٌ مئوية في هذه الشاشة.** خطُّ الأنابيب لا يقيس تقدّمًا، ورقمٌ
 * يُعرض بلا قياسٍ خلفه اختلاقٌ صغير يتكرّر في كلّ بطاقة.
 */

/** ما تعرضه البطاقة — **قرارٌ واحد يُحسب في الخادم، لا سبعةٌ هنا**. */
interface CardActions {
  /** review · process · reprocess · attach_file · null */
  primary: string | null;
  is_running: boolean;
  can_review: boolean;
  can_process: boolean;
  can_reprocess: boolean;
  /** المسار القديم باقٍ في الواجهة البرمجية ومسحوبٌ من البطاقة. */
  can_parse: boolean;
  can_attach_file: boolean;
  can_mine: boolean;
  can_view_opportunities: boolean;
  can_archive: boolean;
  can_restore: boolean;
  can_trash_file: boolean;
  is_archived: boolean;
  /** سببُ منعِ الأرشفة والسلّة أثناء عملٍ جارٍ — **والخادم يفرضه أيضًا**. */
  lifecycle_blocked_reason: string | null;
  /**
   * available · in_flight · no_evidence · found · failed · withheld ·
   * completed_empty · no_eligible_evidence
   *
   * و`no_eligible_evidence` ليست `no_evidence`: الأولى فحصٌ جرى فلم يجد
   * دليلًا مؤهَّلًا، والثانية فحصٌ لم يجرِ بعد. والنصُّ يأتي من الخادم.
   */
  mining_state: string;
  mining_reason: string;
  parse_withdrawn_reason: string;
  blocked_reason: string | null;
}

interface Thesis {
  id: string;
  /** `null` تعني «لم يُستخرَج بعد» — ولا تُملأ باسم ملف ولا بتخمين. */
  title: string | null;
  degree: string | null;

  /** هويّةُ البطاقة: اسمُ الملفّ، وما يُعرض، وهل هو عنوانٌ مستخرَج. */
  source_filename: string | null;
  source_file_id: string | null;
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

  results_extracted: number;

  opportunities_found: number;
  opportunities_outcome: string;
  opportunities_outcome_label: string;
  opportunities_are_candidates: boolean;

  /** **مؤرشَفة = مُخفاة لا محذوفة.** `null` تعني «في القائمة». */
  archived_at: string | null;

  actions: CardActions;
}

interface RemovalDependency {
  key: string;
  label: string;
  count: number;
  blocking: boolean;
}

interface RemovalPreview {
  thesis_id: string;
  /** **لا «أيجوز حذفُها؟»** — الحذفُ ذهب. بل «أيستوجب إخفاؤها إقرارًا؟». */
  needs_acknowledgement: boolean;
  dependencies: RemovalDependency[];
  blocking: RemovalDependency[];
  explanation: string;
  source_file_id: string | null;
}

/**
 * حالُ بطاقةٍ واحدة — **ولا تُشارك بطاقةً أخرى شيئًا منها**.
 *
 * `busy` اسمُ الفعل الجاري لا رايةٌ صمّاء: البطاقة تقول أيَّ فعلٍ يجري،
 * وتُعطّل ما يتعارض معه وحده.
 */
interface CardState {
  busy: string | null;
  error: string | null;
  notice: string | null;
  menuOpen: boolean;
  preview: RemovalPreview | null;
  trashNeedsConfirm: boolean;
}

const EMPTY_CARD: CardState = {
  busy: null, error: null, notice: null,
  menuOpen: false, preview: null, trashNeedsConfirm: false,
};

const PAGE = 25;

/** العروض كما يقبلها الخادم — **قائمةٌ واحدة، فلا يرسل الزرّ ما يُردّ**. */
const VIEWS = [
  ["all", "theses.viewAll"],
  ["recent", "theses.viewRecent"],
  ["awaiting_action", "theses.viewAwaitingAction"],
  ["failed", "theses.viewFailed"],
  ["completed", "theses.viewCompleted"],
  // **الأرشيف مرئيّ** — وإلّا صارت الأرشفة حذفًا في تجربة الباحث.
  ["archived", "theses.viewArchived"],
] as const;

const BUTTON: React.CSSProperties = {
  padding: "8px 16px", border: "1px solid var(--border)",
  borderRadius: "var(--radius)", background: "transparent",
  color: "inherit", font: "inherit", cursor: "pointer",
};

const PRIMARY: React.CSSProperties = {
  padding: "8px 16px", border: "none", borderRadius: "var(--radius)",
  background: "var(--athera-teal)", color: "#fff", font: "inherit",
  textDecoration: "none", cursor: "pointer",
};

export default function ThesesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [theses, setTheses] = useState<Thesis[]>([]);
  const [error, setError] = useState<string | null>(null);
  // **خبرٌ على مستوى الصفحة لفعلٍ تغادر بطاقتُه القائمة** — وهو الاستثناء
  // الوحيد: بطاقةٌ خرجت من القائمة لا تحمل خبرَ خروجها.
  const [notice, setNotice] = useState<string | null>(null);

  // **حالُ كلّ بطاقةٍ على حدة** — والمفتاح معرّفُ الرسالة. وحالُ انشغالٍ
  // واحدة للصفحة كلّها كانت تجعل ضغطتين على بطاقتين تتصادمان، وخبرَ إحداهما
  // يمحو خبر الأخرى.
  const [cardState, setCardState] = useState<Record<string, CardState>>({});

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


  const card = useCallback(
    (id: string): CardState => cardState[id] ?? EMPTY_CARD,
    [cardState],
  );

  const patchCard = useCallback((id: string, patch: Partial<CardState>) => {
    setCardState((current) => ({
      ...current,
      [id]: { ...(current[id] ?? EMPTY_CARD), ...patch },
    }));
  }, []);

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

  const load = useCallback(async (commit: Commit) => {
    try {
      const rows = await fetchPage(null, view, applied);
      // **هنا كان العطب**: ردُّ «الكلّ» المتأخّر كان يكتب صفوفَه فوق صفوف
      // «المؤرشفة»، فتقول القائمةُ المنسدلة عرضًا وتقول الصفوفُ غيرَه.
      commit(() => {
        setTheses(rows);
        // صفحةٌ ممتلئة تعني أنّ بعدها المزيد **احتمالًا** — ولا يُدّعى عددٌ
        // كلّيّ لم يُحسب: عدُّ كلّ الرسائل عبارةٌ ثانية ورحلةٌ ثانية إلى
        // مومباي في كلّ فتحةِ شاشة، ثمنُها لا يشتري شيئًا يقرؤه الباحث.
        setHasMore(rows.length === PAGE);
        setError(null);
      });
    } catch (err) {
      const message = err instanceof AtheraApiError
        ? err.localized(locale) : t("common.loadFailed");
      commit(() => setError(message));
    } finally {
      commit(() => setLoaded(true));
    }
  }, [fetchPage, locale, t, view, applied]);

  const refresh = useDeferredLoad(load);

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
    // **خبرُ فعلٍ سابق لا يُقرأ حكمًا على عرضٍ جديد.**
    setNotice(null);
  }

  /** خانة فارغة تُرسل `null` لا سلسلة فارغة: العقد يميّز «غير مذكور» عن «فارغ». */


  function say(err: unknown): string {
    return err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed");
  }

  /**
   * فعلٌ على بطاقةٍ بعينها — **وخبرُه يقع فيها، لا في أعلى الصفحة**.
   *
   * ومن ضغط البطاقة الخامسة عشرة لا يصعد ليعرف أنجح أم سقط، ولا يقرأ خطأً
   * لا يعرف أيَّ بطاقةٍ يخصّ.
   */
  async function run(id: string,
                     action: "mine-opportunities" | "reprocess" | "restore",
                     successKey: string) {
    patchCard(id, { busy: action, error: null, notice: null, menuOpen: false });
    try {
      await apiFetch(`/api/v1/theses/${id}/${action}`, { method: "POST", locale });
      patchCard(id, { busy: null, notice: t(successKey) });
      await refresh();
    } catch (err) {
      patchCard(id, { busy: null, error: say(err) });
    }
  }

  /** **ما يقوم على الرسالة يُحسب قبل السؤال، لا بعده.** */
  async function askToRemove(id: string) {
    patchCard(id, { busy: "removal-preview", error: null, notice: null, menuOpen: false });
    try {
      const preview = await apiFetch<RemovalPreview>(
        `/api/v1/theses/${id}/removal-preview`, { locale });
      patchCard(id, { busy: null, preview });
    } catch (err) {
      patchCard(id, { busy: null, error: say(err) });
    }
  }

  /**
   * **الأرشفة تُخفي ولا تحذف** — ولا نقطةَ حذفٍ في الخادم أصلًا.
   *
   * و`acknowledge` يُرسَل صريحًا حين يتدلّى من الرسالة عملٌ حسمه إنسان:
   * الخادمُ يردّ بلا إقرارٍ بـ409، والمعاينةُ التي قرأها الباحث للتوّ هي
   * التي تجعل الإقرار إقرارًا لا ضغطةً ثانية.
   */
  async function confirmArchive(id: string, acknowledge: boolean) {
    patchCard(id, { busy: "archive", error: null });
    setNotice(null);
    try {
      await apiFetch(`/api/v1/theses/${id}/archive`, {
        method: "POST", locale, body: JSON.stringify({ acknowledge }),
      });
      // البطاقة تغادر القائمة الافتراضية، فالخبرُ يُقال في الصفحة.
      setCardState((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
      setError(null);
      setNotice(t("theses.archived"));
      await refresh();
    } catch (err) {
      // **والرفضُ يُقرأ في بطاقته** ومعه المعاينة التي تشرحه.
      patchCard(id, { busy: null, error: say(err) });
    }
  }

  /**
   * نقلُ ملفّ المصدر إلى السلّة — **فعلٌ آخر غير إزالة السجلّ**.
   *
   * والخادم يردّ 409 على ملفٍّ تستعمله بحوث، ومعه عددُها. فلا يُرسَل إقرارٌ
   * صامتٌ من أوّل ضغطة: يُقال ما يترتّب، ثمّ يُقرّ الباحث.
   */
  async function trashFile(id: string, fileId: string, confirm: boolean) {
    patchCard(id, { busy: "trash-file", error: null, notice: null, menuOpen: false });
    try {
      await apiFetch(`/api/v1/files/${fileId}/trash`, {
        method: "POST", locale, body: JSON.stringify({ confirm }),
      });
      patchCard(id, { busy: null, notice: t("theses.fileTrashed"),
                      trashNeedsConfirm: false });
      await refresh();
    } catch (err) {
      patchCard(id, {
        busy: null, error: say(err),
        trashNeedsConfirm: err instanceof AtheraApiError && err.status === 409,
      });
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
      {notice ? (
        <p className="provenance-note" role="status" data-testid="page-notice">
          {notice}
        </p>
      ) : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : theses.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>
          {view !== "all" || applied.trim() !== "" ? t("theses.noMatches") : t("theses.empty")}
        </p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {theses.map((thesis) => {
          const state = card(thesis.id);
          const actions = thesis.actions;
          // **فعلٌ يجري يُعطّل ما يتعارض معه** — لا ما لا علاقة له به.
          const busy = state.busy !== null;
          // **أيُّ الأفعال هو الأوّل قرارُ الخادم لا اجتهادُ الشاشة.** فلو
          // تغيّرت القاعدة يومًا — أن تسبق إعادةُ القراءة المراجعةَ في حالٍ
          // ما — تغيّرت في `card_actions.compute` وحدها، ولا يبقى هنا ترتيبٌ
          // ثانٍ يفترق عنها بصمت.
          const lead = (name: string) =>
            actions.primary === name ? PRIMARY : BUTTON;
          return (
            <article className="card" key={thesis.id} data-testid={`thesis-card-${thesis.id}`}>
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

              {/* **المؤرشَفة تقول إنّها مؤرشَفة** — لا تُعرض كأنّها في القائمة. */}
              {actions.is_archived ? (
                <div className="provenance-note" data-testid="card-archived"
                     style={{ marginBlockStart: 4 }}>
                  {t("theses.archivedBadge")}
                </div>
              ) : null}

              {/* ── الحال: محفوظةٌ في القاعدة، ونصُّها من الخادم بلغة الباحث ── */}
              <div className="metric-label" style={{ marginBlockStart: 6 }}>
                {t("theses.stateLabel")}: {thesis.processing_state_label}
                {thesis.processing_attempts > 1
                  ? ` · ${t("theses.attemptsLabel")}: ${thesis.processing_attempts}`
                  : ""}
              </div>

              {/* **وما يجري الآن يُقال، ولا يُترك زرًّا مطفأً بلا خبر.** */}
              {actions.is_running ? (
                <p
                  className="provenance-note"
                  role="status"
                  data-testid="card-running"
                  style={{ margin: "6px 0 0" }}
                >
                  {actions.blocked_reason} · {t("theses.runningNote")}
                </p>
              ) : null}

              {/* **الفشل يُقال بسببه — ولا يُعرض صفرًا صامتًا.** */}
              {thesis.failure_message ? (
                <p className="error" style={{ margin: "6px 0 0" }}>
                  {thesis.failure_message}
                </p>
              ) : null}

              {/* ═══ ما يقرؤه الباحثُ أوّلًا: جملةٌ واحدة وفعلٌ واحد ═══
                  **وثلاثُ حالاتٍ لا أكثر** في المسار السويّ: نحلّل الآن،
                  أو وجدنا أفكارًا، أو تعذّر التحليل.

                  وكانت البطاقةُ تعرض عليه عدَّ الأقسام وعدَّ الفرص وأساسَ
                  الحقوق وتاريخَ المناقشة وحالَ التنقيب — مفرداتِ نظامٍ
                  يقرؤها من بنى النظام، لا من رفع رسالته. وتفاصيلُها باقيةٌ
                  كاملةً تحت «تفاصيل الاستخراج» لمن أرادها. */}
              <div
                data-testid="card-headline"
                style={{ marginBlockStart: 8, display: "grid", gap: 8 }}
              >
                <strong style={{ fontSize: 16 }}>
                  {actions.is_running
                    ? t("theses.simpleAnalyzing")
                    : thesis.failure_code
                      ? t("theses.simpleFailed")
                      : thesis.opportunities_found > 0
                        ? t("theses.simpleReady").replace(
                            "{count}", String(thesis.opportunities_found))
                        // **والصفرُ يقوله الخادمُ بسببه، ولا تخترع الشاشةُ له
                        //   جملة.** كتبتُ هنا «اكتمل التحليل، ولا أفكارَ بعد»
                        //   فقالتها البطاقةُ عن رسالةٍ رُفعت ولم تُقرأ بعدُ
                        //   أصلًا — اختلاقٌ صغير في الموضع الذي بُنيت هذه
                        //   الشاشةُ كلُّها لمنعه. والسببُ محسوبٌ في الخادم
                        //   لستّ حالاتٍ مختلفة، فيُعرض كما قاله.
                        : thesis.opportunities_outcome_label}
                </strong>

                {/* **فعلٌ رئيسٌ واحد** — ولا زرَّ معطّلًا ولا مفردةَ نظام. */}
                {!actions.is_running && !thesis.failure_code
                    && thesis.opportunities_found > 0 ? (
                  <div>
                    <Link
                      href={`/${locale}/theses/${thesis.id}/journey`}
                      data-testid="card-view-paper-ideas"
                      style={lead("review")}
                    >
                      {t("theses.viewPaperIdeas")}
                    </Link>
                  </div>
                ) : null}
              </div>

              {/* ── وتفاصيلُ الاستخراج تُطوى ولا تُحذف ──
                  من أرادها وجدها كاملةً: أساسُ الحقوق، وتاريخُ المناقشة،
                  وعدُّ الأقسام بسببه، وسببُ عدد الفرص. */}
              <details data-testid="card-advanced" style={{ marginBlockStart: 8 }}>
                <summary className="metric-label" style={{ cursor: "pointer" }}>
                  {t("theses.extractionDetails")}
                </summary>

                <div className="metric-label" style={{ marginBlockStart: 6 }}>
                  {t("theses.rightsBasis")}:{" "}
                  {thesis.rights_basis
                    ? t(`theses.basis.${thesis.rights_basis}`)
                    : t("theses.noRights")}
                  {thesis.defended_on
                    ? ` · ${t("theses.defended")}: ${thesis.defended_on}` : ""}
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

                {/* **ومراجعةُ ما استُخرج تسكن هنا** — لا فعلًا رئيسًا.
                    الباحثُ لم يرفع رسالته ليراجع استخراجًا آليًّا؛ رفعها
                    ليعرف أيَّ الأوراق تُشتقّ منها. والمراجعةُ ضبطُ جودةٍ
                    اختياريّ، وبابُها مفتوحٌ لمن أراده. */}
                {actions.can_review ? (
                  <div style={{ marginBlockStart: 8 }}>
                    <Link
                      href={`/${locale}/theses/${thesis.id}/review`}
                      data-testid="card-review"
                    >
                      {t("theses.reviewCta")}
                    </Link>
                  </div>
                ) : null}
              </details>

              {/* ── الأفعال: ما يقوله الخادم، لا ما تجتهد فيه الشاشة ── */}
              <div style={{ display: "flex", gap: 8, marginBlockStart: 12, flexWrap: "wrap" }}>
                {actions.can_restore ? (
                  <button
                    type="button"
                    data-testid="card-restore"
                    onClick={() => void run(thesis.id, "restore", "theses.restored")}
                    disabled={busy}
                    style={{ ...lead("restore"), opacity: busy ? 0.6 : 1 }}
                  >
                    {state.busy === "restore"
                      ? t("theses.busyLabel")
                      : t("theses.restoreCta")}
                  </button>
                ) : null}

                {/* **أرفق ملفًّا** بدل «فكّك» التي تردّ `thesis.no_file`. */}
                {actions.can_attach_file ? (
                  <Link
                    href={`/${locale}/library`}
                    data-testid="card-attach-file"
                    style={lead("attach_file")}
                  >
                    {t("theses.attachFileCta")}
                  </Link>
                ) : null}

                {/* **أوّلُ قراءةٍ ليست إعادة** — والاسمُ يقول أيُّهما. */}
                {actions.can_process ? (
                  <button
                    type="button"
                    data-testid="card-process"
                    onClick={() => void run(thesis.id, "reprocess", "theses.readQueued")}
                    disabled={busy}
                    style={{ ...lead("process"), opacity: busy ? 0.6 : 1 }}
                  >
                    {state.busy === "reprocess" ? t("theses.busyLabel") : t("theses.processCta")}
                  </button>
                ) : null}

                {actions.can_reprocess ? (
                  <button
                    type="button"
                    data-testid="card-reprocess"
                    onClick={() => void run(thesis.id, "reprocess", "theses.readQueued")}
                    disabled={busy}
                    style={{ ...lead("reprocess"), opacity: busy ? 0.6 : 1 }}
                  >
                    {state.busy === "reprocess"
                      ? t("theses.busyLabel")
                      : thesis.failure_code
                        ? t("theses.retryCta")
                        : t("theses.reprocessCta")}
                  </button>
                ) : null}

                {/* ── وجهةُ الرحلة: فرصٌ قائمةٌ تُفتح ──

                    **والتنقيبُ يبدأ من نفسه بعد القراءة**، فلا يُطلب من
                    الباحث تشغيلُ ما يعمل وحده. وهذا رابطٌ إلى رسالته
                    بعينها، لا شاشةٌ يُعيد فيها اختيارها. */}
                {/* **ولا فعلان إلى الوجهة نفسها.** «اعرض أفكار الأوراق» في
                    صدر البطاقة يقود إلى الرحلة، و«اعرض فرص النشر» كانت
                    تقود إليها أيضًا بمفردةِ نظامٍ أخرى. فيبقى الأوّل. */}
                {null}

                {/* **ورحلةُ هذه الرسالة إلى ورقة** — ستُّ خطواتٍ تقول ما تمّ
                    وما ينتظر. ولا شرطَ عليها: الصفحةُ نفسُها تعرض الحالَ
                    كما هي، ورابطٌ يظهر ويختفي يُخفي الرحلةَ عمّن يحتاجها. */}
                <Link
                  href={`/${locale}/theses/${thesis.id}/journey`}
                  data-testid="card-journey"
                  style={BUTTON}
                >
                  {t("journey.cardLink")}
                </Link>

                {/* **ولا زرَّ تنقيبٍ إلّا حين تعثّر التنقيب أو كان المسارُ
                    قديمًا بلا أتمتة** — وما عداه يعمل من نفسه. */}
                {actions.can_mine ? (
                  <button
                    type="button"
                    data-testid="card-mine"
                    onClick={() => void run(thesis.id, "mine-opportunities", "theses.mined")}
                    disabled={busy}
                    style={{ ...BUTTON, opacity: busy ? 0.6 : 1 }}
                  >
                    {state.busy === "mine-opportunities"
                      ? t("theses.busyLabel")
                      : t("theses.mine")}
                  </button>
                ) : null}

                {actions.can_archive || actions.can_restore
                  || actions.can_trash_file || actions.lifecycle_blocked_reason ? (
                  <button
                    type="button"
                    data-testid="card-menu"
                    aria-haspopup="true"
                    aria-expanded={state.menuOpen}
                    onClick={() => patchCard(thesis.id, { menuOpen: !state.menuOpen })}
                    style={BUTTON}
                  >
                    {t("theses.moreActions")}
                  </button>
                ) : null}
              </div>

              {/* **وحالُ التنقيب تُقال دائمًا** — والسببُ من الخادم لا من
                  الشاشة. وتُقال أيضًا حين توجد فرص: هناك تحمل التحفّظ،
                  أنّها مبدئيّةٌ من عناصر الرسالة قبل أيّ مقابلةٍ بالأدب
                  المنشور أو حكمٍ على جِدّتها. */}
              {actions.mining_reason ? (
                <p className="provenance-note" data-testid="card-mining-note"
                   style={{ marginBlockStart: 8 }}>
                  {actions.mining_reason}
                </p>
              ) : null}

              {/* **ومنعُ إعادة القراءة يُقال حيث يقع** — لا زرٌّ مطفأ بلا تفسير. */}
              {!thesis.can_retry && thesis.retry_blocked_reason && !actions.is_running ? (
                <p className="provenance-note" data-testid="card-retry-blocked">
                  {thesis.retry_blocked_reason}
                </p>
              ) : null}

              {/* ── قائمةُ «⋯» ──
                  **مجموعةُ أزرارٍ مسمّاة، لا `role="menu"`.** ودورُ القائمة
                  يَعِد بتنقّلٍ بالأسهم لم يُبنَ، ووعدٌ في ARIA يخذل قارئ
                  الشاشة كما يخذله زرٌّ لا يفعل. */}
              {state.menuOpen ? (
                <div
                  role="group"
                  aria-label={t("theses.moreActions")}
                  data-testid="card-menu-panel"
                  style={{
                    marginBlockStart: 8, padding: 8, display: "grid", gap: 6,
                    border: "1px solid var(--border)", borderRadius: "var(--radius)",
                  }}
                >
                  {actions.can_review ? (
                    <Link
                      href={`/${locale}/theses/${thesis.id}/review`}
                      data-testid="menu-review"
                      style={{ color: "inherit" }}
                    >
                      {t("theses.reviewCta")}
                    </Link>
                  ) : null}
                  {actions.can_reprocess || actions.can_process ? (
                    <button
                      type="button"
                      data-testid="menu-reprocess"
                      disabled={busy}
                      onClick={() => void run(thesis.id, "reprocess", "theses.readQueued")}
                      style={{ ...BUTTON, textAlign: "start" }}
                    >
                      {t("theses.reprocessCta")}
                    </button>
                  ) : null}
                  {actions.can_archive ? (
                    <button
                      type="button"
                      data-testid="menu-archive"
                      disabled={busy}
                      onClick={() => void askToRemove(thesis.id)}
                      style={{ ...BUTTON, textAlign: "start" }}
                    >
                      {t("theses.archiveCta")}
                    </button>
                  ) : null}
                  {actions.can_restore ? (
                    <button
                      type="button"
                      data-testid="menu-restore"
                      disabled={busy}
                      onClick={() => void run(thesis.id, "restore", "theses.restored")}
                      style={{ ...BUTTON, textAlign: "start" }}
                    >
                      {t("theses.restoreCta")}
                    </button>
                  ) : null}
                  {actions.can_trash_file && thesis.source_file_id ? (
                    <button
                      type="button"
                      data-testid="menu-trash-file"
                      disabled={busy}
                      onClick={() =>
                        void trashFile(thesis.id, thesis.source_file_id as string, false)}
                      style={{ ...BUTTON, textAlign: "start" }}
                    >
                      {t("theses.trashFileCta")}
                    </button>
                  ) : null}
                  {/* **ولا زرَّ يَعِد بما يردّه الخادم**: أثناء عملٍ جارٍ
                      تختفي الأرشفة والسلّة معًا، ويبقى سببُهما مكتوبًا. */}
                  {actions.lifecycle_blocked_reason ? (
                    <p className="provenance-note" data-testid="menu-lifecycle-blocked"
                       style={{ margin: 0 }}>
                      {actions.lifecycle_blocked_reason}
                    </p>
                  ) : null}
                  <p className="provenance-note" style={{ margin: 0 }}>
                    {t("theses.removalDistinctNote")}
                  </p>
                </div>
              ) : null}

              {/* ── معاينةُ التبعات: تُحسب قبل السؤال، لا بعده ── */}
              {state.preview ? (
                <div
                  data-testid="removal-preview"
                  style={{
                    marginBlockStart: 8, padding: 10,
                    border: "1px solid var(--border)", borderRadius: "var(--radius)",
                  }}
                >
                  <strong>{t("theses.removalTitle")}</strong>
                  <p className="provenance-note">{state.preview.explanation}</p>
                  {state.preview.dependencies.filter((dep) => dep.count > 0).length === 0 ? (
                    <p className="metric-label" data-testid="removal-no-dependencies">
                      {t("theses.dependencyNone")}
                    </p>
                  ) : (
                    <ul style={{ margin: "4px 0", paddingInlineStart: 18 }}>
                      {state.preview.dependencies
                        .filter((dep) => dep.count > 0)
                        .map((dep) => (
                          <li key={dep.key} className="metric-label">
                            {dep.label}: {dep.count}
                            {dep.blocking ? ` · ${t("theses.dependencyBlocks")}` : ""}
                          </li>
                        ))}
                    </ul>
                  )}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {/* **والإقرارُ يُطلب حيث يقوم عليها عملٌ حسمه إنسان** —
                        ولا يُمنع الفعل: الأرشفة تُستعاد، والمطلوب أن تقع
                        بعلم. فالزرّ حاضرٌ في الحالين ونصُّه يقول أيُّهما. */}
                    <button
                      type="button"
                      data-testid="archive-confirm"
                      disabled={busy}
                      onClick={() =>
                        void confirmArchive(thesis.id,
                                            state.preview!.needs_acknowledgement)}
                      style={BUTTON}
                    >
                      {state.busy === "archive"
                        ? t("theses.busyLabel")
                        : state.preview.needs_acknowledgement
                          ? t("theses.archiveAcknowledge")
                          : t("theses.archiveConfirm")}
                    </button>
                    <button
                      type="button"
                      data-testid="archive-cancel"
                      onClick={() => patchCard(thesis.id, { preview: null })}
                      style={BUTTON}
                    >
                      {t("theses.removalCancel")}
                    </button>
                  </div>
                </div>
              ) : null}

              {/* ── خبرُ البطاقة وخطؤها: **فيها، لا في أعلى الصفحة** ── */}
              {state.notice ? (
                <p
                  className="provenance-note"
                  role="status"
                  data-testid="card-notice"
                  style={{ marginBlockStart: 8 }}
                >
                  {state.notice}
                </p>
              ) : null}
              {state.error ? (
                <p
                  className="error"
                  role="alert"
                  data-testid="card-error"
                  style={{ marginBlockStart: 8 }}
                >
                  {state.error}
                </p>
              ) : null}
              {state.trashNeedsConfirm && thesis.source_file_id ? (
                <button
                  type="button"
                  data-testid="trash-confirm"
                  disabled={busy}
                  onClick={() =>
                    void trashFile(thesis.id, thesis.source_file_id as string, true)}
                  style={BUTTON}
                >
                  {t("theses.trashConfirm")}
                </button>
              ) : null}
            </article>
          );
        })}
      </div>

      {loaded && theses.length > 0 ? (
        hasMore ? (
          <button
            type="button"
            onClick={() => void more()}
            style={{ ...BUTTON, marginBlockStart: 12 }}
          >
            {t("theses.loadMore")}
          </button>
        ) : (
          <p className="provenance-note">{t("theses.endOfList")}</p>
        )
      ) : null}

    </>
  );
}
