"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/**
 * حالة التشغيل الحيّة — مصدر بوابات الميزات.
 *
 * البوابة لا تُكتب في الواجهة ولا تُخمَّن: تُقرأ من `/settings/posture`، وهو
 * ما يعلنه الخادم عن نفسه. فإن فُعّل مزوّد نموذج في مرحلة لاحقة، انفتحت
 * الواجهة بلا نشر جديد. وإن تعذّرت القراءة بقيت مغلقة — الافتراض الآمن أن
 * القدرة غير متاحة، لا أنها متاحة.
 */
export interface PostureItem {
  key: string;
  label: string;
  value: string;
  detail: string;
}

/**
 * لماذا القدرة مغلقة — **وليست كل الأسباب واحدًا**.
 *
 *   ready       المزوّد معلَن ومهيّأ
 *   provider    الخادم يقول: لا مزوّد (أو مُسمّى بلا مفتاح)
 *   unreachable لم نستطع أن نسأل أصلًا: غير مسجّل دخول، أو الشبكة، أو
 *               عنوان API غير مضبوط في هذا النشر
 *
 * والفرق ليس تجميلًا. كانت الشاشة تقول «المزوّد مضبوط على لا مزوّد» في
 * الحالتين الأخيرتين — وهي **دعوى عن حالة الخادم لم تُفحَص قط**. فباحثٌ
 * انتهت جلسته يقرأ أن المنصّة غير مفعّلة، وهي تعمل.
 */
export type ModelGateReason = "ready" | "provider" | "unreachable";

export interface Posture {
  loading: boolean;
  items: PostureItem[];
  modelEnabled: boolean;
  /** سبب الإغلاق — يُعرض للمستخدم بدل سببٍ مفترَض. */
  modelGateReason: ModelGateReason;
  literatureOnline: boolean;
}

export function usePosture(locale: Locale): Posture {
  const [items, setItems] = useState<PostureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [reachable, setReachable] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() =>
      apiFetch<{ items: PostureItem[] }>("/api/v1/settings/posture", { locale })
        .then((data) => {
          if (!active) return;
          setItems(data.items);
          // وصلنا وقرأنا — فما نقوله بعدها عن الخادم مسنَدٌ إلى جوابه.
          setReachable(true);
        })
        .catch(() => {
          // **ولا نبتلع الفشل بصمت.** ابتلاعه كان يجعل «تعذّر السؤال»
          // يبدو «الجواب: لا مزوّد» — وهي دعوى لم تُفحَص.
          if (active) setReachable(false);
        })
        .finally(() => {
          if (active) setLoading(false);
        }),
    );
    return () => {
      active = false;
    };
  }, [locale]);

  const valueOf = (key: string) => items.find((i) => i.key === key)?.value;
  // الخادم يعلن `not_configured` لمزوّد مُسمّى بلا مفتاح — فلا نعدّه متاحًا.
  const provider = valueOf("model_provider");
  const declared =
    Boolean(provider) && provider !== "null" && provider !== "not_configured";

  return {
    loading,
    items,
    // البوابة تبقى مغلقة عند الشك — الافتراض الآمن لم يتغيّر.
    modelEnabled: reachable && declared,
    modelGateReason: !reachable ? "unreachable" : declared ? "ready" : "provider",
    literatureOnline: Boolean(valueOf("literature_registry")) && valueOf("literature_registry") !== "offline",
  };
}
