"use client";

import { use } from "react";

import { SectionWorkspace } from "@/components/SectionWorkspace";
import { DEFAULT_LOCALE, isLocale } from "@/lib/i18n";

/** صياغة المنهجية (S5E-B) — قسمٌ واحد على مساحة العمل المشتركة. */
export default function MethodsPage({
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
      sectionKey="method"
      copy="methods"
    />
  );
}
