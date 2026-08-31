"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * محرّك التحليل (§17، §18).
 *
 * ثلاثة أشياء لا تعرضها هذه الشاشة عمدًا: لا زرّ «شغّل التحليل» على نسخة غير
 * مجمّدة، ولا خطة تُعدَّل بعد قفلها، ولا تفسير يُكتب قبل وجود مخرَج. كلها
 * ممنوعة في الخادم أصلًا؛ إخفاؤها هنا يمنع المستخدم من مواجهة رفضٍ مبهم.
 */
interface DatasetVersion {
  id: string;
  dataset_id: string;
  state: string;
  state_label: string;
  label: string;
  checksum: string;
  row_count: number | null;
  change_note_ar: string | null;
  freeze_id: string | null;
  frozen_at: string | null;
  is_immutable: boolean;
}

interface Dataset {
  id: string;
  project_id: string;
  name: string;
  classification: string;
  versions: DatasetVersion[];
}

interface PlannedTest {
  test_key: string;
  test_kind: string;
  variables: string[];
  note_ar: string | null;
}

interface AnalysisPlan {
  id: string;
  version_label: string;
  is_locked: boolean;
  approved_at: string | null;
  tests: PlannedTest[];
}

export default function AnalysisPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [plans, setPlans] = useState<AnalysisPlan[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [ds, pl] = await Promise.all([
        apiFetch<Dataset[]>("/api/v1/analysis/datasets", { locale }),
        apiFetch<AnalysisPlan[]>("/api/v1/analysis/plans", { locale }),
      ]);
      setDatasets(ds);
      setPlans(pl);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function act(id: string, path: string) {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(path, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("analysis.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("analysis.subtitle")}</p>
      <p className="provenance-note">{t("analysis.frozenNote")}</p>
      {error ? <p className="error">{error}</p> : null}

      <h2>{t("analysis.datasets")}</h2>
      {datasets.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("analysis.emptyDatasets")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {datasets.map((dataset) => (
          <article className="card" key={dataset.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{dataset.name}</strong>
              <span className="metric-label">{dataset.classification}</span>
            </div>
            <ul style={{ marginBlock: 4, paddingInlineStart: 20, listStyle: "none" }}>
              {dataset.versions.map((version) => (
                <li key={version.id} style={{ marginBlockEnd: 6 }}>
                  <strong>{version.label}</strong> — {version.state_label}
                  {version.row_count !== null ? ` · ${t("analysis.rows")}: ${version.row_count}` : ""}
                  {` · ${version.checksum.slice(0, 12)}…`}
                  {version.frozen_at ? (
                    <span className="badge-ok">
                      {" "}
                      {t("analysis.frozen")} · {t("analysis.freezeId")}: {version.freeze_id}
                    </span>
                  ) : version.state === "raw" ? (
                    // RAW لا يُجمَّد ولا يُعدَّل: هو الأصل الذي تُقاس عليه بقية النسخ.
                    <span className="metric-label"> {t("analysis.rawImmutable")}</span>
                  ) : (
                    <button
                      type="button"
                      style={{ marginInlineStart: 8 }}
                      disabled={busyId === version.id}
                      onClick={() =>
                        void act(version.id, `/api/v1/analysis/datasets/versions/${version.id}/freeze`)
                      }
                    >
                      {t("analysis.freeze")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <h2>{t("analysis.plans")}</h2>
      {plans.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("analysis.emptyPlans")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {plans.map((plan) => (
          <article className="card" key={plan.id}>
            <strong>{plan.version_label}</strong>
            <p className="metric-label">
              {t("analysis.plannedTests")}: {plan.tests.length}
              {plan.tests.length > 0
                ? ` — ${plan.tests.map((test) => test.test_key).join("، ")}`
                : ""}
            </p>
            {plan.is_locked ? (
              <p className="badge-ok">{t("analysis.planLocked")}</p>
            ) : (
              <button
                type="button"
                disabled={busyId === plan.id}
                onClick={() => void act(plan.id, `/api/v1/analysis/plans/${plan.id}/approve`)}
              >
                {t("analysis.approvePlan")}
              </button>
            )}
          </article>
        ))}
      </div>
      <p className="provenance-note">{t("analysis.harkingNote")}</p>
    </>
  );
}
