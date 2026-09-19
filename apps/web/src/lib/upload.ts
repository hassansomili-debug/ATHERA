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
import {
  AtheraApiError, apiFetch, intentRefusal, isApiMisconfigured, type ApiError,
} from "./api";
import type { Locale } from "./i18n";
import {
  intentFingerprint,
  isProtectedRequest,
  keyForIntent,
  resolveIntent,
  shouldRetainIntent,
} from "./idempotency";
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

/**
 * ══ ونقلان، ومفتاحٌ واحد (Stage 6) ══
 *
 * **وهذا كان العطبَ الصريح.** الرفعُ يبدأ بـ`XMLHttpRequest`، فإن ردَّ
 * الخادمُ ٤٠١ سقط إلى `apiFetch`. ولمّا كان لكلِّ نقلٍ توليدُه الخاصّ صار
 * الطلبان **طلبَين مستقلَّين** في نظر الخادم — فرفعةٌ واحدةٌ تُنتج كائنَين.
 *
 * فيُعَدُّ المفتاحُ هنا مرّةً واحدة، ويُمرَّر إلى النقلين معًا.
 */
export function uploadWithProgress<T>(
  path: string,
  body: FormData,
  options: {
    locale: Locale;
    onProgress?: (progress: UploadProgress) => void;
    /**
     * هُويّةُ نيّةِ هذا العنصر — **لازمةٌ للمسارات المحميّة**.
     *
     * فملفّان مختلفان قد يتّفقان في الاسم والحجم والنوع، و`FormData` لا
     * يُقرأ محتواه لبناء بصمة. فعنصرُ الطابور هو الذي يحمل هُويّتَه.
     */
    intentId?: string;
  },
): Promise<T> {
  const { locale, onProgress, intentId } = options;

  if (isApiMisconfigured()) {
    // العميل يعلن الخلل نفسه برسالته المشروحة — فيُمرّ عليه بلا رفع.
    return apiFetch<T>(path, { method: "POST", locale, body, intentId });
  }

  const protectedRoute = isProtectedRequest("POST", path);
  const ticket = protectedRoute
    ? intentFingerprint({ method: "POST", path, body: "__form_data__", intentId })
        .then((fingerprint) => ({ fingerprint, key: keyForIntent(fingerprint) }))
        // ولا يُفتح `XMLHttpRequest` أصلًا إن رُفضت النيّة — الرفضُ قبل النقل.
        .catch((cause) => { throw intentRefusal(cause, locale); })
    : Promise.resolve(null);

  return ticket.then((intent) => new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${BASE_URL}${path}`);
    request.setRequestHeader("Accept-Language", locale);
    const bearer = getAccessToken();
    if (bearer) request.setRequestHeader("Authorization", `Bearer ${bearer}`);
    if (intent) request.setRequestHeader("Idempotency-Key", intent.key);
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
        // نجاحٌ يحسم النيّة — فرفعةٌ جديدةٌ تأخذ مفتاحًا جديدًا.
        if (intent) resolveIntent(intent.fingerprint);
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
        // **وبالمفتاح نفسِه**: تبديلُ النقلِ ليس نيّةً جديدة.
        apiFetch<T>(path, {
          method: "POST", locale, body, intentId,
          idempotencyKey: intent?.key,
        }).then(resolve, reject);
        return;
      }
      let payload: { error?: ApiError } | null = null;
      try {
        payload = JSON.parse(request.responseText) as { error?: ApiError };
      } catch {
        payload = null;
      }
      // يبقى المفتاحُ للغامض، ويُحرَّر للمحسوم.
      if (intent && !shouldRetainIntent(status, payload?.error?.code)) {
        resolveIntent(intent.fingerprint);
      }
      reject(payload?.error
        ? new AtheraApiError(status, payload.error)
        : genericError(locale, status));
    };

    // انقطاعُ الشبكة ليس ردًّا: `status` يساوي صفرًا، ولا جسم يُقرأ منه سبب.
    // **والنيّةُ تبقى معلَّقةً بمفتاحها** — فالخادمُ قد يكون أودع.
    request.onerror = () => reject(genericError(locale, 0));
    request.onabort = () => reject(genericError(locale, 0));

    request.send(body);
  }));
}
