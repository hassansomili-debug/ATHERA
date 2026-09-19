"use client";

import Link from "next/link";
import { useCallback, useState, type ReactNode } from "react";

import { fill, formatCount, formatUsd, type ModelUsage } from "@/lib/admin";
import { AtheraApiError, apiFetch } from "@/lib/api";
import { getMessages, translator, type Locale } from "@/lib/i18n";
import { useDeferredLoad, type Commit } from "@/lib/useDeferredLoad";

/**
 * هيكلُ لوحة الإدارة (المرحلة ٩) — **وجملةُ النطاق في كلّ صفحة**.
 *
 * «تعرض هذه اللوحة بيانات مساحة العمل الحالية فقط» ليست زينة: مديرٌ يقرأ
 * «٣٠ عضوًا» دون أن يعرف أنّها مساحتُه وحدها قد يظنّها المنصّةَ كلَّها.
 */

export type AdminSection =
  | "overview" | "users" | "projects" | "usage" | "operations";

const SECTIONS: Array<{ id: AdminSection | "audit" | "posture"; path: string; key: string }> = [
  { id: "overview", path: "admin", key: "admin.tabOverview" },
  { id: "users", path: "admin/users", key: "admin.tabUsers" },
  { id: "projects", path: "admin/projects", key: "admin.tabProjects" },
  { id: "usage", path: "admin/usage", key: "admin.tabUsage" },
  { id: "operations", path: "admin/operations", key: "admin.tabOperations" },
  // **ولا تُكرَّر شاشتان قائمتان**: سجلُّ التدقيق وحالُ التشغيل روابطُ إليهما.
  { id: "audit", path: "audit", key: "admin.tabAudit" },
  { id: "posture", path: "settings", key: "admin.tabPosture" },
];

export function AdminShell({
  locale, active, workspace, children,
}: {
  locale: Locale;
  active: AdminSection;
  workspace?: string | null;
  children: ReactNode;
}) {
  const t = translator(getMessages(locale));
  return (
    <div className="admin-console" data-testid="admin-console">
      <div className="page-head">
        <h1>{t("admin.title")}</h1>
        <p>{t("admin.subtitle")}</p>
      </div>
      <p className="admin-scope" data-testid="admin-scope" role="note">
        {workspace ? (
          <strong>{t("admin.currentWorkspace")}: {workspace}</strong>
        ) : null}
        <span>{t("admin.scopeNote")}</span>
      </p>
      <nav aria-label={t("admin.sectionsLabel")} className="admin-subnav">
        <ul>
          {SECTIONS.map((section) => (
            <li key={section.id}>
              <Link
                href={`/${locale}/${section.path}`}
                aria-current={section.id === active ? "page" : undefined}
                data-testid={`admin-tab-${section.id}`}
              >
                {t(section.key)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {children}
    </div>
  );
}

/**
 * حالُ المورد — **أربعٌ لا ثلاث**: جارٍ، ومحجوب، ومتعثّر، وجاهز.
 *
 * «المحجوب» غيرُ «المتعثّر»: غيرُ المدير يرى أنّ اللوحة ليست له، لا أنّ خللًا
 * وقع. و«المتعثّر» غيرُ «الفارغ»: طلبٌ سقط لا يُعرض قائمةً خالية.
 */
export type ResourceState<T> =
  | { status: "loading" }
  | { status: "forbidden" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

export function useAdminResource<T>(locale: Locale, path: string | null) {
  const t = translator(getMessages(locale));
  const [state, setState] = useState<ResourceState<T>>({ status: "loading" });

  const load = useCallback(async (commit: Commit) => {
    if (path === null) return;
    commit(() => setState({ status: "loading" }));
    try {
      const data = await apiFetch<T>(path, { locale });
      commit(() => setState({ status: "ready", data }));
    } catch (err) {
      if (err instanceof AtheraApiError && err.status === 403) {
        commit(() => setState({ status: "forbidden" }));
        return;
      }
      const message = err instanceof AtheraApiError ? err.localized(locale) : t("admin.loadFailed");
      commit(() => setState({ status: "error", message }));
    }
  }, [locale, path, t]);

  const reload = useDeferredLoad(load);
  return { state, reload };
}

/** يعرض كلَّ حالٍ غيرِ جاهزةٍ بعبارتها — ويُعيد `null` حين تكون جاهزة. */
export function ResourceGate<T>({
  locale, state, reload,
}: {
  locale: Locale;
  state: ResourceState<T>;
  reload: () => void;
}) {
  const t = translator(getMessages(locale));
  if (state.status === "loading") {
    return (
      <p className="metric-label" role="status" aria-live="polite" data-testid="admin-loading">
        {t("admin.loading")}
      </p>
    );
  }
  if (state.status === "forbidden") {
    return <p className="error" role="alert" data-testid="admin-forbidden">{t("admin.noAccess")}</p>;
  }
  if (state.status === "error") {
    return (
      <div role="alert" data-testid="admin-error" className="admin-error">
        <p className="error">{state.message}</p>
        <p className="metric-label">{t("admin.loadFailed")}</p>
        <button type="button" onClick={() => void reload()}>{t("admin.retry")}</button>
      </div>
    );
  }
  return null;
}

/**
 * التكلفةُ المسجَّلة — **والفارغُ لم يُسجَّل، لا «صفر»**.
 *
 * لا يُكتب «٠٫٠٠ $» على تشغيلاتٍ لم تُسعَّر؛ ويُعرض دائمًا كم منها سُجّلت تكلفتُه.
 */
export function CostLine({ locale, t, usage }: {
  locale: Locale; t: (k: string) => string; usage: ModelUsage;
}) {
  // **الفارغُ لم يُسجَّل — لا «صفر»**. فلا يُكتب «٠٫٠٠ $» على تشغيلاتٍ لم تُسعَّر.
  if (usage.model_runs === 0) {
    return <p className="metric-label" data-testid="cost-none">{t("admin.costNoRuns")}</p>;
  }
  if (usage.runs_with_cost === 0) {
    return <p className="metric-label" data-testid="cost-not-recorded">{t("admin.costNotRecorded")}</p>;
  }
  return (
    <>
      <div className="metric-value" data-testid="cost-value">
        {formatUsd(locale, usage.recorded_cost_usd)}
      </div>
      <p className="metric-label" data-testid="cost-coverage">
        {fill(t("admin.costCoverage"), {
          with: formatCount(locale, usage.runs_with_cost),
          total: formatCount(locale, usage.model_runs),
        })}
      </p>
    </>
  );
}
