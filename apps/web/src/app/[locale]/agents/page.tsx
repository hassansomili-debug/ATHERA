"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * تفتيش سجل الأجنتات (§8).
 *
 * عرض القيود في الواجهة قرار حوكمة لا تفصيل تصميمي: الباحث والمؤسسة يريان
 * ما لا يستطيع الأجنت فعله، بدل الوثوق بوعد في تعليمات لا يرونها.
 */
interface AgentSpec {
  key: string;
  name: string;
  responsibility: string;
  constraint: string;
  allowed_tools: string[];
  guards: string[];
  gate: string | null;
}

export default function AgentsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [agents, setAgents] = useState<AgentSpec[]>([]);
  const [error, setError] = useState<string | null>(null);
  // **الفراغ كان صامتًا هنا.** لا رسالة تحميل ولا رسالة خلوّ: صفحةٌ بعنوان
  // وحده، فلا يُفرَّق بين سجلٍّ لم يصل بعد وسجلٍّ لا أجنت فيه — وهما حالان
  // مختلفتان تمامًا في شاشةٍ غرضها إعلان القيود.
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiFetch<AgentSpec[]>("/api/v1/brain/agents", { locale })
      .then(setAgents)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      // في دالّة رد نداء لا في جسم التأثير — `react-hooks/set-state-in-effect`.
      .finally(() => setLoaded(true));
  }, [locale, t]);

  return (
    <>
      <h1>{t("agents.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("agents.subtitle")}</p>
      <p className="provenance-note">{t("agents.toolsNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : agents.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("agents.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: "var(--space)" }}>
        {agents.map((agent) => (
          <article className="card" key={agent.key}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{agent.name}</strong>
              <span className="metric-label">
                {t("agents.gate")}: {agent.gate ?? t("agents.noGate")}
              </span>
            </div>
            <p style={{ marginBlock: 6, fontSize: 14 }}>
              <span className="metric-label">{t("agents.responsibility")}: </span>
              {agent.responsibility}
            </p>
            <p
              style={{
                marginBlock: 6,
                paddingInlineStart: 12,
                borderInlineStart: "3px solid var(--athera-gold)",
                fontSize: 14,
              }}
            >
              <span className="metric-label">{t("agents.constraint")}: </span>
              {agent.constraint}
            </p>
            <div className="metric-label" style={{ marginBlockStart: 8 }}>
              {t("agents.tools")}: {agent.allowed_tools.join("، ")}
            </div>
            <div className="metric-label">
              {t("agents.guards")}: {agent.guards.join("، ")}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
