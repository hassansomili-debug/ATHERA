"use client";

import { useEffect, useState } from "react";

import { apiFetch, AtheraApiError } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";

/**
 * «ربط بمشروع» — من المكتبة إلى البحث، **بلا نسخ**.
 *
 * الملف أصلٌ واحد قد يخدم أكثر من بحث، فالربط علاقةٌ لا نسخة (الترحيل
 * 0020). والزرّ هنا لا يُعرض ما لم يكن للباحث بحثٌ يربط به: **زرٌّ يفتح
 * قائمةً فارغة وعدٌ لا يُنجَز**، والصمت مع سببٍ مذكور أصدق منه.
 */
interface ProjectRow {
  id: string;
  title_ar: string;
}

export function ProjectPicker({
  locale, messages, fileName, busy, onChoose, onCancel,
}: {
  locale: Locale;
  messages: Messages;
  fileName: string;
  busy: boolean;
  onChoose: (projectId: string) => void;
  onCancel: () => void;
}) {
  const t = translator(messages);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string>("");

  useEffect(() => {
    let live = true;
    apiFetch<ProjectRow[]>("/api/v1/workspace/projects", { locale })
      .then((rows) => {
        if (!live) return;
        setProjects(rows);
        setChosen(rows[0]?.id ?? "");
        setState("ready");
      })
      .catch((err) => {
        if (!live) return;
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
        setState("failed");
      });
    return () => {
      live = false;
    };
  }, [locale]);

  return (
    <div className="card" style={{ marginBlockStart: 8, padding: 12 }}>
      {state === "loading" ? (
        <p role="status" aria-live="polite">{t("app.loading")}</p>
      ) : state === "failed" ? (
        <p className="error" role="alert">{error ?? t("common.loadFailed")}</p>
      ) : projects.length === 0 ? (
        <>
          <p>{t("library.noProjects")}</p>
          <button
            type="button"
            aria-label={`${t("library.linkCancel")}: ${fileName}`}
            onClick={onCancel}
          >
            {t("library.linkCancel")}
          </button>
        </>
      ) : (
        <>
          <label style={{ display: "block", marginBlockEnd: 8 }}>
            {t("library.chooseProject")}
            <select
              value={chosen}
              aria-label={`${t("library.chooseProject")}: ${fileName}`}
              onChange={(event) => setChosen(event.target.value)}
              style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
            >
              {projects.map((row) => (
                <option key={row.id} value={row.id}>{row.title_ar}</option>
              ))}
            </select>
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              disabled={busy || !chosen}
              aria-label={`${t("library.linkSave")}: ${fileName}`}
              onClick={() => onChoose(chosen)}
            >
              {t("library.linkSave")}
            </button>
            <button
              type="button"
              disabled={busy}
              aria-label={`${t("library.linkCancel")}: ${fileName}`}
              onClick={onCancel}
            >
              {t("library.linkCancel")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
