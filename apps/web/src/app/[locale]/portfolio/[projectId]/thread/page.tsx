"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, type Locale, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  CONNECTION_STATES,
  type ConnectionState,
  type GoldenThread,
  type ThreadConnection,
  byStagePair,
  goldenThread,
  worstState,
} from "@/lib/goldenThread";

/**
 * الخيط الذهبي — **لا خطّ بلا صفٍّ مخزَّن**.
 *
 * خطٌّ بين هدفٍ وبناءٍ لأنّ الاثنين في البحث نفسه كذبٌ في صورة، وهو أسوأ
 * من فراغ: الفراغ يُرى فيُسأل عنه، والخطُّ المخترَع يُقرأ إثباتًا ويُنقل
 * إلى قسم المنهجية. فكل وصلةٍ هنا تعرض **اسم الصفّ** الذي يشهد لها،
 * والوصلة التي لا صفَّ لها تُعرض فجوةً بطرفٍ واحد ولا يُملأ طرفها الغائب.
 *
 * **ولا درجة اتساق هنا.** الدرجة تُحسب لبوابة البروتوكول في شاشةٍ أخرى،
 * ونقلُها إلى هنا يعيد ما مُنع في «ما نعرفه»: رقمٌ يخفي الفرق بين خيطٍ
 * تنقصه وصلةٌ وخيطٍ ينقصه منهج. فما يُعرض أعدادٌ بحالاتها لا مجموعُ نقاط.
 *
 * **وخيطٌ فارغ ليس خيطًا متّسقًا.** التحميل والفشل والفراغ ثلاث حالات
 * مفترقة، ولكلٍّ نصّها.
 */

type Load = "loading" | "ready" | "failed";

const STATE_LABEL: Record<ConnectionState, string> = {
  known: "goldenThread.state_known",
  needs_review: "goldenThread.state_needs_review",
  missing: "goldenThread.state_missing",
  conflicting: "goldenThread.state_conflicting",
};

const STATE_HINT: Record<ConnectionState, string> = {
  known: "goldenThread.stateHint_known",
  needs_review: "goldenThread.stateHint_needs_review",
  missing: "goldenThread.stateHint_missing",
  conflicting: "goldenThread.stateHint_conflicting",
};

/** الوسم يتبع الحال: «متعارضة» لا تُعرض بلون «موصولة». */
const STATE_CHIP: Record<ConnectionState, string> = {
  known: "chip chip-ok",
  needs_review: "chip chip-stage",
  missing: "chip chip-muted",
  conflicting: "chip chip-warn",
};

/** أسماء الجداول تُترجم إلى لغة الباحث — ولا يُعرض اسم جدولٍ عاريًا. */
function originLabel(t: (key: string) => string, origin: string): string {
  const key = `goldenThread.origin_${origin}`;
  const label = t(key);
  return label === key ? origin : label;
}

export default function GoldenThreadPage({
  params,
}: {
  params: Promise<{ locale: string; projectId: string }>;
}) {
  const { locale: raw, projectId } = use(params);
  const locale: Locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [thread, setThread] = useState<GoldenThread | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [error, setError] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
    [locale, t],
  );

  const refresh = useCallback(() => {
    setLoad("loading");
    setError(null);
    return goldenThread(locale, projectId)
      .then((view) => {
        setThread(view);
        setLoad("ready");
      })
      .catch((err: unknown) => {
        setLoad("failed");
        setError(say(err));
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

  const stageLabel = (key: string) =>
    thread?.stages.find((stage) => stage.key === key)?.label ?? key;

  /**
   * طرفا الوصلة — **والغائب يُسمّى غائبًا ولا يُملأ**.
   *
   * وعرضُ اسمٍ في مكان الطرف الناقص يجعل الفجوة تُقرأ وصلةً، وهو الخطّ
   * المخترَع نفسه في صورة نصّ.
   */
  const endpoints = (connection: ThreadConnection) => (
    <p style={{ margin: 0 }}>
      <span>{connection.source_label ?? t("goldenThread.notRecorded")}</span>
      {" ← "}
      <span>{connection.target_label ?? t("goldenThread.notRecorded")}</span>
    </p>
  );

  const totalNodes = (thread?.stages ?? []).reduce(
    (sum, stage) => sum + stage.nodes.length,
    0,
  );

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/portfolio/${projectId}`}>
          {t("goldenThread.backToProject")}
        </Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>{t("goldenThread.title")}</h1>
      {/* **اسمُ البحث يُعرض، ولا يُترك الباحث يخمّن أيَّ خيطٍ يقرأ.**
          والعنوان يصل من عقد العرض: فارغُه يصير «مشروع بدون عنوان» **مُعلَنًا
          بديلًا**، وتاريخُ الإنشاء حقلٌ مستقلّ لا جزءٌ من الاسم — ودمجُهما هو
          أصلُ العناوين المشوَّهة التي ظهرت طابعًا زمنيًّا في مكان العنوان. */}
      {thread ? (
        <p style={{ marginBlockEnd: 4 }} data-testid="thread-project-title">
          <span className="metric-label">{t("goldenThread.projectTitleLabel")}: </span>
          <strong>{thread.title}</strong>
          {thread.created_at ? (
            <span className="metric-label" style={{ marginInlineStart: 8 }}>
              {t("goldenThread.createdAtLabel")}:{" "}
              {new Date(thread.created_at).toLocaleDateString(
                locale === "ar" ? "ar" : "en",
              )}
            </span>
          ) : null}
        </p>
      ) : null}
      {thread?.title_is_fallback ? (
        <p className="metric-label" data-testid="thread-title-fallback">
          {t("goldenThread.projectTitleFallback")}
        </p>
      ) : null}
      <p className="metric-label">{t("goldenThread.lead")}</p>
      <p style={{ marginBlockEnd: 12 }}>
        <Link href={`/${locale}/portfolio/${projectId}/brain`}>
          {t("goldenThread.openBrain")}
        </Link>
      </p>

      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button type="button" className="chip chip-muted" onClick={() => void refresh()}>
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {load === "loading" ? (
        <p data-testid="thread-loading" style={{ color: "var(--muted)" }}>
          {t("app.loading")}
        </p>
      ) : load === "failed" || thread === null ? (
        // **الفشل ليس خيطًا فارغًا.** ولو عُرضت المراحل خاليةً هنا لقرأها
        // الباحث حكمًا بأنّ بحثه بلا عناصر، وهو حكمٌ لم يُفحص.
        <p data-testid="thread-failed" className="gate">
          {t("goldenThread.loadFailedNote")}
        </p>
      ) : (
        <>
          <section className="note" style={{ marginBlockEnd: 14 }}>
            <p style={{ margin: 0 }}>{thread.note}</p>
            <p style={{ margin: "6px 0 0", display: "flex", gap: 6, flexWrap: "wrap" }}
               data-testid="thread-counts" aria-label={t("goldenThread.countsTitle")}>
              {CONNECTION_STATES.map((state) => (
                <span key={state} className={STATE_CHIP[state]}>
                  {t(STATE_LABEL[state])}: {thread.counts[state] ?? 0}
                </span>
              ))}
            </p>
          </section>

          <section aria-labelledby="thread-read-notes" style={{ marginBlockEnd: 14 }}>
            <h2 id="thread-read-notes">{t("goldenThread.readNotesTitle")}</h2>
            <p className="metric-label">{t("goldenThread.readNotesHint")}</p>
            <ul>
              {thread.read_notes.map((note) => (
                <li key={note.key}>{note.detail}</li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="thread-stages" style={{ marginBlockEnd: 18 }}>
            <h2 id="thread-stages">{t("goldenThread.stagesTitle")}</h2>
            {totalNodes === 0 ? (
              <p data-testid="thread-empty" className="note">
                {t("goldenThread.emptyThread")}
              </p>
            ) : null}
            {/* المراحل تسع، فتُجرّ أفقيًّا ولا تُضغط في شاشةٍ ضيّقة. */}
            <div style={{ overflowX: "auto" }}>
              <ol style={{ display: "flex", gap: 12, listStyle: "none", padding: 0,
                           margin: 0, minInlineSize: "min-content" }}>
                {thread.stages.map((stage) => (
                  <li key={stage.key} className="card"
                      style={{ minInlineSize: 200, flex: "0 0 auto" }}>
                    <p style={{ margin: 0, fontWeight: 560 }}>{stage.label}</p>
                    <p className="metric-label" data-testid={`stage-count-${stage.key}`}>
                      {stage.nodes.length} {t("goldenThread.nodeCount")}
                    </p>
                    {stage.nodes.length === 0 ? (
                      <p style={{ margin: 0, color: "var(--muted)" }}>
                        {t("goldenThread.emptyStage")}
                      </p>
                    ) : (
                      <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                        {stage.nodes.map((node) => (
                          <li key={node.id}>
                            {node.label}
                            {/* **من أيّ جدول قُرئت العقدة يُقال.** «نتيجة»
                                كتبها الباحث ليست «نتيجة» أخرجها تحليل. */}
                            <div className="metric-label">
                              {originLabel(t, node.origin)}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </section>

          <section aria-labelledby="thread-connections">
            <h2 id="thread-connections">{t("goldenThread.connectionsTitle")}</h2>
            {thread.connections.length === 0 ? (
              <p data-testid="thread-no-connections" style={{ color: "var(--muted)" }}>
                {t("goldenThread.emptyConnections")}
              </p>
            ) : (
              byStagePair(thread).map((group) => {
                const summary = worstState(group.connections);
                return (
                  <section key={group.key} style={{ marginBlockEnd: 14 }}>
                    <h3 style={{ marginBlockEnd: 2 }}>
                      {stageLabel(group.from)} ← {stageLabel(group.to)}{" "}
                      <span className={STATE_CHIP[summary]}
                            data-testid={`pair-state-${group.key}`}>
                        {t(STATE_LABEL[summary])}
                      </span>
                    </h3>
                    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                      {group.connections.map((connection, index) => (
                        <li key={`${group.key}-${connection.source_id ?? "none"}-${connection.target_id ?? "none"}-${index}`}
                            className="card" style={{ marginBlockEnd: 8 }}>
                          <p style={{ margin: 0, display: "flex", gap: 6, flexWrap: "wrap" }}>
                            <span className={STATE_CHIP[connection.state]}>
                              {t(STATE_LABEL[connection.state])}
                            </span>
                          </p>
                          {endpoints(connection)}
                          <p style={{ margin: "4px 0 0" }}>{connection.detail}</p>
                          <p className="metric-label" style={{ margin: "4px 0 0" }}>
                            {t(STATE_HINT[connection.state])}
                          </p>
                          {/* الشاهد يُسمّى باسمه: قارئُ الشاشة يعرف من أيّ
                              عمودٍ جاء الخطّ، ومن لا شاهد له يُقال ذلك فيه. */}
                          <p className="metric-label" style={{ margin: "4px 0 0" }}>
                            {connection.basis
                              ? `${t("goldenThread.basisLabel")}: ${connection.basis}`
                              : t("goldenThread.noBasis")}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })
            )}
          </section>
        </>
      )}
    </>
  );
}
