"use client";

import { use } from "react";

import { SectionWorkspace } from "@/components/SectionWorkspace";
import { DEFAULT_LOCALE, isLocale } from "@/lib/i18n";

/**
 * صياغة النتائج (S5E-C) — **بوضعٍ صارم**.
 *
 * الفرق عن المنهجية ليس في الشكل: كل قيمة إحصائية هنا تحتاج مخرَج تحليل
 * بعينه. فتُعرض المخرجات المؤهَّلة، ويُعرض ما حُجب من الأدلة لأنه بلا سند —
 * كي يعرف الباحث لماذا غاب رقم يعرفه، بدل أن يظن الأداة نسيته.
 */
export default function ResultsPage({
  params,
}: {
  params: Promise<{ locale: string; manuscriptId: string }>;
}) {
  const { locale: raw, manuscriptId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;

  return (
    <SectionWorkspace
      locale={locale}
      manuscriptId={manuscriptId}
      sectionKey="results"
      copy="results"
      strict
    />
  );
}
