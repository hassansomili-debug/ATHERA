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

interface Editing {
  row: MatrixRow;
  cell: MatrixCell;
  state: CellState;
  scope: SourceScope;
  value: string;
  quote: string;
  locator: string;
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
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Editing | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return loadMatrix(locale, projectId)
      .then((view) => {
        setData(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, projectId, say]);

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
    });

  const save = () => {
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
    setBusy(true);
    setError(null);
    void setMatrixCell(locale, projectId, editing.row.source_id, editing.cell.field_key, {
      cell_state: editing.state,
      source_scope: editing.scope,
      // **الغياب غيابٌ لا فراغٌ يُملأ**: «غير مذكور» تُرسَل بلا قيمة ولا
      // شاهد، فلا يبقى في القاعدة نصٌّ بجانب حالٍ تنفيه.
      value_ar: missing ? null : editing.value,
      evidence_quote: quote,
      evidence_locator: locator,
    })
      .then(() => {
        setEditing(null);
        return refresh();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  const review = (row: MatrixRow, cell: MatrixCell, verdict: "approved" | "rejected" | "unknown") => {
    setBusy(true);
    setError(null);
    void verifyMatrixCell(locale, projectId, row.source_id, cell.field_key, verdict)
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  const rows = data?.rows ?? [];
  const fields = data?.fields ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}/screening`}>{t("screening.title")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("matrix.title")}</h1>
      <p className="metric-label">{t("matrix.includedOnlyNote")}</p>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

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
        // الجدول يجرّ نفسه أفقيًّا — ستة عشر عمودًا لا تتّسع لها شاشة.
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
                          {cell.cell_state !== "missing" &&
                          cell.verification_status === "unverified" ? (
                            <button
                              type="button"
                              className="chip chip-muted"
                              disabled={busy}
                              aria-label={`${t("matrix.verification_approved")}: ${t(`matrix.field_${cell.field_key}`)} — ${describe(row)}`}
                              onClick={() => review(row, cell, "approved")}
                            >
                              {t("matrix.confirmCell")}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
                    </>
                  )}
                </>
              )}
            </>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlockStart: 8 }}>
            <button
              type="button"
              className="chip chip-stage"
              disabled={busy || (editing.state !== "missing" && !editing.value.trim())}
              onClick={save}
            >
              {t("common.save")}
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
