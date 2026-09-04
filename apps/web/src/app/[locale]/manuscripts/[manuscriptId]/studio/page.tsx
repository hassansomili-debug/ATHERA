"use client";

import { use, useCallback, useState } from "react";

import { SectionWorkspace } from "@/components/SectionWorkspace";
import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * مصنع المخطوطات (S5E-D).
 *
 * ثلاثة أعمدة: الأقسام وحالاتها، ثم القسم المفتوح، ثم عوائق الورقة كوحدة.
 * **ولا نسبة جاهزية واحدة**: رقمٌ مثل «٧٣٪ جاهزة» يُقرأ وعدًا، ويخفي أن
 * الباقي عائقٌ علمي لا عملٌ متبقٍّ. فتُعرض الأعداد والعوائق بأسمائها.
 *
 * **والحالة لا تُقال بلونٍ وحده** (§29): لكل حالة نصّها، فالتمييز يبقى
 * قائمًا لمن لا يميّز الألوان ولمن يقرأ بقارئ شاشة.
 *
 * وعلى الشاشات الضيّقة يُطوى العمودان الجانبيان بدل أن تُحشر ثلاثة أعمدة
 * لا يُقرأ منها شيء (§28).
 */
interface SectionOverview {
  section_key: string;
  title_ar: string;
  enabled: boolean;
  status: string;
  claims: number;
  grounded_claims: number;
  literature: string;
  purpose_ar: string;
}

interface ManuscriptIssue {
  issue_key: string;
  sections: string[];
  severity: string;
  message_ar: string;
  message_en: string;
  excerpt: string | null;
}

interface Overview {
  manuscript_id: string;
  title_ar: string;
  version_label: string;
  sections: SectionOverview[];
  approved_sections: number;
  enabled_sections: number;
  pending_literature: string[];
  issues: ManuscriptIssue[];
  blocking: number;
  note: string;
}

const DERIVED_STATUS: Record<string, string> = {
  not_started: "studio.statusNotStarted",
  pending_literature: "studio.statusPendingLiterature",
  disabled: "studio.statusDisabled",
  draft: "methods.statusDraft",
  needs_review: "methods.statusNeedsReview",
  approved: "methods.statusApproved",
  revision_requested: "methods.statusRevisionRequested",
};

export default function StudioPage({
  params,
}: {
  params: Promise<{ locale: string; manuscriptId: string }>;
}) {
  const { locale: raw, manuscriptId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [overview, setOverview] = useState<Overview | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [asideOpen, setAsideOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // **«لا عوائق» كانت تُقال قبل أن تُقرأ الورقة.** من يفتح العمود الجانبي
  // قبل عودة النظرة العامة يقرأ أن ورقته بلا عائق، وهي أهم دعوى في الشاشة
  // وأخطرها إن قيلت بلا فحص. والشاشة كلّها كانت صامتة أثناء الانتظار.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setOverview(
        await apiFetch<Overview>(`/api/v1/manuscripts/${manuscriptId}/overview`, {
          locale,
        }),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [manuscriptId, locale, t]);

  useDeferredLoad(load);

  const enabled = (overview?.sections ?? []).filter((s) => s.enabled);
  const pending = (overview?.sections ?? []).filter((s) => !s.enabled);

  return (
    <main dir={locale === "ar" ? "rtl" : "ltr"}>
      <header>
        <h1>{t("studio.title")}</h1>
        {overview ? (
          <p>
            {overview.title_ar} · {t("studio.version")} {overview.version_label} ·{" "}
            {overview.approved_sections} {t("studio.approvedOf")} {overview.enabled_sections}
          </p>
        ) : null}
        {error ? <p role="alert">{error}</p> : null}
        {!loaded ? <p data-testid="studio-loading">{t("app.loading")}</p> : null}
      </header>

      <div>
        {/* ── يمين/يسار: الأقسام وحالاتها ── */}
        <nav aria-label={t("studio.sections")}>
          <h2>{t("studio.sections")}</h2>
          <ul>
            {enabled.map((section) => (
              <li key={section.section_key}>
                <button
                  type="button"
                  onClick={() => setActive(section.section_key)}
                  aria-current={active === section.section_key ? "true" : undefined}
                >
                  <span>{section.title_ar}</span>{" "}
                  {/* الحالة نصًّا لا لونًا وحده */}
                  <span>— {t(DERIVED_STATUS[section.status] ?? "studio.statusNotStarted")}</span>
                  {section.claims > 0 ? (
                    <span>
                      {" "}
                      · {section.grounded_claims}/{section.claims} {t("studio.facts")}
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>

          {pending.length > 0 ? (
            <section>
              <h3>{t("studio.pendingLiterature")}</h3>
              <p>{t("studio.pendingNote")}</p>
              <ul>
                {pending.map((section) => (
                  <li key={section.section_key}>
                    {section.title_ar} — {t("studio.statusPendingLiterature")}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </nav>

        {/* ── الوسط: القسم المفتوح ── */}
        <section aria-live="polite">
          {active ? (
            <SectionWorkspace
              locale={locale}
              manuscriptId={manuscriptId}
              sectionKey={active}
              copy={active === "results" ? "results" : "methods"}
              strict={active === "results"}
              onChanged={load}
            />
          ) : (
            <p>{t("studio.selectSection")}</p>
          )}
        </section>

        {/* ── الجانب: عوائق الورقة كوحدة ── */}
        <aside aria-label={t("studio.blockers")}>
          <button type="button" onClick={() => setAsideOpen((open) => !open)}>
            {asideOpen ? t("studio.collapse") : t("studio.expand")} · {t("studio.blockers")}
            {overview ? ` (${overview.blocking})` : ""}
          </button>
          {asideOpen || (overview?.blocking ?? 0) > 0 ? (
            <div>
              <h2>{t("studio.blockers")}</h2>
              {!loaded ? (
                <p>{t("app.loading")}</p>
              ) : (overview?.issues ?? []).length === 0 ? (
                <p>{t("studio.noBlockers")}</p>
              ) : (
                <ul>
                  {(overview?.issues ?? []).map((issue) => (
                    <li key={`${issue.issue_key}-${issue.sections.join("-")}`}>
                      <strong>{issue.sections.join(" · ")}</strong>{" "}
                      {locale === "ar" ? issue.message_ar : issue.message_en}
                      {issue.excerpt ? <code>{issue.excerpt}</code> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </aside>
      </div>

      {overview ? <footer>{overview.note}</footer> : null}
    </main>
  );
}
