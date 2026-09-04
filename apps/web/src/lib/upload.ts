/**
 * رفعٌ بتقدّم مرئي | Upload with real progress.
 *
 * **`fetch` لا يقول كم رُفع.** لا يملك حدثًا لتقدّم الإرسال إطلاقًا، فباحثٌ
 * يرفع كتابًا بمئة ميجابايت على شبكةٍ متوسطة ينتظر دقائق أمام زرٍّ مكتوب
 * عليه «جارٍ الرفع…» لا يتغيّر. فيظنّ الشاشة متجمّدة، فيغلقها أو يعيد
 * المحاولة — ورفعُه كان يمضي. و`XMLHttpRequest` وحده يعطي
 * `upload.onprogress` بنسبةٍ حقيقية من البايتات المرسلة، فيُستعمل هنا.
 *
 * **ولا يُستنسخ عميل الـAPI.** الرمز يُقرأ من الجلسة نفسها، والخطأ يُلفّ
 * في `AtheraApiError` نفسه بلغتيه، وخللُ الإعداد يُعلن قبل الطلب — وهي
 * الضمانات التي فقدها من كتب `fetch` خامًّا من قبل. والتجديد وحده لا
 * يُعاد بناؤه: 401 يعيد المحاولة عبر `apiFetch` الذي يملك التجديد الواحد
 * في الطيران، فتُفقد نسبةُ تلك المحاولة وحدها ولا تُفقد الجلسة.
 */
import { AtheraApiError, apiFetch, isApiMisconfigured, type ApiError } from "./api";
import type { Locale } from "./i18n";
import { getAccessToken } from "./session";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** ما رُفع من الإجمالي — و`total` صفرٌ حين لا يعلنه المتصفح. */
export interface UploadProgress {
  loaded: number;
  total: number;
}

const genericError = (locale: Locale, status: number) =>
  new AtheraApiError(status, {
    code: "server.error",
    locale,
    message: "Request failed",
    messages: { ar: "فشل الطلب.", en: "Request failed." },
  });

export function uploadWithProgress<T>(
  path: string,
  body: FormData,
  options: { locale: Locale; onProgress?: (progress: UploadProgress) => void },
): Promise<T> {
  const { locale, onProgress } = options;

  if (isApiMisconfigured()) {
    // العميل يعلن الخلل نفسه برسالته المشروحة — فيُمرّ عليه بلا رفع.
    return apiFetch<T>(path, { method: "POST", locale, body });
  }

  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${BASE_URL}${path}`);
    request.setRequestHeader("Accept-Language", locale);
    const bearer = getAccessToken();
    if (bearer) request.setRequestHeader("Authorization", `Bearer ${bearer}`);
    // لا `Content-Type` هنا: الحدّ الفاصل لـ`FormData` يولّده المتصفح،
    // وفرضُ نوعٍ فوقه يُنتج طلبًا لا يستطيع الخادم تفكيكه.

    if (onProgress) {
      request.upload.onprogress = (event) => {
        onProgress({ loaded: event.loaded, total: event.lengthComputable ? event.total : 0 });
      };
    }

    request.onload = () => {
      const status = request.status;
      if (status >= 200 && status < 300) {
        try {
          resolve((request.responseText ? JSON.parse(request.responseText) : undefined) as T);
        } catch {
          reject(genericError(locale, status));
        }
        return;
      }
      // **الجلسة تُجدَّد حيث يُحرس التجديد.** إعادةُ بنائه هنا تعني رمزَي
      // تحديثٍ يُستعملان معًا، فيُبطل الأول الثاني وتُمحى جلسةٌ صالحة.
      if (status === 401) {
        apiFetch<T>(path, { method: "POST", locale, body }).then(resolve, reject);
        return;
      }
      let payload: { error?: ApiError } | null = null;
      try {
        payload = JSON.parse(request.responseText) as { error?: ApiError };
      } catch {
        payload = null;
      }
      reject(payload?.error
        ? new AtheraApiError(status, payload.error)
        : genericError(locale, status));
    };

    // انقطاعُ الشبكة ليس ردًّا: `status` يساوي صفرًا، ولا جسم يُقرأ منه سبب.
    request.onerror = () => reject(genericError(locale, 0));
    request.onabort = () => reject(genericError(locale, 0));

    request.send(body);
  });
}
