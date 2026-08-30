import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * لوحة الباحث (§27.2) — الهيكل فقط في Sprint 0.
 *
 * القيم معروضة كـ"لا بيانات بعد" عمدًا: المنتج لا يعرض رقمًا بلا مصدر
 * (§4 Evidence First). ستُملأ من محرك الترقية في MVP-2.
 */
export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const metrics = [
    "dashboard.promotionReadiness",
    "dashboard.researchUnits",
    "dashboard.soleAuthorUnits",
    "dashboard.strictWos",
    "dashboard.activeProjects",
    "dashboard.pendingApprovals",
  ];

  return (
    <>
      <h1>{t("dashboard.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("dashboard.subtitle")}</p>

      <section className="grid" aria-label={t("dashboard.title")}>
        {metrics.map((key) => (
          <article className="card" key={key}>
            <div className="metric-label">{t(key)}</div>
            <div className="metric-value">—</div>
          </article>
        ))}
      </section>

      <p className="provenance-note">{t("provenance.noFabrication")}</p>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>{t("dashboard.emptyState")}</p>
    </>
  );
}
