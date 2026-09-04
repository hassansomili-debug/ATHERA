"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  createTask,
  loadTaskSuggestions,
  loadTasks,
  updateTask,
  type Task,
  type TaskStatus,
  type TaskSuggestionsView,
  type TasksView,
} from "@/lib/projectManagement";

/**
 * مهامّ البحث — **ولوحُ مهامّ ليس ما هذا**.
 *
 * فالفرق ليس في الشكل: هنا لا يقول شيءٌ «٧٣٪ مكتمل»، ولا تدخل قائمةَ
 * الباحث مهمّةٌ لم يقبلها بيده. **والاقتراح يُعرض في قسمٍ منفصلٍ باسمه**،
 * ولا يُخلط بما ألزم به الباحث نفسه — ولو خُلطا لما عاد يميّز بينهما، فوثق
 * بالقائمة كلّها أو أهملها كلّها.
 *
 * **والمتأخّر شارةٌ لا لون**: لونٌ وحده لا يبلغ قارئ الشاشة، ولا يُقرأ في
 * لقطةٍ بالأبيض والأسود.
 *
 * **وأربع حالات عرضٍ لا تُخلط.** وأخطرها الأخيرة: طلبٌ فشل يُعرض «لا
 * مهامّ» يجعل الباحث يظنّ قائمته فارغة — والشبكة وحدها كانت معطوبة.
 */

type Load = "loading" | "ready" | "failed";

const STATUSES: TaskStatus[] = [
  "not_started",
  "in_progress",
  "awaiting_review",
  "needs_decision",
  "blocked",
  "completed",
];

export default function ProjectTasksPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<TasksView | null>(null);
  const [ideas, setIdeas] = useState<TaskSuggestionsView | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [stage, setStage] = useState("idea");

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return Promise.all([loadTasks(locale, projectId), loadTaskSuggestions(locale, projectId)])
      .then(([view, proposals]) => {
        setData(view);
        setIdeas(proposals);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, projectId, say]);

  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  const add = () => {
    if (!title.trim()) return;
    setBusy("new");
    setError(null);
    void createTask(locale, projectId, { title: title.trim(), stage })
      .then(() => {
        setTitle("");
        return refresh();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  /** **القبول فعلٌ صريح** — والخادم يردّ ٤٢٢ بدونه، والقاعدة ترفض الصفّ. */
  const accept = (key: string, taskTitle: string, taskStage: string) => {
    setBusy(key);
    setError(null);
    void createTask(locale, projectId, {
      title: taskTitle,
      stage: taskStage,
      source: "research_brain_suggestion",
      accept_suggestion: true,
    })
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const move = (task: Task, status: TaskStatus) => {
    setBusy(task.id);
    setError(null);
    void updateTask(locale, projectId, task.id, { status })
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const tasks = data?.tasks ?? [];
  const suggestions = ideas?.suggestions ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}/plan`}>{t("projectManagement.planTitle")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("projectManagement.tasksTitle")}</h1>
      <p className="metric-label">{t("projectManagement.tasksMeaning")}</p>

      <div className="card" style={{ marginBlock: "var(--space)" }}>
        <label>
          {t("projectManagement.taskTitle")}{" "}
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} />
        </label>{" "}
        <label>
          {t("projectManagement.taskStage")}{" "}
          <select value={stage} onChange={(e) => setStage(e.target.value)}>
            {[
              "idea",
              "literature_discovery",
              "gap_problem",
              "design_methodology",
              "data_preparation_collection",
              "analysis",
              "scientific_writing",
              "scientific_review",
              "journal_selection",
              "submission",
              "peer_review_revision",
              "published",
            ].map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>{" "}
        <button type="button" className="chip chip-stage" disabled={busy === "new"} onClick={add}>
          {t("projectManagement.addTask")}
        </button>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="tasks-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="tasks-failed" style={{ color: "var(--muted)" }}>
          {t("projectManagement.loadFailedNote")}
        </p>
      ) : (
        <>
          {data ? (
            <p className="metric-label">
              {t("projectManagement.openTasks")}: {data.counts.open}
              {" · "}
              {t("projectManagement.overdueTasks")}: {data.counts.overdue}
              {" · "}
              {t("projectManagement.awaitingDecision")}: {data.counts.awaiting_your_decision}
            </p>
          ) : null}

          {tasks.length === 0 ? (
            <p data-testid="tasks-empty" style={{ color: "var(--muted)" }}>
              {t("projectManagement.emptyTasks")}
            </p>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {tasks.map((task) => (
                <article className="card" key={task.id} data-testid="task-card">
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <span className="chip chip-stage">{task.status_label}</span>
                    <span className="chip chip-muted">{task.stage_label}</span>
                    <span className="chip chip-muted">{task.priority_label}</span>
                    {/* **شارةٌ لا لون** — واللون وحده لا يبلغ قارئ الشاشة. */}
                    {task.is_overdue ? (
                      <span className="chip chip-muted" data-testid="task-overdue">
                        {t("projectManagement.overdueBadge")}
                      </span>
                    ) : null}
                    {task.suggested_by_system ? (
                      <span className="chip chip-muted">{task.source_label}</span>
                    ) : null}
                  </div>

                  <strong style={{ display: "block", marginBlockStart: 6 }}>{task.title}</strong>
                  <p className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("projectManagement.assignee")}:{" "}
                    {task.assignee_name ?? t("projectManagement.unassigned")}
                    {" · "}
                    {t("projectManagement.taskDue")}:{" "}
                    {task.due_at ? task.due_at.slice(0, 10) : t("common.none")}
                  </p>

                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBlockStart: 8 }}>
                    {STATUSES.map((status) => (
                      <button
                        key={status}
                        type="button"
                        className={task.status === status ? "chip chip-stage" : "chip chip-muted"}
                        aria-label={`${t("projectManagement.changeStatus")} ${status}: ${task.title}`}
                        aria-pressed={task.status === status}
                        disabled={busy === task.id || task.status === status}
                        onClick={() => move(task, status)}
                      >
                        {status}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}

          {/* ── الاقتراحات في قسمٍ منفصلٍ باسمه، ولا تُخلط بما التزم به الباحث ── */}
          <h2>{t("projectManagement.suggestionsTitle")}</h2>
          <p className="metric-label">{ideas?.note ?? t("projectManagement.suggestionsNote")}</p>
          {suggestions.length === 0 ? (
            <p data-testid="suggestions-empty" style={{ color: "var(--muted)" }}>
              {t("projectManagement.emptySuggestions")}
            </p>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {suggestions.map((item) => (
                <article className="card" key={item.key} data-testid="suggestion-card">
                  <strong>{item.title_ar}</strong>
                  {/* **السبب يشير إلى عددٍ في القاعدة** — لا اقتراحَ بلا سببه. */}
                  <p className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("projectManagement.why")}: {item.why_ar}
                  </p>
                  <button
                    type="button"
                    className="chip chip-stage"
                    aria-label={`${t("projectManagement.acceptSuggestion")}: ${item.title_ar}`}
                    disabled={busy === item.key}
                    onClick={() => accept(item.key, item.title_ar, item.stage)}
                  >
                    {t("projectManagement.acceptSuggestion")}
                  </button>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
