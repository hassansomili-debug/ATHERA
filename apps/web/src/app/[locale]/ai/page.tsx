"use client";

import { use, useState, useSyncExternalStore } from "react";

import { AtheraAiInput } from "@/components/AtheraAiInput";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";

/**
 * أثيرا AI — العقل البحثي.
 *
 * المستخدم يخاطب «أثيرا AI»، ولا يرى ستة عشر أجنتًا ولا أسماءها. السجل
 * التفصيلي باقٍ في «قدرات أثيرا AI» لمن أراد الشفافية، لا في وجه من يريد
 * إنجاز بحث.
 *
 * والنوايا الثماني ليست أزرارًا تدّعي عملًا: ما دام التنفيذ غير مُفعَّل،
 * تبقى معطّلة ويُعلَن سببها — ولا تُولَّد نتيجة واحدة.
 */
const INTENTS = [
  "intentIdea", "intentThesis", "intentSearch", "intentMethod",
  "intentData", "intentManuscript", "intentJournal", "intentReview",
];

/** الرابط لا يتغيّر بلا تنقّل، والتنقّل يعيد التركيب — فلا اشتراك. */
const NO_SUBSCRIPTION = () => () => undefined;
const attachedFile = (): string | undefined =>
  new URLSearchParams(window.location.search).get("file") ?? undefined;
/** فكرةٌ كتبها الباحث في الرئيسية — تصل مكتوبةً في المربّع، لا تُطلب ثانية. */
const askedQuestion = (): string =>
  new URLSearchParams(window.location.search).get("q") ?? "";

export default function AiPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  // **مستندٌ جاء من المكتبة ليُسأل عنه.**
  //
  // ويُقرأ في المتصفّح لا عند التوليد: `searchParams` تُخرج الصفحة من
  // التوليد المسبق وتطلب حدًّا للتعليق، وهذه قيمةٌ لا وجود لها أصلًا قبل
  // أن ينقر الباحث. ولا يُضبط داخل `useEffect` — تصيير متتالٍ يمنعه
  // `react-hooks/set-state-in-effect`، و`useSyncExternalStore` هي الأداة
  // الموضوعة لهذا: لقطةٌ على العميل وأخرى على الخادم تمنع اختلاف الترطيب.
  const attachFileId = useSyncExternalStore(NO_SUBSCRIPTION, attachedFile, () => undefined);
  // الرئيسية توجّه ولا تنفّذ — فما كتبه الباحث هناك يصل هنا مكتوبًا.
  const asked = useSyncExternalStore(NO_SUBSCRIPTION, askedQuestion, () => "");
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const messages = getMessages(locale);
  const t = translator(messages);
  const { modelEnabled, loading } = usePosture(locale);
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
