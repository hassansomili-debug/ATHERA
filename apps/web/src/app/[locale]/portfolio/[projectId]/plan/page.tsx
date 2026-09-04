"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import { confirmStage, loadDashboard, type Dashboard } from "@/lib/projectManagement";
import { displayTitle } from "@/lib/projectTitle";

/**
 * لوحةُ المشروع — **تجيب عن سؤالٍ عمليّ، لا تعرض أرقام زينة**.
 *
 * والباحث يفتحها وفي ذهنه ساعةٌ فارغة؛ يريد أن يعرف أين يضعها. فيُقال له
 * بعملٍ بعينه: ثلاثُ مهامّ فات موعدها، ومهمّةٌ موقوفةٌ على قرارك.
 *
 * **ولا نسبةَ في هذه الشاشة ولا في عقدها.** «٧٣٪ مكتمل» يُقرأ حكمًا على
 * الورقة، ولم يقع من ذلك شيء — عُدَّت بطاقاتٌ وقُسمت على بطاقات. والعدد
 * يُفتَح ويُرى، والنسبة تُصدَّق.
 *
 * **والمرحلة أربع حقائق لا واحدة**: ما هي الآن، وهل أكّدها الباحث، وما
 * المقترَح بعدها، وبأيّ سند. والشارة تقول «لم تؤكّدها بعد» صراحةً — فلا
 * تُقرأ القيمة الافتراضية حكمًا من المنصّة.
 *
 * **وأربع حالات عرضٍ لا تُخلط**: قبل الجواب، وأثناءه، وجوابٌ فارغ، وفشل.
 * وأخطرها الأخيرة: طلبٌ فشل يُعرض «لا شيء يحتاج انتباهك» يجعل الباحث يطمئن
 * وعنده ثلاثُ مهامّ متأخرة.
 */

type Load = "loading" | "ready" | "failed";

export default function ProjectPlanPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [data, setData] = useState<Dashboard | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return loadDashboard(locale, projectId)
      .then((view) => {
        setData(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setError(say(err));
        setLoad("failed");
      });
  }, [locale, projectId, say]);

  /** **لا تُضبط حالةٌ داخل التأثير مباشرةً** — قاعدةٌ يفرضها المدقّق خطأً. */
  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (alive) void refresh();
    });
    return () => {
      alive = false;
    };
  }, [refresh]);

  /** **اعتمادُ المرحلة فعلُ الباحث** — وهو المسار الوحيد الذي يغيّرها. */
  const confirm = (stage: string) => {
    setBusy(true);
    setError(null);
    void confirmStage(locale, projectId, stage, note.trim() || undefined)
      .then(() => {
        setNote("");
        return refresh();
      })
      .catch((err: unknown) => setError(say(err)))
      .finally(() => setBusy(false));
  };

  const attention = data?.needs_your_attention ?? [];
  const suggestion = data?.stage.suggestion;

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>{t("projectManagement.backToProject")}</Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("projectManagement.planTitle")}</h1>
      <p className="metric-label">{t("projectManagement.planMeaning")}</p>

      <nav aria-label={t("projectManagement.tabsLabel")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/tasks`}>
              {t("projectManagement.tasksTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/${projectId}/timeline`}>
              {t("projectManagement.timelineTitle")}
            </Link>
          </li>
          <li>
            <Link className="chip chip-muted" href={`/${locale}/portfolio/trash`}>
              {t("projectManagement.trashTitle")}
            </Link>
          </li>
        </ul>
      </nav>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="plan-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" ? (
        <p data-testid="plan-failed" style={{ color: "var(--muted)" }}>
          {t("projectManagement.loadFailedNote")}
        </p>
      ) : data ? (
        <>
          {/* ── العنوان: يمرّ بالعقد المشترك، والتاريخ في حقلٍ منفصل ── */}
          <article className="card">
            <h2 style={{ marginBlockStart: 0 }}>{displayTitle(data.title, locale)}</h2>
            {data.title.is_placeholder ? (
              <p className="metric-label" data-testid="plan-untitled">
                {t("projectManagement.untitledNote")}
              </p>
            ) : null}
            {data.title.created_at ? (
              <p className="metric-label">
                {t("projectManagement.createdAt")}: {data.title.created_at.slice(0, 10)}
              </p>
            ) : null}
          </article>

          {/* ── المرحلة: أربع حقائق، كلٌّ في موضعها ── */}
          <article className="card" style={{ marginBlockStart: "var(--space)" }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
              <span className="chip chip-stage">{data.stage.current_stage_label}</span>
              {data.stage.is_researcher_confirmed ? null : (
                <span className="chip chip-muted" data-testid="stage-unconfirmed">
                  {t("projectManagement.notConfirmed")}
                </span>
              )}
            </div>
            <p className="metric-label" style={{ marginBlockStart: 6 }}>
              {data.stage.disclaimer}
            </p>

            <h3>{t("projectManagement.suggestedNext")}</h3>
            {suggestion?.is_offered ? (
              <>
                <p>
                  <strong>{suggestion.stage_label}</strong>
                </p>
                {/* **السندُ يُعرض دائمًا** — ولو صمت لقُرئ الاقتراح حكمًا. */}
                <p className="metric-label">{suggestion.basis}</p>
                <button
                  type="button"
                  className="chip chip-stage"
                  disabled={busy}
                  aria-label={`${t("projectManagement.confirmStage")}: ${suggestion.stage_label}`}
                  onClick={() => confirm(suggestion.stage as string)}
                >
                  {t("projectManagement.confirmStage")}
                </button>
              </>
            ) : (
              <p className="metric-label" data-testid="suggestion-empty">
                {suggestion?.basis ?? t("projectManagement.noSuggestion")}
              </p>
            )}
            <p style={{ marginBlockStart: 8 }}>
              <label>
                {t("projectManagement.stageNote")}{" "}
                <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
              </label>
            </p>
          </article>

          {/* ── ما يحتاج انتباهك: أعدادٌ لا نسب ── */}
          <h2>{t("projectManagement.needsAttention")}</h2>
          {attention.length === 0 ? (
            <p data-testid="attention-empty" style={{ color: "var(--muted)" }}>
              {data.nothing_urgent_note || t("projectManagement.nothingUrgent")}
            </p>
          ) : (
            <ul style={{ display: "grid", gap: 8, listStyle: "none", padding: 0 }}>
              {attention.map((item) => (
                <li className="card" key={item.key} data-testid={`attention-${item.key}`}>
                  <strong>
                    {item.label}
                    {item.count === null ? "" : ` — ${item.count}`}
                  </strong>
                  <p className="metric-label" style={{ marginBlockStart: 4 }}>
                    {item.detail}
                  </p>
                  <Link
                    className="chip chip-muted"
                    aria-label={`${item.label}: ${t("projectManagement.tasksTitle")}`}
                    href={
                      item.destination === "tasks"
                        ? `/${locale}/portfolio/${projectId}/tasks`
                        : `/${locale}/portfolio/${projectId}/timeline`
                    }
                  >
                    {item.destination === "tasks"
                      ? t("projectManagement.tasksTitle")
                      : t("projectManagement.timelineTitle")}
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {/* ── الأعداد: كلٌّ منها واقعةٌ تُفتَح وتُرى ── */}
          <div className="card" style={{ marginBlockStart: "var(--space)" }}>
            <div className="metric-label">
              {t("projectManagement.openTasks")}: {data.counts.open}
              {" · "}
              {t("projectManagement.overdueTasks")}: {data.counts.overdue}
              {" · "}
              {t("projectManagement.awaitingDecision")}: {data.counts.awaiting_your_decision}
              {" · "}
              {t("projectManagement.teamCount")}: {data.team_members}
            </div>
            <div className="metric-label">
              {t("projectManagement.startDate")}: {data.start_date ?? t("common.none")}
              {" · "}
              {t("projectManagement.targetDate")}: {data.target_completion_date ?? t("common.none")}
            </div>
          </div>

          {data.missing_scientific_items.length > 0 ? (
            <>
              <h2>{t("projectManagement.missingItems")}</h2>
              <ul>
                {data.missing_scientific_items.map((item) => (
                  <li key={item.key}>
                    {item.label}{" "}
                    <span className="metric-label">
                      ({t("projectManagement.expectedSince")} {item.expected_since_stage_label})
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          <h2>{t("projectManagement.recentActivity")}</h2>
          {data.recent_activity.length === 0 ? (
            <p data-testid="activity-empty" style={{ color: "var(--muted)" }}>
              {t("common.none")}
            </p>
          ) : (
            <ul>
              {data.recent_activity.map((row, index) => (
                <li key={`${row.kind}-${row.occurred_at}-${index}`}>
                  <span className="metric-label">{row.occurred_at.slice(0, 16).replace("T", " ")}</span>{" "}
                  {row.subject}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </>
  );
}
