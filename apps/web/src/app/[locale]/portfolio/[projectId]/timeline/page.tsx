"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  loadStageHistory,
  loadTimeline,
  setMilestone,
  updatePlan,
  type StageHistory,
  type Timeline,
} from "@/lib/projectManagement";

/**
 * الخطُّ الزمني — **مواعيدُ يضعها الباحث لنفسه، لا رقابةٌ على ساعاته**.
 *
 * فلا ساعةَ عملٍ هنا ولا «كم قضيتَ في هذه المهمّة»: تتبّعُ الوقت خارج
 * نطاق هذا العمل عمدًا، وإدخالُه يحوّل أداةَ بحثٍ إلى أداةِ مراقبة.
 *
 * **واعتمادُ المَعْلَم فعلُ إنسانٍ يُنسب إليه** — ولا يُستنتج من فتح هذه
 * الصفحة. ولو استُنتج لصار «اكتملت مراجعة الأدبيات» مكتوبًا في سجلٍّ لأن
 * أحدًا مرّ من هنا.
 *
 * **وتاريخُ المراحل يُعرض كما وقع**، والعودة إلى مرحلةٍ سابقة تُسمّى
 * «عودة» لا «تراجعًا»: التحليل قد يكشف عيبًا في التصميم، وذلك هو الصواب
 * العلميّ. ومع كل اعتمادٍ يُعرض ما كانت المنصّة تقترحه حينها — فيُقرأ بعد
 * شهرٍ أنّ الباحث خالف الاقتراح، لا أنّ الاقتراح لم يكن.
 */

type Load = "loading" | "ready" | "failed";

export default function ProjectTimelinePage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<Timeline | null>(null);
  const [history, setHistory] = useState<StageHistory | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [target, setTarget] = useState("");

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return Promise.all([loadTimeline(locale, projectId), loadStageHistory(locale, projectId)])
      .then(([view, past]) => {
        setData(view);
        setHistory(past);
        setStart(view.start_date ?? "");
        setTarget(view.target_completion_date ?? "");
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

  const saveDates = () => {
    setBusy("dates");
    setError(null);
    void updatePlan(locale, projectId, {
      start_date: start || null,
      clear_start_date: !start,
      target_completion_date: target || null,
      clear_target_completion_date: !target,
    })
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const toggle = (key: string, completed: boolean) => {
    setBusy(key);
    setError(null);
    void setMilestone(locale, projectId, key, { completed })
      .then(() => refresh())
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(null));
  };

  const milestones = data?.milestones ?? [];
  const events = history?.events ?? [];

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}/plan`}>{t("projectManagement.planTitle")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("projectManagement.timelineTitle")}</h1>
      <p className="metric-label">{t("projectManagement.timelineMeaning")}</p>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="timeline-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="timeline-failed" style={{ color: "var(--muted)" }}>
          {t("projectManagement.loadFailedNote")}
        </p>
      ) : (
        <>
          <div className="card">
            <label>
              {t("projectManagement.startDate")}{" "}
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </label>{" "}
            <label>
              {t("projectManagement.targetDate")}{" "}
              <input type="date" value={target} onChange={(e) => setTarget(e.target.value)} />
            </label>{" "}
            <button
              type="button"
              className="chip chip-stage"
              disabled={busy === "dates"}
              onClick={saveDates}
            >
              {t("projectManagement.saveDates")}
            </button>
          </div>

          <h2>{t("projectManagement.milestones")}</h2>
          {milestones.length === 0 ? (
            <p data-testid="milestones-empty" style={{ color: "var(--muted)" }}>
              {t("common.none")}
            </p>
          ) : (
            <ul style={{ display: "grid", gap: 8, listStyle: "none", padding: 0 }}>
              {milestones.map((milestone) => (
                <li className="card" key={milestone.key} data-testid="milestone-row">
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <strong>{milestone.label}</strong>
                    <span className={milestone.is_completed ? "chip chip-stage" : "chip chip-muted"}>
                      {milestone.is_completed
                        ? t("projectManagement.markComplete")
                        : t("projectManagement.notCompleted")}
                    </span>
                  </div>
                  <p className="metric-label" style={{ marginBlockStart: 4 }}>
                    {t("projectManagement.milestoneTarget")}:{" "}
                    {milestone.target_date ?? t("common.none")}
                    {milestone.completed_at
                      ? ` · ${t("projectManagement.confirmedBy")} ${milestone.completed_at.slice(0, 10)}`
                      : ""}
                  </p>
                  <button
                    type="button"
                    className="chip chip-muted"
                    aria-label={`${
                      milestone.is_completed
                        ? t("projectManagement.unmarkComplete")
                        : t("projectManagement.markComplete")
                    }: ${milestone.label}`}
                    disabled={busy === milestone.key}
                    onClick={() => toggle(milestone.key, !milestone.is_completed)}
                  >
                    {milestone.is_completed
                      ? t("projectManagement.unmarkComplete")
                      : t("projectManagement.markComplete")}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h2>{t("projectManagement.stageHistory")}</h2>
          <p className="metric-label">{history?.note ?? ""}</p>
          {events.length === 0 ? (
            <p data-testid="history-empty" style={{ color: "var(--muted)" }}>
              {t("projectManagement.emptyHistory")}
            </p>
          ) : (
            <ol style={{ display: "grid", gap: 8 }}>
              {events.map((event) => (
                <li key={event.id} data-testid="stage-event">
                  <strong>
                    {event.from_stage_label ? `${event.from_stage_label} ← ` : ""}
                    {event.to_stage_label}
                  </strong>{" "}
                  <span className="metric-label">
                    {event.occurred_at.slice(0, 16).replace("T", " ")}
                  </span>
                  {event.is_return_to_earlier_stage ? (
                    <span className="chip chip-muted" data-testid="returned-earlier">
                      {t("projectManagement.returnedEarlier")}
                    </span>
                  ) : null}
                  {event.system_suggested_stage ? (
                    <p className="metric-label">
                      {t("projectManagement.systemSuggestedThen")}: {event.system_suggested_stage}
                      {" — "}
                      {event.followed_the_suggestion
                        ? t("projectManagement.followedSuggestion")
                        : t("projectManagement.againstSuggestion")}
                    </p>
                  ) : null}
                  {event.note_ar ? <p>{event.note_ar}</p> : null}
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </>
  );
}
