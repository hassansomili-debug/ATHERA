"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/**
 * ما تستطيعه بُبريفا AI الآن — **بلغة الباحث لا بلغة التشغيل**.
 *
 * وكانت شاشة AI تعرض بطاقات وضع التشغيل كما هي: اسمُ مزوّد النموذج، وحالُ
 * تخزين S3، وسقفُ تصنيف البيانات C1. وتلك تشخيصُ بنيةٍ تحتية لمن ينشر
 * الخادم، لا للباحث الذي جاء ليكتب ورقة — وعرضُها له يجعل سطحَ عمله يبدو
 * لوحةَ عمليات.
 *
 * **وثلاثُ قدراتٍ لا واحدة.** كان في الخادم منطقٌ واحد يطوي اكتشافَ
 * المراجع في سجلّ الرصد المجدول، فتقول الشاشة إنّ البحث معطّل وهو يعمل.
 */
export interface AiCapabilities {
  assistant_available: boolean;
  reference_discovery_available: boolean;
  reference_discovery_providers: string[];
  literature_registry_available: boolean;
  full_text_retrieval_available: boolean;
}

export interface AiCapabilitiesState {
  /** `loading` | `ready` | `failed` — ثلاثيةٌ تُقرأ بأطرافها الثلاثة. */
  phase: "loading" | "ready" | "failed";
  capabilities: AiCapabilities | null;
}

export function useAiCapabilities(locale: Locale): AiCapabilitiesState {
  const [phase, setPhase] = useState<"loading" | "ready" | "failed">("loading");
  const [capabilities, setCapabilities] = useState<AiCapabilities | null>(null);

  useEffect(() => {
    let active = true;
    void apiFetch<AiCapabilities>("/api/v1/ai/capabilities", { locale })
      .then((data) => {
        if (!active) return;
        setCapabilities(data);
        setPhase("ready");
      })
      .catch(() => {
        // **ولا يُدَّعى شيء عن قدرةٍ لم تُسأل.** «تعذّر السؤال» ليس
        // «الجواب: غير متاح» — والثاني دعوى عن حال الخادم لم تُفحص.
        if (active) setPhase("failed");
      });
    return () => {
      active = false;
    };
  }, [locale]);

  return { phase, capabilities };
}
