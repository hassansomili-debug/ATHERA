"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { detectIntent, destinationFor } from "@/lib/intent";
import { type Locale, type Messages, translator } from "@/lib/i18n";

/**
 * مربّع البداية في الرئيسية — **موجِّهٌ لا محادثة**.
 *
 * كان هنا مربّعُ «بُبريفا AI» نفسه بحرفه: النصّ نفسه، والأزرار نفسها،
 * والإرسال نفسه. فصارت للمنتج محادثتان في شاشتين، والباحث لا يعرف أيّهما
 * «الحقيقية» ولا أين يجد جوابَ سؤالٍ سأله بالأمس. والرئيسية سؤالُها
 * «ماذا تريد أن تنجز؟» — وهو سؤالُ توجيهٍ لا سؤالُ تنفيذ.
 *
 * فما يقع هنا شيءٌ واحد: يُقرأ ما لصقه الباحث، **ويُقال له أين سيذهب قبل
 * أن يذهب**، ثم يُنقَل إلى السطح الذي ينفّذ. ولا يُولَّد هنا جواب، ولا
 * يُنادى نموذج.
 *
 * **ولا «قريبًا» على شيءٍ يعمل.** الـDOI والرابط يذهبان إلى اكتشاف
 * المراجع — وهو ينادي Crossref وOpenAlex بلا مفتاح ولا إعداد. وكان مربّع
 * الذكاء يعرض «🔗 DOI أو رابط — قريبًا» على قدرةٍ قائمةٍ منذ أشهر.
 */
export function HomeIntake({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const router = useRouter();
  const [value, setValue] = useState("");
  const [going, setGoing] = useState(false);

  // مشتقٌّ في التصيير لا مضبوطٌ في تأثير — فلا تصيير متتالٍ ولا حالة ثانية.
  const intent = detectIntent(value);

  /** ما سيقع، بالكلمات، قبل أن يقع. */
  const preview = intent
    ? {
        doi: { icon: "⌕", text: t("home.routeDoi") },
        url: { icon: "⌕", text: t("home.routeUrl") },
        idea: { icon: "✦", text: t("home.routeIdea") },
      }[intent.kind]
    : null;

  return (
    <form
      className="intake"
      onSubmit={(event) => {
        event.preventDefault();
        if (!intent) return;
        setGoing(true);
        router.push(destinationFor(intent, locale));
      }}
    >
      <label className="sr-only" htmlFor="home-intake">
        {t("home.startPlaceholder")}
      </label>
      <textarea
        id="home-intake"
        rows={3}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={t("home.startPlaceholder")}
      />
      <div className="intake-foot">
        {/*
          **الأيقونة والنصّ معًا، ولا لون يحمل المعنى وحده.** ومن أطفأ
          الألوان أو قرأ بقارئ شاشة يبلغه ما يبلغ غيره: `role="status"`
          يُنطق عند تغيّره.
        */}
        <p className="intake-route" role="status" data-testid="home-intake-route">
          {preview ? (
            <>
              <span aria-hidden="true">{preview.icon}</span> {preview.text}
            </>
          ) : (
            t("home.routeIdle")
          )}
        </p>
        <button type="submit" className="ai-send" disabled={!intent || going}>
          {going ? t("home.startGoing") : t("home.startAction")}
        </button>
      </div>
    </form>
  );
}
