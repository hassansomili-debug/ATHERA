import { ResearchThread } from "@/components/ResearchThread";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * الصفحة العامّة | The public landing page — **بنصّ ورقة الهويّة**.
 *
 * **ولا شيء فيها مخترَع.** لا عملاء، ولا أسعار، ولا أرقام، ولا شعارات
 * جامعات، ولا «يثق بنا». وكلُّ قدرةٍ مذكورة هنا لها شاشةٌ تُفتح بعد الدخول.
 *
 * **وأربعةُ أشياء في الورقة لم تُنقَل، وسببُ كلٍّ مكتوب** في
 * `docs/integration/brand-requests.md`:
 *
 *   ١ «الأسعار» — الأسعار ممنوعةٌ على السطح العام بأمرٍ مكتوب، ورابطٌ إلى
 *     صفحةٍ لا نملأها صدقًا هو زرٌّ ميت.
 *   ٢ «شاهد الفيديو» — لا فيديو في المستودع. وزرٌّ لا يفعل شيئًا هو بعينه
 *     العطب الذي أزاله المسار أ.
 *   ٣ «للباحثين» و«للمؤسسات» و«عن المنصّة» — لا صفحات لها. وما بقي من
 *     القائمة مراسٍ إلى أقسامٍ **موجودةٌ في هذه الصفحة**، تُقاس بالنقر لا
 *     بالنيّة.
 *   ٤ لوحةُ المؤشّرات في الورقة كلُّها بياناتٌ وهميّة — اسمٌ ومشاريعُ
 *     وأرقام. ولا تُكتب في الشيفرة: تأتي من الخادم أو تُعلَن فارغةً.
 */
const NODES = ["node1", "node2", "node3", "node4", "node5", "node6"] as const;

const CAPABILITIES = [
  "Discover",
  "Build",
  "Manage",
  "Analyze",
  "Write",
  "Publish",
] as const;

const INTEGRITY = [
  "integrity1",
  "integrity2",
  "integrity3",
  "integrity4",
  "integrity5",
  "integrity6",
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
          {/*
            سطران: الوعد ثمّ الكلمة التي تحمله. والثانية بالبنفسجي — وهي
            في `<span>` داخل العنوان نفسه، فيبقى العنوان واحدًا في الشجرة
            ولا ينقسم إلى عنوانين لقارئ الشاشة.
          */}
          <h1>
            {t("landing.title")}
            <span className="accent">{t("landing.titleAccent")}</span>
          </h1>
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
        <ResearchThread className="hero-thread" idSuffix="hero" />
      </section>

      <section className="band" id="how-it-works" aria-labelledby="thread-heading">
        <h2 id="thread-heading">{t("landing.threadHeading")}</h2>
        <p className="band-lead">{t("landing.threadBody")}</p>
        {/*
          **قائمةٌ مرتّبة لأن الترتيب معنى.** ستُّ عقدٍ تُقرأ على التوالي،
          والخيط الذي يصلها في الورقة يقولها للعين — و`<ol>` يقولها لقارئ
          الشاشة، فلا يبقى المعنى في الرسم وحده.
        */}
        <ol className="stages stages-six">
          {NODES.map((node) => (
            <li className="stage" key={node}>
              <span className="stage-node" aria-hidden="true" />
              <strong>{t(`landing.${node}`)}</strong>
            </li>
          ))}
        </ol>
        <p className="thread-foot">{t("landing.threadFoot")}</p>
      </section>

      <section className="band" id="product" aria-labelledby="capabilities-heading">
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

      <section className="band band-ink" id="integrity" aria-labelledby="integrity-heading">
        <h2 id="integrity-heading">{t("landing.integrityHeading")}</h2>
        <p className="band-lead">{t("landing.integrityBody")}</p>
        <ul className="integrity">
          {INTEGRITY.map((rule) => (
            <li key={rule}>
              {/*
                العلامة زخرفٌ يُخفى، والقاعدةُ نصٌّ يُقرأ — ولو أُطفئت
                الرموز كلُّها بقيت القواعد الستّ مقروءةً منطوقة.
              */}
              <span className="tick" aria-hidden="true">✓</span>
              <span>{t(`landing.${rule}`)}</span>
            </li>
          ))}
        </ul>

        <h3 className="legend-title">{t("landing.evidenceHeading")}</h3>
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
