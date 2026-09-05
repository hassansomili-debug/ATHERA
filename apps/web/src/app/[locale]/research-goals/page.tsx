"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * أهدافي البحثية وقيودي | Research Goals and Constraints (§12).
 *
 * **والهدفُ ليس وعدًا.** لا شريطَ تقدّمٍ هنا، ولا نسبةَ إنجاز، ولا موعدٌ
 * محسوبٌ من نيّةٍ كتبها الباحث. ونصُّ الشاشة يقول ذلك صراحةً بدل أن يُترك
 * للتأويل.
 *
 * **وغيابُ القيد «غيرُ معروف»، لا «لا قيد»** — وهو فرقٌ مكتوبٌ في الشاشة
 * لأنّ قراءتَه خطأً تُنتج توصيةً بما تمنعه ميزانيّةٌ لم يسألها أحد.
 */

interface Goal {
  id: string;
  goal_type: string;
  target: string;
  priority: string;
  timeframe: string | null;
  status: string;
  researcher_confirmed: boolean;
  notes: string | null;
}

interface Constraint {
  id: string;
  constraint_type: string;
  value: string;
  notes: string | null;
  researcher_confirmed: boolean;
}

const GOAL_TYPES = [
  "publication", "promotion", "funding", "collaboration",
  "skill", "visibility", "thesis", "other",
] as const;

const PRIORITIES = ["high", "medium", "low"] as const;

const CONSTRAINT_TYPES = [
  "time", "publication_budget", "no_fee_preference", "language",
  "data_availability", "institutional", "deadline", "methodological",
  "geography_community", "collaboration",
] as const;

export default function ResearchGoalsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [goals, setGoals] = useState<Goal[]>([]);
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const [goalType, setGoalType] = useState<string>("publication");
  const [goalTarget, setGoalTarget] = useState("");
  const [goalPriority, setGoalPriority] = useState<string>("medium");
  const [goalTimeframe, setGoalTimeframe] = useState("");

  const [constraintType, setConstraintType] = useState<string>("time");
  const [constraintValue, setConstraintValue] = useState("");

  const load = useCallback(async () => {
    try {
      const [everyGoal, everyConstraint] = await Promise.all([
        apiFetch<Goal[]>("/api/v1/researcher/goals", { locale }),
        apiFetch<Constraint[]>("/api/v1/researcher/constraints", { locale }),
      ]);
      setGoals(everyGoal);
      setConstraints(everyConstraint);
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function addGoal(event: React.FormEvent) {
    event.preventDefault();
    setBusyId("new-goal");
    setError(null);
    try {
      await apiFetch("/api/v1/researcher/goals", {
        method: "POST",
        locale,
        body: JSON.stringify({
          goal_type: goalType,
          target: goalTarget,
          priority: goalPriority,
          timeframe: goalTimeframe || null,
          researcher_confirmed: true,
        }),
      });
      setGoalTarget("");
      setGoalTimeframe("");
      await load();
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function addConstraint(event: React.FormEvent) {
    event.preventDefault();
    setBusyId("new-constraint");
    setError(null);
    try {
      await apiFetch("/api/v1/researcher/constraints", {
        method: "POST",
        locale,
        body: JSON.stringify({
          constraint_type: constraintType,
          value: constraintValue,
          researcher_confirmed: true,
        }),
      });
      setConstraintValue("");
      await load();
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function remove(kind: "goals" | "constraints", id: string) {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/researcher/${kind}/${id}`, { method: "DELETE", locale });
      await load();
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("researchGoals.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>
        {t("researchGoals.subtitle")}
      </p>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {/* ══ الأهداف ══ */}
      <h2>{t("researchGoals.goals")}</h2>
      <p className="provenance-note">{t("researchGoals.goalsNote")}</p>
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : goals.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("researchGoals.goalsEmpty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {goals.map((goal) => (
          <article className="card" key={goal.id} data-testid="research-goal">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <strong>{goal.target}</strong>
              <span className="chip chip-muted">
                {t(`researchGoals.goalTypes.${goal.goal_type}`)}
              </span>
            </div>
            <p className="metric-label">
              {t("researchGoals.priority")}: {t(`researchGoals.priorities.${goal.priority}`)}
              {" · "}
              {t("researchGoals.status")}: {t(`researchGoals.statuses.${goal.status}`)}
              {goal.timeframe ? ` · ${t("researchGoals.timeframe")}: ${goal.timeframe}` : ""}
            </p>
            <div className="actions">
              <button
                type="button"
                disabled={busyId === goal.id}
                onClick={() => void remove("goals", goal.id)}
              >
                {t("researchGoals.remove")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <form className="form" onSubmit={(event) => void addGoal(event)}>
        <div>
          <label htmlFor="new-goal-type">{t("researchGoals.goalType")}</label>
          <select
            id="new-goal-type"
            value={goalType}
            onChange={(event) => setGoalType(event.target.value)}
          >
            {GOAL_TYPES.map((kind) => (
              <option value={kind} key={kind}>
                {t(`researchGoals.goalTypes.${kind}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="new-goal-target">{t("researchGoals.target")}</label>
          <input
            id="new-goal-target"
            value={goalTarget}
            onChange={(event) => setGoalTarget(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="new-goal-priority">{t("researchGoals.priority")}</label>
          <select
            id="new-goal-priority"
            value={goalPriority}
            onChange={(event) => setGoalPriority(event.target.value)}
          >
            {PRIORITIES.map((level) => (
              <option value={level} key={level}>
                {t(`researchGoals.priorities.${level}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="new-goal-timeframe">
            {t("researchGoals.timeframe")} ({t("researchGoals.optional")})
          </label>
          <input
            id="new-goal-timeframe"
            value={goalTimeframe}
            onChange={(event) => setGoalTimeframe(event.target.value)}
          />
        </div>
        <div className="actions">
          <button type="submit" disabled={busyId === "new-goal" || !goalTarget.trim()}>
            {t("researchGoals.addGoal")}
          </button>
        </div>
      </form>

      {/* ══ القيود ══ */}
      <h2>{t("researchGoals.constraints")}</h2>
      <p className="provenance-note">{t("researchGoals.constraintsNote")}</p>
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : constraints.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("researchGoals.constraintsEmpty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {constraints.map((constraint) => (
          <article className="card" key={constraint.id} data-testid="research-constraint">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <strong>{constraint.value}</strong>
              <span className="chip chip-muted">
                {t(`researchGoals.constraintTypes.${constraint.constraint_type}`)}
              </span>
            </div>
            <div className="actions">
              <button
                type="button"
                disabled={busyId === constraint.id}
                onClick={() => void remove("constraints", constraint.id)}
              >
                {t("researchGoals.remove")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <form className="form" onSubmit={(event) => void addConstraint(event)}>
        <div>
          <label htmlFor="new-constraint-type">{t("researchGoals.constraintType")}</label>
          <select
            id="new-constraint-type"
            value={constraintType}
            onChange={(event) => setConstraintType(event.target.value)}
          >
            {CONSTRAINT_TYPES.map((kind) => (
              <option value={kind} key={kind}>
                {t(`researchGoals.constraintTypes.${kind}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="new-constraint-value">{t("researchGoals.value")}</label>
          <input
            id="new-constraint-value"
            value={constraintValue}
            onChange={(event) => setConstraintValue(event.target.value)}
          />
        </div>
        <div className="actions">
          <button
            type="submit"
            disabled={busyId === "new-constraint" || !constraintValue.trim()}
          >
            {t("researchGoals.addConstraint")}
          </button>
        </div>
      </form>
    </>
  );
}
