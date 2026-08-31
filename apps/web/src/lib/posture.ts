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

export interface Posture {
  loading: boolean;
  items: PostureItem[];
  modelEnabled: boolean;
  literatureOnline: boolean;
}

export function usePosture(locale: Locale): Posture {
  const [items, setItems] = useState<PostureItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() =>
      apiFetch<{ items: PostureItem[] }>("/api/v1/settings/posture", { locale })
        .then((data) => {
          if (active) setItems(data.items);
        })
        .catch(() => undefined)
        .finally(() => {
          if (active) setLoading(false);
        }),
    );
    return () => {
      active = false;
    };
  }, [locale]);

  const valueOf = (key: string) => items.find((i) => i.key === key)?.value;
  return {
    loading,
    items,
    modelEnabled: Boolean(valueOf("model_provider")) && valueOf("model_provider") !== "null",
    literatureOnline: Boolean(valueOf("literature_registry")) && valueOf("literature_registry") !== "offline",
  };
}
