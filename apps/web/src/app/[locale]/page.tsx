import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * لوحة الباحث — الهيكل فقط.
 *
 * القيم معروضة كـ"لا بيانات بعد" عمدًا: المنتج لا يعرض رقمًا بلا مصدر
 * (Evidence First).
 *
 * أربعة مؤشرات كانت هنا — جاهزية الترقية، والوحدات البحثية، ووحدات
 * التأليف المنفرد، وشرط Web of Science الصارم — وكلها مقاييس لائحة ترقية
 * أكاديمية لا مقاييس بحث. أُزيلت مع إعادة التموضع (ADR-0005). وتُعاد بناء
 * هذه الشاشة كليًا على نوايا البحث الخمس في مرحلة S4.
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
