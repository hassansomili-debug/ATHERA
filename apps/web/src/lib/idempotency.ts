/**
 * مفاتيحُ النيّة في المتصفّح | browser intent idempotency (RC-T1-H2 · Stage 6).
 *
 * الخادمُ صار يقبل `Idempotency-Key` على مساراته المحميّة (الأطوار H2-A حتى
 * H2-B5، ثمّ هيكلُ الورقة في المرحلة ٨): يُعيد الجوابَ المخزون، ويرفض مفتاحًا أُعيد بمعنًى آخر، ويمنع نداءَ
 * مزوّدٍ ثانيًا داخل الجيل الواحد. **وكلُّ ذلك معطَّلٌ ما لم يُرسل المتصفّحُ
 * مفتاحًا** — والمتصفّح هو الذي يعرف متى تكون محاولتان نيّةً واحدة.
 *
 * ## الدعوى المأذونة — وحدَها
 *
 *   داخل نافذة بقاءِ الخادم، إعادةُ المحاولةِ لنيّةٍ محميّةٍ واحدة تُعيد
 *   استعمالَ المفتاح نفسِه — ومن ذلك إعادةُ المحاولة بعد تجديد الرمز،
 *   ومسلكُ الرفع البديل. والنيّةُ الجديدةُ المقصودةُ تأخذ مفتاحًا جديدًا.
 *
 * **ولا يُدَّعى**: تنفيذٌ مرّةً واحدةً بالضبط، ولا حمايةٌ لا نهائيّةٌ من
 * الإعادة، ولا طابورٌ دائمٌ في المتصفّح، ولا تنفيذٌ واحدٌ للنموذج أو للتخزين.
 *
 * ## الفرقُ الذي يصعب: نيّةٌ واحدةٌ أم نيّتان؟
 *
 * ولا يصحّ طرفان: مفتاحٌ لكلّ محاولةٍ شبكيّة يُلغي الحمايةَ أصلًا، ومفتاحٌ
 * دائمٌ لكلّ مسارٍ يجعل الباحثَ عاجزًا عن أن يسأل سؤالًا مرّتين عمدًا.
 *
 * فالنيّةُ تُعرَّف ببصمةٍ دلاليّة: الفعلُ، والمسارُ، وهُويّةُ الجسمِ الدلاليّة،
 * وهُويّةٌ صريحةٌ من الواجهة حين لا يكفي الجسم. وتبقى البصمةُ معلَّقةً حتى
 * **تُحسَم** — فالنجاحُ يُحرّرها، والغموضُ يُبقيها.
 */

/** ما يقبله الخادم: `^[A-Za-z0-9_-]{16,128}$`. */
const KEY_PATTERN = /^[A-Za-z0-9_-]{16,128}$/;

/** مِلكُ PUBRIVA وحدَها في `sessionStorage` — ولا تصادمَ مع غيرها. */
const NAMESPACE = "pubriva.idempotency.v1";

/** بقاءُ جيلِ الخادم أربعٌ وعشرون ساعة (الترحيل 0037). */
const SERVER_RETENTION_MS = 24 * 60 * 60 * 1000;

/**
 * الأفقُ الآمنُ للعميل — وهامشُ ساعةٍ دون بقاءِ الخادم.
 *
 * **وانقضاءُ الأفق ليس إذنًا بمفتاحٍ جديد.** كان السكُّ يقع هنا تلقائيًّا،
 * وهو أسوأُ ما في الباب: بين الثالثةِ والعشرين والرابعةِ والعشرين يكون
 * جيلُ K1 حيًّا في الخادم بينما يسكّ المتصفّحُ K2 — فيصيران توليدَين،
 * ويُنفَّذ العملُ مرّتين وقد كُتب مرّة.
 *
 * والمتصفّحُ **لا يعرف** أنفّذ الطلبُ الأوّلُ أم لا. فالنيّةُ المعلَّقةُ
 * الشائخةُ تُغلَق: لا مفتاحَ بديل، ولا طلبَ يخرج، ويُقال السببُ باسمه.
 * وتركُها معلَّقةً كما هي مقصود — تخلّيًا صريحًا عنها يحتاج فعلًا صريحًا،
 * لا دورانَ مفتاحٍ ضمنيًّا.
 */
const REUSE_WINDOW_MS = SERVER_RETENTION_MS - 60 * 60 * 1000;

/**
 * نيّةٌ معلَّقةٌ تجاوزت الأفقَ الآمن — ولا يُسكّ لها بديل.
 *
 * تُرفع **قبل** أيِّ طلب، فلا طفرةَ تخرج في هذه الحال.
 */
export class IdempotencyIntentExpired extends Error {
  readonly code = "idempotency.intent_expired";

  constructor(readonly fingerprint: string, readonly ageMs: number) {
    super(`a pending idempotent intent is older than the safe horizon (${ageMs}ms)`);
    this.name = "IdempotencyIntentExpired";
  }
}

/**
 * لا عشوائيّةَ معمّاةٍ في هذا المتصفّح — فلا مفتاح، ولا طلب.
 *
 * **و`Math.random` ليست بديلًا.** المفتاحُ عقدٌ مُعتِمٌ بين عميلٍ وخادم،
 * وتصادمُه يعني أن تُعاد إجابةُ باحثٍ إلى آخر. فالهبوطُ الصامتُ بالعشوائيّة
 * يُبدّل عطبًا ظاهرًا بعطبٍ لا يُرى.
 */
export class IdempotencyEntropyUnavailable extends Error {
  readonly code = "idempotency.entropy_unavailable";

  constructor() {
    super("no cryptographic randomness is available for an idempotency key");
    this.name = "IdempotencyEntropyUnavailable";
  }
}

export interface PendingIntent {
  /** المفتاحُ المعتِم — **لا يُشتقّ من جسمٍ ولا مستخدمٍ ولا زمن**. */
  key: string;
  /** تجزئةُ المادّةِ الدلاليّة — **لا المادّةُ نفسُها**. */
  fingerprint: string;
  createdAt: number;
}

/**
 * سياسةُ المسارات — **مشتقّةٌ من مصدر الخادم لا من الذاكرة**.
 *
 * كلُّ نمطٍ هنا يقابل معالجًا يمرّ فعلًا بأوليّات الترحيل 0037
 * (`idempotency.begin*`). وما لم يكن كذلك لا يُضاف لمجرّد أنّه `POST`.
 */
const PROTECTED_ROUTES: readonly RegExp[] = [
  // ── H2-A: طفراتٌ ذرّيّةٌ في القاعدة ──
  /^\/api\/v1\/workspace\/projects$/,
  /^\/api\/v1\/portfolio\/projects$/,
  /^\/api\/v1\/analysis\/runs$/,
  /^\/api\/v1\/manuscripts$/,
  // ── H2-B2: قراءاتٌ خارجيّةٌ بـPOST (العقدُ بالمسار لا بالفعل) ──
  /^\/api\/v1\/sources\/search$/,
  /^\/api\/v1\/references\/search$/,
  /^\/api\/v1\/sources\/import$/,
  /^\/api\/v1\/sources\/[^/]+\/verify$/,
  // ── H2-B3: التخزين ──
  /^\/api\/v1\/files$/,
  /^\/api\/v1\/files\/upload$/,
  /^\/api\/v1\/files\/[^/]+\/complete$/,
  // ── H2-B4: النموذج ──
  /^\/api\/v1\/ai\/ask$/,
  /^\/api\/v1\/brain\/ask$/,
  /^\/api\/v1\/manuscripts\/[^/]+\/sections\/[^/]+\/draft$/,
  /^\/api\/v1\/projects\/[^/]+\/publication-opportunities$/,
  // ── H2-C (المرحلة ٨): هيكلُ الورقة — طفرةٌ ذرّيّةٌ بلا مزوّد ──
  /^\/api\/v1\/projects\/[^/]+\/publication-opportunities\/[^/]+\/outline$/,
  /^\/api\/v1\/theses\/[^/]+\/opportunities\/[^/]+\/thread$/,
  /^\/api\/v1\/profile\/import$/,
  // ── H2-B5: معالجةُ الرسالة ──
  /^\/api\/v1\/theses\/upload$/,
  /^\/api\/v1\/theses\/process-file\/[^/]+$/,
  /^\/api\/v1\/theses\/[^/]+\/reprocess$/,
];

/**
 * مساراتُ الرموز — **لا تَرِث أبدًا مفاتيحَ طفراتِ البحث**.
 *
 * ودورانُ الرمز ليس طفرةً علميّة: خلطُهما يعني أن يُعاد جوابُ دخولٍ مخزونٌ
 * على محاولةِ دخولٍ جديدة.
 */
const AUTH_ROUTES: readonly RegExp[] = [
  /^\/api\/v1\/auth\/login$/,
  /^\/api\/v1\/auth\/register$/,
  /^\/api\/v1\/auth\/refresh$/,
  /^\/api\/v1\/auth\/logout$/,
  /^\/api\/v1\/auth\/forgot-password$/,
  /^\/api\/v1\/auth\/reset-password$/,
  /^\/api\/v1\/auth\/change-password$/,
];

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** المسارُ بلا استعلام — فالاستعلامُ ليس هُويّةَ مسار. */
function normalizePath(path: string): string {
  const q = path.indexOf("?");
  return q === -1 ? path : path.slice(0, q);
}

export function isAuthRoute(path: string): boolean {
  return AUTH_ROUTES.some((r) => r.test(normalizePath(path)));
}

/**
 * أيَحمل هذا الطلبُ مفتاحًا؟ — **بالمسارِ والفعلِ معًا**.
 *
 * و`GET`/`HEAD`/`OPTIONS` لا تحمل مفتاحًا بحال: القراءةُ لا تُطفر، وتلويثُها
 * بمفاتيحَ يملأ جدولَ الخادم بلا معنى.
 */
export function isProtectedRequest(method: string, path: string): boolean {
  const verb = (method || "GET").toUpperCase();
  if (!MUTATING.has(verb)) return false;
  const clean = normalizePath(path);
  if (isAuthRoute(clean)) return false;
  return PROTECTED_ROUTES.some((r) => r.test(clean));
}

/** يُستعمل في الحارس والفحوص. */
export const PROTECTED_ROUTE_PATTERNS = PROTECTED_ROUTES;
export const AUTH_ROUTE_PATTERNS = AUTH_ROUTES;

/** مفتاحٌ معتِمٌ عشوائيّ — ٣٢ محرفًا ضمن ما يقبله الخادم. */
export function newIdempotencyKey(): string {
  const c = globalThis.crypto;
  if (c?.randomUUID) return c.randomUUID().replaceAll("-", "");
  if (c?.getRandomValues) {
    const bytes = new Uint8Array(16);
    c.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  // **ولا هبوطَ إلى `Math.random`** — يُغلَق الباب، ولا يُخفَّض العقد.
  throw new IdempotencyEntropyUnavailable();
}

export function isValidKey(key: string): boolean {
  return KEY_PATTERN.test(key);
}

/** ترتيبٌ قانونيٌّ للمفاتيح — فترتيبُ JSON ليس معنًى. */
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(value as Record<string, unknown>).sort()) {
      out[k] = canonical((value as Record<string, unknown>)[k]);
    }
    return out;
  }
  return value;
}

async function sha256Hex(text: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (subtle) {
    const digest = await subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
  }
  // مسلكٌ احتياطيٌّ للبيئات بلا `crypto.subtle` — تجزئةٌ غيرُ تعمويّة، وهي
  // كافيةٌ هنا: البصمةُ تفرّق بين نيّتين في تبويبةٍ واحدة، ولا تحرس سرًّا.
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < text.length; i += 1) {
    h1 = Math.imul(h1 ^ text.charCodeAt(i), 0x01000193) >>> 0;
    h2 = Math.imul(h2 + text.charCodeAt(i), 0x85ebca6b) >>> 0;
  }
  return h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0");
}

/**
 * بصمةُ النيّةِ في المتصفّح — **ليست بصمةَ الخادم العلميّة**.
 *
 * غرضُها واحدٌ لا غير: «أهذه المحاولةُ ما زالت نيّةَ الواجهةِ نفسَها؟».
 * ولا يُبنى عليها تفويضٌ ولا تكافؤٌ علميٌّ ولا كشفُ تعارض — تلك كلُّها
 * للخادم، وبصمتُه هي الحَكَم.
 *
 * **ولا يُحفَظ متنٌ**: ما يُخزَّن تجزئةٌ فقط.
 */
export async function intentFingerprint(input: {
  method: string;
  path: string;
  body?: unknown;
  intentId?: string;
}): Promise<string> {
  const material = JSON.stringify({
    method: (input.method || "POST").toUpperCase(),
    path: normalizePath(input.path),
    intentId: input.intentId ?? null,
    body: input.intentId ? null : canonical(input.body ?? null),
  });
  return sha256Hex(material);
}

// ═══════════════ سجلُّ النيّاتِ المعلَّقة — تبويبةً واحدة ═══════════════
//
// `sessionStorage` **مقصودٌ أنّه محصورٌ بالتبويبة**: استمرارُ الإعادة داخل
// تبويبةِ الباحثِ نفسِها هو ما يُدَّعى، لا أكثر. وتبويبةٌ ثانيةٌ مستقلّةٌ قد
// تُنشئ نيّةً ومفتاحًا آخرَين — والخادمُ يبقى حارسَ الطفرةِ بمستأجرِه وفاعلِه
// ومفتاحِه. ولا يُنقَل هذا إلى `localStorage`: ذاك يُبقي مفاتيحَ نيّاتٍ
// مهجورةٍ عبر الجلسات كلِّها.

const memory = new Map<string, PendingIntent>();

function readAll(): Record<string, PendingIntent> {
  // **والقراءةُ من حيث تقع الكتابة.** بلا `sessionStorage` تُكتب النيّاتُ
  // في الذاكرة، وكانت القراءةُ تردّ `{}` فلا يُعاد مفتاحٌ قطّ — سجلٌّ
  // يكتب ولا يُقرأ ليس سجلًّا.
  try {
    const store = globalThis.sessionStorage;
    if (!store) return Object.fromEntries(memory);
    const raw = store.getItem(NAMESPACE);
    return raw ? (JSON.parse(raw) as Record<string, PendingIntent>) : {};
  } catch {
    return Object.fromEntries(memory);
  }
}

function writeAll(all: Record<string, PendingIntent>): void {
  try {
    if (globalThis.sessionStorage) {
      globalThis.sessionStorage.setItem(NAMESPACE, JSON.stringify(all));
      return;
    }
  } catch {
    /* المخزنُ محجوبٌ أو ممتلئ — تُستعمل الذاكرة. */
  }
  memory.clear();
  for (const [k, v] of Object.entries(all)) memory.set(k, v);
}

/**
 * مفتاحُ هذه النيّة — يُعاد استعمالُه إن كانت معلَّقةً، ويُولَّد إن لم تكن.
 *
 * **والانقضاءُ يفشل مغلقًا**: نيّةٌ معلَّقةٌ تجاوزت نافذةَ بقاءِ الخادم لا
 * يُعاد مفتاحُها — فالصفُّ زال، وإرسالُه يعني تنفيذًا جديدًا يُظَنّ إعادة.
 * فتُسقَط وتُفتح نيّةٌ جديدةٌ صراحةً.
 */
export function keyForIntent(fingerprint: string): string {
  const all = readAll();
  const found = all[fingerprint];
  if (found && isValidKey(found.key)) {
    const age = Date.now() - found.createdAt;
    // داخل الأفق: نيّةٌ واحدةٌ بمفتاحٍ واحد.
    if (age < REUSE_WINDOW_MS) return found.key;
    // **وخارجه يُغلَق الباب.** الصفُّ يبقى كما هو: لا يُمحى ولا يُستبدل،
    // فما زلنا لا نعرف ما فعله الخادمُ بـ`found.key`.
    throw new IdempotencyIntentExpired(fingerprint, age);
  }
  const key = newIdempotencyKey();
  all[fingerprint] = { key, fingerprint, createdAt: Date.now() };
  writeAll(all);
  return key;
}

/** حُسمت النيّة: نجاحًا أو إخفاقًا نهائيًّا — فلا تُعاد بمفتاحها. */
export function resolveIntent(fingerprint: string): void {
  const all = readAll();
  if (fingerprint in all) {
    delete all[fingerprint];
    writeAll(all);
  }
}

/** للفحوص والتشخيص — ولا يُستعمل في منطق الواجهة. */
export function peekIntent(fingerprint: string): PendingIntent | null {
  return readAll()[fingerprint] ?? null;
}

export function clearAllIntents(): void {
  try {
    globalThis.sessionStorage?.removeItem(NAMESPACE);
  } catch {
    /* تُمسح الذاكرةُ على أيّ حال. */
  }
  memory.clear();
}

/**
 * أيَبقى المفتاحُ معلَّقًا بعد هذا الجواب؟
 *
 * **الغموضُ يُبقي، والحسمُ يُحرّر.** فما لا يستطيع المتصفّحُ أن يجزم أنّ
 * الخادمَ لم يُودِعه يبقى بمفتاحه — وإلّا صارت الإعادةُ تنفيذًا ثانيًا.
 *
 * ‏• انقطاعُ نقلٍ (لا جواب أصلًا) ⇒ يبقى.
 * ‏• ٤٠٨/٤٢٥/٤٢٩ و٥xx ⇒ يبقى.
 * ‏• `idempotency.in_progress` و`external_result_unknown` ⇒ يبقى.
 * ‏• نجاحٌ (٢xx) — ومنه الإعادةُ المخزونة ⇒ يُحرَّر.
 * ‏• رفضٌ نهائيٌّ للعميل (٤٠٠/٤٠١ بعد التجديد/٤٠٣/٤٠٤/٤٢٢) ⇒ يُحرَّر.
 * ‏• `idempotency.key_reused` ⇒ يُحرَّر، **ولا يُدوَّر المفتاحُ صامتًا**:
 *   ذاك خطأُ سلامةٍ يُعرَض، لا يُخفى بإعادةٍ بمفتاحٍ آخر.
 */
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const RETRYABLE_CODES = new Set([
  "idempotency.in_progress",
  "idempotency.external_result_unknown",
]);

export function shouldRetainIntent(status: number, code?: string | null): boolean {
  if (status === 0) return true; // انقطاعُ نقلٍ: لا جوابَ يُحكَم به
  if (status >= 200 && status < 300) return false;
  if (code && RETRYABLE_CODES.has(code)) return true;
  return RETRYABLE_STATUS.has(status);
}

/**
 * هُويّةُ نيّةٍ ثابتةٌ لكلِّ **كائنِ ملفٍّ مختار** — لا لاسمه ولا لحجمه.
 *
 * فاسمُ الملفِّ وحجمُه ونوعُه لا تميّزه: ملفّان مختلفان قد يتّفقان فيها
 * الثلاثةَ. وكائنُ `File` نفسُه هو الهُويّة: اختيارٌ جديدٌ يُنتج كائنًا
 * جديدًا فيأخذ مفتاحًا جديدًا، وإعادةُ محاولةٍ على الاختيار نفسِه تُبقيه.
 *
 * و`WeakMap` تمنع تسرّبَ الذاكرة: يزول القيدُ مع زوال الكائن، ولا يُقرأ
 * محتوى الملفّ ولا يُجزَّأ — الخادمُ صاحبُ البصمةِ على البايتات.
 */
const fileIntents = new WeakMap<object, string>();

export function fileIntentId(file: object): string {
  const found = fileIntents.get(file);
  if (found) return found;
  const id = newIdempotencyKey();
  fileIntents.set(file, id);
  return id;
}
