import { ResearchThread } from "@/components/ResearchThread";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * الصفحة العامّة | The public landing page.
 *
 * **ولا شيء فيها مخترَع.** لا عملاء، ولا أسعار، ولا أرقام، ولا شعارات
 * جامعات، ولا «يثق بنا». وكلُّ قدرةٍ مذكورة هنا لها شاشةٌ تُفتح بعد
 * الدخول، ونصُّها مشتقٌّ من نصّ تلك الشاشة نفسه — فلا يَعِد الموقعُ بما لا
 * يفعله المنتج، ولا يفترق الوعدُ عن المُنجَز بعد تعديلٍ في أحدهما.
 *
 * والحالات الأربع معروضةٌ هنا كما تُعرض في المنتج تمامًا: الصنفُ نفسه،
 * واللونُ نفسه، والاسمُ مكتوبٌ بجانبه. ومن رآها هنا عرفها هناك.
 */
const STAGES = ["Discover", "Build", "Review", "Publish"] as const;

const CAPABILITIES = [
  "References",
  "Thesis",
  "Analysis",
  "Manuscript",
  "Review",
  "Team",
] as const;

/** الحالات الأربع — والصنفُ هو صنفُ المنتج نفسه لا نسخةٌ للعرض. */
const STATES = [
  { key: "Candidate", chip: "chip-candidate" },
  { key: "Review", chip: "chip-review" },
  { key: "Verified", chip: "chip-verified" },
  { key: "Conflict", chip: "chip-conflict" },
] as const;

export default async function LandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">{t("landing.eyebrow")}</p>
          <h1>{t("landing.title")}</h1>
          <p className="hero-body">{t("landing.body")}</p>
          <p className="hero-actions">
            <a className="btn-primary" href={`/${locale}/register`}>
              {t("landing.primaryCta")}
            </a>
            <a className="btn-quiet" href={`/${locale}/login`}>
              {t("landing.secondaryCta")}
            </a>
          </p>
        </div>
        {/* الخيط نفسه مرسومًا كبيرًا — عنصرُ الهويّة، لا خلفيّةَ زينة. */}
        <ResearchThread className="hero-thread" idSuffix="hero" />
      </section>

      <section className="band" aria-labelledby="thread-heading">
        <h2 id="thread-heading">{t("landing.threadHeading")}</h2>
        <p className="band-lead">{t("landing.threadBody")}</p>
        {/*
          **قائمةٌ مرتّبة لأن الترتيب معنى.** المراحل الأربع تُقرأ على
          التوالي، والخيط الذي يصلها في الورقة يقولها للعين — و`<ol>`
          يقولها لقارئ الشاشة، فلا يبقى المعنى في الرسم وحده.
        */}
        <ol className="stages">
          {STAGES.map((stage) => (
            <li className="stage" key={stage}>
              <span className="stage-node" aria-hidden="true" />
              <strong>{t(`landing.stage${stage}Title`)}</strong>
              <span>{t(`landing.stage${stage}Body`)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="band" aria-labelledby="capabilities-heading">
        <h2 id="capabilities-heading">{t("landing.capabilitiesHeading")}</h2>
        <p className="band-lead">{t("landing.capabilitiesBody")}</p>
        <div className="cap-grid">
          {CAPABILITIES.map((capability) => (
            <article className="cap" key={capability}>
              <h3>{t(`landing.cap${capability}Title`)}</h3>
              <p>{t(`landing.cap${capability}Body`)}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="band band-ink" aria-labelledby="evidence-heading">
        <h2 id="evidence-heading">{t("landing.evidenceHeading")}</h2>
        <p className="band-lead">{t("landing.evidenceBody")}</p>

        <h3 className="legend-title">{t("landing.stateLegendLabel")}</h3>
        <p className="band-lead">{t("landing.stateLegendBody")}</p>
        <ul className="legend">
          {STATES.map((state) => (
            <li key={state.key}>
              {/*
                **الصنفُ يحمل اللون، والنصُّ يحمل المعنى.** ولو أُطفئت
                الأنماط كلّها بقي اسمُ الحال مقروءًا ومنطوقًا.
              */}
              <span className={`chip ${state.chip}`} data-state={state.key.toLowerCase()}>
                {t(`landing.state${state.key}`)}
              </span>
              <span>{t(`landing.state${state.key}Body`)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="band" aria-labelledby="bilingual-heading">
        <h2 id="bilingual-heading">{t("landing.bilingualHeading")}</h2>
        <p className="band-lead">{t("landing.bilingualBody")}</p>
      </section>

      <section className="band closing" aria-labelledby="closing-heading">
        <h2 id="closing-heading">{t("landing.closingHeading")}</h2>
        <p className="band-lead">{t("landing.closingBody")}</p>
        <p className="hero-actions">
          <a className="btn-primary" href={`/${locale}/register`}>
            {t("landing.primaryCta")}
          </a>
          <a className="btn-quiet" href={`/${locale}/login`}>
            {t("landing.secondaryCta")}
          </a>
        </p>
      </section>
    </>
  );
}
