"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  type CellState,
  type MatrixCell,
  type MatrixRow,
  type MatrixView,
  type SourceScope,
  describe,
  extractMatrix,
  loadMatrix,
  setMatrixCell,
  verifyMatrixCell,
} from "@/lib/screening";

/**
 * مصفوفة الأدبيات — **وما لم يُقرأ لا يُكتب**.
 *
 * مصفوفةٌ تُملأ بالتخمين أسوأ من مصفوفةٍ فارغة: الفارغة تُظهر الفجوة،
 * والمخمَّنة تُخفيها ثم تُنقل إلى قسم المنهجية. فكل خانةٍ هنا تقول شيئين
 * لا واحدًا: ما وُجد، **ومن أين قُرئ**.
 *
 * و«غير مذكور» ليست خانةً بيضاء. الخانة البيضاء تُقرأ «لا شيء يستحق
 * الذكر»، و«غير مذكور» تُقرأ «لم تذكره الدراسة» — والثانية وحدها فجوةٌ
 * يعرف الباحث أنّ عليه أن يعالجها. ومقياسٌ غائب يبقى غائبًا: لا يُخترع له
 * اسم، ولا يُنسب إلى الدراسة ما لم تقله.
 *
 * **ومَدى القراءة يُعرض في الخانة نفسها**، لا في حاشيةٍ أسفل الصفحة: من
 * قرأ ملخّصًا وحده يرى ذلك مكتوبًا في كل خانةٍ ملأها منه.
 *
 * **والقراءة الآلية تقترح ولا تعتمد.** ما تكتبه يظهر «ينتظر مراجعتك»
 * و«اقتراح آليّ»، ويُراجَع بالمسار نفسه الذي تُراجَع به مرشّحات الذاكرة
 * الموثقة: اعتماد، أو تعديلٌ ثم اعتماد، أو رفض، أو «لم تذكرها الدراسة».
 * ولا نظامَ اعتمادٍ ثانٍ يُبنى بجانب الأول.
 */

type Load = "loading" | "ready" | "failed";

const STATE_LABEL: Record<CellState, string> = {
  known: "matrix.stateKnown",
  needs_review: "matrix.stateNeedsReview",
  missing: "matrix.stateMissing",
  conflicting: "matrix.stateConflicting",
};

const SCOPE_LABEL: Record<SourceScope, string> = {
  metadata_only: "matrix.scopeMetadata",
  abstract_only: "matrix.scopeAbstract",
  full_text: "matrix.scopeFullText",
};

const SCOPES: SourceScope[] = ["metadata_only", "abstract_only", "full_text"];
const STATES: CellState[] = ["known", "needs_review", "missing", "conflicting"];

/** المُحدِّد الوحيد المسموح لخانةٍ قُرئت من ملخّص — ولا صفحة لملخّص. */
const ABSTRACT_LOCATOR = "abstract";

const PAGE_SIZE = 25;

interface Editing {
  row: MatrixRow;
  cell: MatrixCell;
  state: CellState;
  scope: SourceScope;
  value: string;
  quote: string;
  locator: string;
  page: string;
  section: string;
}

export default function LiteratureMatrixPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<MatrixView | null>(null);
  const [page, setPage] = useState(1);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Editing | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(
    (which: number) => {
      setLoad("loading");
      setError(null);
      return loadMatrix(locale, projectId, which, PAGE_SIZE)
        .then((view) => {
          setData(view);
          setLoad("ready");
        })
        .catch((err: unknown) => {
          setError(say(err));
          setLoad("failed");
        });
    },
    [locale, projectId, say],
  );

  // **لا حالة تُضبط داخل التأثير مباشرةً** — والوعد المؤجّل يجعل الترتيب صريحًا.
  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh(page);
    });
    return () => {
      alive = false;
    };
  }, [refresh, page]);

  const rows = data?.rows ?? [];
  const fields = data?.fields ?? [];
  const reload = () => refresh(page);

  const openEditor = (row: MatrixRow, cell: MatrixCell) =>
    setEditing({
      row,
      cell,
      state: cell.cell_state,
      // المدى الابتدائي هو ما تسمح به الدراسة، لا أعلى ما في القائمة.
      scope: cell.source_scope,
      value: cell.value_ar ?? "",
      quote: cell.evidence_quote ?? "",
      locator: cell.evidence_locator ?? "",
      page: cell.evidence_page === null ? "" : String(cell.evidence_page),
      section: cell.evidence_section ?? "",
    });

  /**
   * الحفظ — و`approveAfter` هي «تعديلٌ ثم اعتماد» من نمط المراجعة القائم.
   *
   * **والكتابة تُبطل المراجعة السابقة دائمًا** (يفرضه الخادم)، فالاعتماد
   * فعلٌ ثانٍ يقع بعدها. ولو تعذّر الثاني بقيت القيمة محفوظةً «تنتظر
   * مراجعتك» ويُعلَن الخطأ — لا تُحفظ معتمَدةً بلا اعتماد وقع.
   */
  const save = (approveAfter: boolean) => {
    if (!editing) return;
    const missing = editing.state === "missing";
    // §14.5 — لا نصّ فلا مقتطف: بياناتٌ وصفية لا يُقتبس منها شيء.
    const quote =
      missing || editing.scope === "metadata_only" || !editing.quote.trim()
        ? null
        : editing.quote.trim();
    // **ولا رقم صفحةٍ يُخترع.** ملخّصٌ لا صفحات له، فموضعه كلمةٌ ثابتة؛
    // وبياناتٌ وصفية لا موضع لها أصلًا.
    const locator = (() => {
      if (quote === null) return null;
      if (editing.scope === "abstract_only") return ABSTRACT_LOCATOR;
      return editing.locator.trim() ? editing.locator.trim() : null;
    })();
    // الصفحة والقسم من النصّ الكامل وحده — ومجهولُ الصفحة يبقى فارغًا.
    const parsedPage = Number.parseInt(editing.page, 10);
    const pageNumber =
      !missing && editing.scope === "full_text" && Number.isFinite(parsedPage)
        ? parsedPage
        : null;
    const section =
      !missing && editing.scope === "full_text" && editing.section.trim()
        ? editing.section.trim()
        : null;

    setBusy(true);
    setError(null);
    setNotice(null);
    const row = editing.row;
    const fieldKey = editing.cell.field_key;
    void setMatrixCell(locale, projectId, row.source_id, fieldKey, {
      cell_state: editing.state,
      source_scope: editing.scope,
      // **الغياب غيابٌ لا فراغٌ يُملأ**: «غير مذكور» تُرسَل بلا قيمة ولا
      // شاهد، فلا يبقى في القاعدة نصٌّ بجانب حالٍ تنفيه.
      value_ar: missing ? null : editing.value,
      evidence_quote: quote,
      evidence_locator: locator,
      evidence_page: pageNumber,
      evidence_section: section,
    })
      .then(() => {
        setEditing(null);
        if (!approveAfter || missing) return reload();
        return verifyMatrixCell(locale, projectId, row.source_id, fieldKey, "approved")
          .then(() => reload());
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  const review = (
    row: MatrixRow,
    cell: MatrixCell,
    verdict: "approved" | "rejected" | "unknown",
  ) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    void verifyMatrixCell(locale, projectId, row.source_id, cell.field_key, verdict)
      .then(() => reload())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  /**
   * «لم تذكرها الدراسة» — **حكمٌ على الدراسة لا على الخانة**.
   *
   * فتُكتب الخانة `missing` بلا قيمةٍ ولا شاهد: ما لم تقله الورقة لا يُكتب
   * عنها. وهي غير «لا أستطيع الحكم»، وتلك حكمٌ على قدرتنا لا على الورقة.
   */
  const markNotStated = (row: MatrixRow, cell: MatrixCell) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    void setMatrixCell(locale, projectId, row.source_id, cell.field_key, {
      cell_state: "missing",
      source_scope: cell.source_scope,
      value_ar: null,
      evidence_quote: null,
      evidence_locator: null,
      evidence_page: null,
      evidence_section: null,
    })
      .then(() => reload())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  /**
   * القراءة الآلية لصفّ أو للصفحة — **مقترحاتٌ لا معرفة**.
   *
   * والنتيجة تُقال بالأرقام: كم خانةً اقتُرحت، وكم لم تذكرها الدراسة، وكم
   * خانةً لك لم تُمسّ. و«تمّ» وحدها لا تقول شيئًا يُتصرَّف على أساسه.
   */
  const readAutomatically = (sourceIds: string[]) => {
    if (sourceIds.length === 0) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    void extractMatrix(locale, projectId, sourceIds)
      .then((result) => {
        const filled = result.results.reduce((sum, one) => sum + one.filled, 0);
        const gaps = result.results.reduce((sum, one) => sum + one.marked_missing, 0);
        const kept = result.results.reduce(
          (sum, one) => sum + one.left_to_the_researcher,
          0,
        );
        const nothing = result.results.every(
          (one) => one.scope === "metadata_only",
        );
        setNotice(
          nothing
            ? t("matrix.extractNothingToRead")
            : `${t("matrix.extractDone")} — ${filled} ${t("matrix.extractedFilled")} · ` +
              `${gaps} ${t("matrix.extractedMissing")} · ${kept} ${t("matrix.extractedKept")}`,
        );
        return reload();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}/screening`}>{t("screening.title")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("matrix.title")}</h1>
      <p className="metric-label">{t("matrix.includedOnlyNote")}</p>
      <p className="metric-label">{t("matrix.extractNote")}</p>

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
        <p data-testid="matrix-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="matrix-failed" style={{ color: "var(--muted)" }}>
          {t("matrix.loadFailedNote")}
        </p>
      ) : rows.length === 0 ? (
        <p data-testid="matrix-empty" style={{ color: "var(--muted)" }}>
          {t("matrix.empty")}{" "}
          <Link href={`/${locale}/portfolio/${projectId}/screening`}>{t("matrix.emptyCta")}</Link>
        </p>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlock: 8 }}>
            <button
              type="button"
              className="chip chip-stage"
              disabled={busy}
              onClick={() => readAutomatically(rows.map((row) => row.source_id))}
            >
              {t("matrix.extractPage")}
            </button>
            <span className="metric-label">
              {data?.total ?? 0} {t("matrix.rowsLabel")}
            </span>
          </div>

          {/* الجدول يجرّ نفسه أفقيًّا — ستة عشر عمودًا لا تتّسع لها شاشة. */}
          <div style={{ overflowX: "auto" }}>
            <table>
              <caption className="metric-label">{data?.note_ar}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("matrix.field_reference")}</th>
                  {fields
                    .filter((field) => field !== "reference")
                    .map((field) => (
                      <th key={field} scope="col">
                        {t(`matrix.field_${field}`)}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.source_id}>
                    <th scope="row" style={{ textAlign: "start", minInlineSize: 220 }}>
                      {describe(row)}
                      <div className="metric-label">{t(SCOPE_LABEL[row.reading_scope])}</div>
                      <button
                        type="button"
                        className="chip chip-muted"
                        disabled={busy || row.reading_scope === "metadata_only"}
                        aria-label={`${t("matrix.extract")}: ${describe(row)}`}
                        onClick={() => readAutomatically([row.source_id])}
                      >
                        {t("matrix.extract")}
                      </button>
                    </th>
                    {row.cells
                      .filter((cell) => cell.field_key !== "reference")
                      .map((cell) => (
                        <td key={cell.field_key} style={{ minInlineSize: 200, verticalAlign: "top" }}>
                          {/* الحال أولًا ثم القيمة: من يقرأ الخانة يعرف قبل
                              كل شيء أهي معلومة أم غياب. */}
                          <div className="metric-label">{t(STATE_LABEL[cell.cell_state])}</div>
                          {cell.cell_state === "missing" ? (
                            <span style={{ color: "var(--muted)" }}>{t("matrix.notStated")}</span>
                          ) : (
                            <span>{cell.value_ar}</span>
                          )}
                          {/* **«تم التحليل من الملخص فقط» ليست حاشية.** هي أهمّ
                              ما في الخانة: بها يعرف الباحث أنّ ما أمامه ليس
                              قراءةَ ورقةٍ كاملة. */}
                          <div className="metric-label">{t(SCOPE_LABEL[cell.source_scope])}</div>
                          <div className="metric-label">
                            {t(`matrix.method_${cell.extraction_method}`)} ·{" "}
                            {t(`matrix.verification_${cell.verification_status}`)}
                          </div>
                          {/* **من أي ملخّصٍ قُرئت ومن أرسله.** «من ملخّص»
                              مجهولِ المرسِل لا يُراجَع: الباحث يفتح النصّ
                              المنسوب فيقابل القيمة به. */}
                          {cell.abstract_provider ? (
                            <div className="metric-label">
                              {t("matrix.fromAbstractOf")} {cell.abstract_provider}
                            </div>
                          ) : null}
                          {cell.evidence_page !== null || cell.evidence_section ? (
                            <div className="metric-label">
                              {cell.evidence_page !== null
                                ? `${t("matrix.pageLabel")} ${cell.evidence_page}`
                                : ""}
                              {cell.evidence_page !== null && cell.evidence_section ? " · " : ""}
                              {cell.evidence_section
                                ? `${t("matrix.sectionLabel")} ${cell.evidence_section}`
                                : ""}
                            </div>
                          ) : null}
                          {cell.evidence_quote ? (
                            <blockquote style={{ margin: "4px 0" }}>
                              «{cell.evidence_quote}»
                              {cell.evidence_locator ? (
                                <span className="metric-label">
                                  {" "}
                                  {cell.evidence_locator === ABSTRACT_LOCATOR
                                    ? t("matrix.locatorAbstract")
                                    : cell.evidence_locator}
                                </span>
                              ) : null}
                            </blockquote>
                          ) : null}
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBlockStart: 4 }}>
                            <button
                              type="button"
                              className="chip chip-muted"
                              disabled={busy}
                              /* الاسم يسمّي عموده ودراسته — في الجدول مئات
                                 الأزرار المتطابقة الاسم. */
                              aria-label={`${t("matrix.edit")}: ${t(`matrix.field_${cell.field_key}`)} — ${describe(row)}`}
                              onClick={() => openEditor(row, cell)}
                            >
                              {t("matrix.edit")}
                            </button>
                            {/* **الحكم فعلٌ ثانٍ مستقلّ عن الكتابة**، وهو نمط
                                المراجعة القائم في المنصّة نفسه: اعتماد، أو
                                تعديلٌ ثم اعتماد (بالتحرير ثم «احفظ واعتمد»)،
                                أو رفض، أو «لم تذكرها الدراسة». و«لا أستطيع
                                الحكم» باقيةٌ معها من الترحيل 0016: من راجع
                                ولم يحسم **لم يرفض**، وخلطُهما يجعل التردّد
                                يبدو بطلانًا. */}
                            {cell.cell_state !== "missing" &&
                            cell.verification_status === "unverified" ? (
                              <>
                                {(["approved", "rejected", "unknown"] as const).map((verdict) => (
                                  <button
                                    key={verdict}
                                    type="button"
                                    className="chip chip-muted"
                                    disabled={busy}
                                    aria-label={`${t(`matrix.verification_${verdict}`)}: ${t(`matrix.field_${cell.field_key}`)} — ${describe(row)}`}
                                    onClick={() => review(row, cell, verdict)}
                                  >
                                    {t(`matrix.verdict_${verdict}`)}
                                  </button>
                                ))}
                                <button
                                  type="button"
                                  className="chip chip-muted"
                                  disabled={busy}
                                  aria-label={`${t("matrix.verdict_edit_then_approve")}: ${t(`matrix.field_${cell.field_key}`)} — ${describe(row)}`}
                                  onClick={() => openEditor(row, cell)}
                                >
                                  {t("matrix.verdict_edit_then_approve")}
                                </button>
                                <button
                                  type="button"
                                  className="chip chip-muted"
                                  disabled={busy}
                                  aria-label={`${t("matrix.verdict_not_stated")}: ${t(`matrix.field_${cell.field_key}`)} — ${describe(row)}`}
                                  onClick={() => markNotStated(row, cell)}
                                >
                                  {t("matrix.verdict_not_stated")}
                                </button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav
            aria-label={t("common.page")}
            style={{ display: "flex", gap: 8, alignItems: "center", marginBlockStart: 12 }}
          >
            <button
              type="button"
              className="chip chip-muted"
              disabled={(data?.page ?? 1) <= 1 || busy}
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
              disabled={(data?.page ?? 1) >= (data?.pages ?? 1) || busy}
              onClick={() => setPage((data?.page ?? 1) + 1)}
            >
              {t("common.next")}
            </button>
          </nav>
        </>
      )}

      {editing ? (
        <div
          className="card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="cell-editor-title"
          style={{ marginBlockStart: 16 }}
        >
          <strong id="cell-editor-title">
            {t(`matrix.field_${editing.cell.field_key}`)} — {describe(editing.row)}
          </strong>
          <p className="metric-label">
            {t("matrix.availableScope")}: {t(SCOPE_LABEL[editing.row.reading_scope])}
          </p>

          <label htmlFor="cell-state" style={{ display: "block", marginBlockStart: 8 }}>
            {t("matrix.stateLabel")}
          </label>
          <select
            id="cell-state"
            value={editing.state}
            onChange={(event) =>
              setEditing({ ...editing, state: event.target.value as CellState })
            }
          >
            {STATES.map((state) => (
              <option key={state} value={state}>
                {t(STATE_LABEL[state])}
              </option>
            ))}
          </select>

          <label htmlFor="cell-scope" style={{ display: "block", marginBlockStart: 8 }}>
            {t("matrix.scopeLabel")}
          </label>
          {/* **لا يُعرض مدًى لا تسمح به الدراسة.** خيارٌ يُعرض ثم يُردّ من
              الخادم يُعلّم الباحث أن الشاشة تكذب؛ فيُحذف من القائمة أصلًا. */}
          <select
            id="cell-scope"
            value={editing.scope}
            onChange={(event) =>
              setEditing({ ...editing, scope: event.target.value as SourceScope })
            }
          >
            {SCOPES.filter(
              (scope) => SCOPES.indexOf(scope) <= SCOPES.indexOf(editing.row.reading_scope),
            ).map((scope) => (
              <option key={scope} value={scope}>
                {t(SCOPE_LABEL[scope])}
              </option>
            ))}
          </select>

          {editing.state === "missing" ? (
            <p style={{ marginBlockStart: 8 }}>{t("matrix.missingExplains")}</p>
          ) : (
            <>
              <label htmlFor="cell-value" style={{ display: "block", marginBlockStart: 8 }}>
                {t("matrix.valueLabel")}
              </label>
              <textarea
                id="cell-value"
                rows={3}
                value={editing.value}
                onChange={(event) => setEditing({ ...editing, value: event.target.value })}
              />

              {editing.scope === "metadata_only" ? (
                <p className="metric-label">{t("matrix.noQuoteFromMetadata")}</p>
              ) : (
                <>
                  <label htmlFor="cell-quote" style={{ display: "block", marginBlockStart: 8 }}>
                    {t("matrix.quoteLabel")}
                  </label>
                  <textarea
                    id="cell-quote"
                    rows={2}
                    value={editing.quote}
                    onChange={(event) => setEditing({ ...editing, quote: event.target.value })}
                  />
                  {editing.scope === "abstract_only" ? (
                    // ملخّصٌ لا صفحات له — فالموضع ثابتٌ ولا يُكتب رقمًا.
                    <p className="metric-label">{t("matrix.locatorIsAbstract")}</p>
                  ) : (
                    <>
                      <label htmlFor="cell-locator" style={{ display: "block", marginBlockStart: 8 }}>
                        {t("matrix.locatorLabel")}
                      </label>
                      <input
                        id="cell-locator"
                        value={editing.locator}
                        onChange={(event) =>
                          setEditing({ ...editing, locator: event.target.value })
                        }
                      />
                      {/* **الصفحة تُكتب حين تُعرف، وتُترك فارغةً حين لا تُعرف.**
                          ورقمٌ مخمَّن يُرسل القارئ إلى صفحةٍ لا تحمل ما نُسب
                          إليها — والفراغ أصدق من رقمٍ لم يُقرأ. */}
                      <label htmlFor="cell-page" style={{ display: "block", marginBlockStart: 8 }}>
                        {t("matrix.pageInputLabel")}
                      </label>
                      <input
                        id="cell-page"
                        inputMode="numeric"
                        value={editing.page}
                        onChange={(event) => setEditing({ ...editing, page: event.target.value })}
                      />
                      <label htmlFor="cell-section" style={{ display: "block", marginBlockStart: 8 }}>
                        {t("matrix.sectionInputLabel")}
                      </label>
                      <input
                        id="cell-section"
                        value={editing.section}
                        onChange={(event) =>
                          setEditing({ ...editing, section: event.target.value })
                        }
                      />
                    </>
                  )}
                  {editing.scope !== "full_text" ? (
                    <p className="metric-label">{t("matrix.pageOnlyFromFullText")}</p>
                  ) : null}
                </>
              )}
            </>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 8 }}>
            <button
              type="button"
              className="chip chip-stage"
              disabled={busy || (editing.state !== "missing" && !editing.value.trim())}
              onClick={() => save(false)}
            >
              {t("common.save")}
            </button>
            {/* «تعديلٌ ثم اعتماد» — فعلٌ واحد للباحث، وكتابةٌ ثم حكمٌ في
                الخادم: القيمة تُحفظ أولًا مرشَّحة، ثم يُنسب الاعتماد إليه
                باسمه ووقته. ولا تُكتب معتمَدةً بأثرٍ جانبي للحفظ. */}
            <button
              type="button"
              className="chip chip-stage"
              disabled={busy || editing.state === "missing" || !editing.value.trim()}
              onClick={() => save(true)}
            >
              {t("matrix.saveAndApprove")}
            </button>
            <button type="button" className="chip chip-muted" onClick={() => setEditing(null)}>
              {t("project.cancel")}
            </button>
          </div>
          <p className="metric-label">{t("matrix.savedStaysCandidate")}</p>
        </div>
      ) : null}
    </>
  );
}
