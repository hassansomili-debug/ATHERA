"use client";

import { use } from "react";

import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { TeamWorkspace } from "@/components/TeamWorkspace";

/**
 * فريقُ المشروع — **الوحدةُ العامّة، ومُنتقي البحث فيها** (§12، §24).
 *
 * والمسارُ باقٍ كما كان: من حفظ رابطَه يجده يعمل، ولا تحويلَ صامتًا إلى
 * صفحة بحث. فهذه لوحةٌ عبرَ الأبحاث — يقرأ فيها الباحثُ ما ينتظره في
 * أبحاثه كلِّها بانتقاءٍ واحد.
 *
 * **والمنطقُ ليس هنا.** انتقل إلى `TeamWorkspace` لمّا صار لقسم البحث
 * (`?section=team`) فريقٌ أيضًا: نسختان من إدارة فريقٍ تفترقان بأوّل
 * تعديل، فتصير إحداهما تعرض الموافقةَ عن غير صاحبها. وهذه الصفحةُ تُمرّر
 * بلا `fixedProjectId` فيبقى المُنتقي، وتلك تُمرّره فيختفي.
 */
export default function TeamPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  return (
    <>
      <h1>{t("team.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("team.subtitle")}</p>
      <p className="provenance-note">{t("team.creditNote")}</p>
      <p className="provenance-note">{t("team.consentIsPersonal")}</p>
      <TeamWorkspace locale={locale} />
    </>
  );
}
