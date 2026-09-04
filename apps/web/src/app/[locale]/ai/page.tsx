"use client";

import { use, useState, useSyncExternalStore } from "react";

import { AtheraAiInput } from "@/components/AtheraAiInput";
import { useAiCapabilities } from "@/lib/aiCapabilities";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * بُبريفا AI — سطحُ عملٍ بحثيّ دائم.
 *
 * المستخدم يخاطب «بُبريفا AI»، ولا يرى ستة عشر أجنتًا ولا أسماءها. السجل
 * التفصيلي باقٍ في «قدرات بُبريفا AI» لمن أراد الشفافية، لا في وجه من يريد
 * إنجاز بحث.
 *
 * **ولا تشخيصَ بنيةٍ تحتية هنا.** كانت الصفحة تُنهي نفسها بشبكةِ بطاقات
 * وضع التشغيل: اسمُ مزوّد النموذج، وحالُ تخزين S3، وسقفُ تصنيف البيانات
 * C1، والرصدُ المجدول. وذلك شأنُ من ينشر الخادم — ومكانه شاشةُ الإعدادات.
 * والباحثُ يقرؤه لوحةَ عمليات لا سطحَ عمل، فيظنّ أنّ عليه ضبط شيءٍ قبل أن
 * يسأل سؤاله.
 *
 * فما بقي هنا ثلاثُ قدراتٍ بلغته: أيبحث في الفهارس؟ أيقرأ ملفاته؟ أيجيب
 * أصلًا؟ — بلا اسم مزوّد ولا سبب تعطيلٍ داخليّ ولا رمز تصنيف.
 */
const INTENTS = [
  "intentIdea", "intentThesis", "intentSearch", "intentMethod",
  "intentData", "intentManuscript", "intentJournal", "intentReview",
];

/** الرابط لا يتغيّر بلا تنقّل، والتنقّل يعيد التركيب — فلا اشتراك. */
const NO_SUBSCRIPTION = () => () => undefined;
const attachedFile = (): string | undefined =>
  new URLSearchParams(window.location.search).get("file") ?? undefined;
const currentProject = (): string | undefined =>
  new URLSearchParams(window.location.search).get("project") ?? undefined;
/** فكرةٌ كتبها الباحث في الرئيسية — تصل مكتوبةً في المربّع، لا تُطلب ثانية. */
const askedQuestion = (): string =>
  new URLSearchParams(window.location.search).get("q") ?? "";

export default function AiPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  // **مستندٌ أو بحثٌ جاء من شاشةٍ أخرى ليُسأل عنه.**
  //
  // ويُقرأ في المتصفّح لا عند التوليد: `searchParams` تُخرج الصفحة من
  // التوليد المسبق وتطلب حدًّا للتعليق، وهذه قيمةٌ لا وجود لها أصلًا قبل
  // أن ينقر الباحث. ولا يُضبط داخل `useEffect` — تصيير متتالٍ يمنعه
  // `react-hooks/set-state-in-effect`، و`useSyncExternalStore` هي الأداة
  // الموضوعة لهذا: لقطةٌ على العميل وأخرى على الخادم تمنع اختلاف الترطيب.
  const attachFileId = useSyncExternalStore(NO_SUBSCRIPTION, attachedFile, () => undefined);
  const projectId = useSyncExternalStore(NO_SUBSCRIPTION, currentProject, () => undefined);
  // الرئيسية توجّه ولا تنفّذ — فما كتبه الباحث هناك يصل هنا مكتوبًا.
  const asked = useSyncExternalStore(NO_SUBSCRIPTION, askedQuestion, () => "");
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const messages = getMessages(locale);
  const t = translator(messages);
  const { modelEnabled, loading } = usePosture(locale);
  const { phase, capabilities } = useAiCapabilities(locale);
  // **مقترحات البداية كانت أزرارًا ميتة.** تُرسم قابلةً للنقر بلا معالج:
  // يضغطها المستخدم فلا يحدث شيء، ولا رسالة تقول لماذا. وهي الآن تملأ
  // المدخل بنصّها، فيعدّله المستخدم ويرسله.
  const [seed, setSeed] = useState("");

  return (
    <>
      <div className="page-head">
        <h1>{t("ai.title")}</h1>
        <p>{t("ai.subtitle")}</p>
      </div>

      <section style={{ maxInlineSize: "78ch", marginBlockEnd: 30 }}>
        <AtheraAiInput
          locale={locale}
          messages={messages}
          rows={4}
          seed={seed || asked}
          attachFileId={attachFileId}
          projectId={projectId}
        />
      </section>

      <section style={{ marginBlockEnd: 30 }}>
        <p className="nav-label" style={{ paddingInline: 0, marginBlockEnd: 10 }}>
          {t("ai.startersLabel")}
        </p>
        <div className="starters">
          {INTENTS.map((key) => (
            <button
              type="button"
              className="starter"
              key={key}
              disabled={loading || !modelEnabled}
              onClick={() => setSeed(t(`ai.${key}`))}
            >
              {t(`ai.${key}`)}
            </button>
          ))}
        </div>
      </section>

      {/* ── ما يستطيعه اليوم، بلغته هو ──
          والثلاثيةُ تُقرأ بأطرافها: «جارٍ» قبل الجواب، وتعذّرُ السؤال
          يُقال تعذّرًا — لا يُقرأ «غير متاح»، فتلك دعوى لم تُفحص. */}
      <section className="card" style={{ maxInlineSize: "78ch", marginBlockEnd: 24 }}>
        <h2 style={{ marginBlockStart: 0 }}>{t("ai.canDoTitle")}</h2>
        {phase === "loading" ? <p>{t("app.loading")}</p> : null}
        {phase === "failed" ? (
          <p className="metric-label">{t("ai.canDoUnknown")}</p>
        ) : null}
        {phase === "ready" && capabilities ? (
          <ul style={{ margin: 0, paddingInlineStart: "1.1rem", fontSize: 14 }}>
            <li data-testid="cap-reference-discovery">
              {capabilities.reference_discovery_available
                ? `${t("ai.capSearchOn")} — ${capabilities.reference_discovery_providers.join("، ")}`
                : t("ai.capSearchOff")}
            </li>
            <li data-testid="cap-full-text">
              {capabilities.full_text_retrieval_available
                ? t("ai.capFullTextOn")
                : t("ai.capFullTextOff")}
            </li>
            <li data-testid="cap-monitoring">
              {capabilities.literature_registry_available
                ? t("ai.capMonitoringOn")
                : t("ai.capMonitoringOff")}
            </li>
          </ul>
        ) : null}
      </section>

      <section className="card" style={{ maxInlineSize: "78ch", marginBlockEnd: 24 }}>
        <h2 style={{ marginBlockStart: 0 }}>{t("ai.deterministic")}</h2>
        <p style={{ color: "var(--muted)", fontSize: 14, marginBlockEnd: 0 }}>
          {t("ai.deterministicBody")}
        </p>
      </section>

      {/*
        ── ما حُذف من هنا: شبكةُ «حالة التشغيل الحيّة» ──

        كانت هذه الشاشة تعرض على الباحث بطاقاتٍ فيها قيمُ التشغيل الخام
        كما يرسلها الخادم: `anthropic`، و`offline`، و`not_configured`،
        و`s3`. وهي أسماءُ مزوّدين وحالاتُ بنيةٍ تحتية لا معنى لها في عملٍ
        علمي — والباحث الذي يقرأ «anthropic» لا يعرف هل يستطيع أن يكمل
        بحثه أم لا، وهو السؤال الوحيد الذي يخصّه.

        **وكانت الشارة تلوّن ولا تقول.** `chip-ok` خضراء و`chip-muted`
        رمادية، والقيمة الخام وحدها في وسطها؛ فمن لا يميّز اللونين يقرأ
        كلمةً إنجليزية بلا حكم. لونٌ يحمل المعنى وحده.

        وموضعُ هذه القيم «الإعدادات ← وضع التشغيل» — وهي معروضةٌ هناك
        بالفعل، بعنوانٍ مترجَم وشرحٍ لكل بند. ولا تُنسخ هنا.

        وما يخصّ الباحث من هذا كلّه شيءٌ واحد: هل يستطيع أن يسأل الآن؟
        وذاك يقوله شريطُ البوابة في المربّع أعلاه — ومعه الفعل التالي
        الصالح، لا حالةُ مزوّد.
      */}
    </>
  );
}
