/**
 * جلسة المتصفح | Browser session (§36).
 *
 * موضع واحد يحمل رمز الوصول، فلا تتفرّق قراءته وكتابته على اثنتين وعشرين
 * شاشة. `apiFetch` يقرأ منه تلقائيًّا، فلا تحتاج شاشة أن تتذكّر تمريره —
 * وهو بالضبط ما نُسي فوقع: الشاشات كانت تستدعي الـAPI بلا ترويسة مصادقة.
 *
 * **الخيار وحدوده:** الرمز في `localStorage` لا في كعكة `httpOnly`. الثمن
 * أن ثغرة XSS تصل إليه؛ والمكسب أن الـAPI يبقى بلا حالة ولا يحتاج حماية
 * CSRF. رمز الوصول قصير (٩٠٠ ثانية) وهو ما يحدّ الضرر. الأمتن نقل رمز
 * التحديث إلى كعكة `httpOnly` — يحتاج تغييرًا في الـAPI، ومسجَّل كدين.
 */
const ACCESS_KEY = "athera_access_token";
const REFRESH_KEY = "athera_refresh_token";
const EXPIRY_KEY = "athera_token_expiry";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/** `localStorage` قد يرمي في وضع التصفح الخاص — القراءة لا تُسقط الصفحة. */
function safeGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* التخزين محجوب: الجلسة تبقى في الذاكرة حتى إعادة التحميل. */
  }
}

let memoryToken: string | null = null;

export function saveSession(tokens: TokenPair): void {
  memoryToken = tokens.access_token;
  safeSet(ACCESS_KEY, tokens.access_token);
  safeSet(REFRESH_KEY, tokens.refresh_token);
  safeSet(EXPIRY_KEY, String(Date.now() + tokens.expires_in * 1000));
}

export function getAccessToken(): string | null {
  return memoryToken ?? safeGet(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return safeGet(REFRESH_KEY);
}

/**
 * هل انتهت صلاحية الرمز؟ يُفحص محليًّا قبل الإرسال.
 *
 * الحكم النهائي للخادم دائمًا — هذا الفحص يوفّر رحلة فاشلة لا أكثر، ولا
 * يُعتمد عليه في المنع.
 */
export function isExpired(): boolean {
  const raw = safeGet(EXPIRY_KEY);
  if (!raw) return false;
  const at = Number(raw);
  return Number.isFinite(at) && Date.now() >= at;
}

export function clearSession(): void {
  memoryToken = null;
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    window.localStorage.removeItem(EXPIRY_KEY);
  } catch {
    /* لا شيء يُفعل: الذاكرة مُسحت أعلاه. */
  }
}

export function isSignedIn(): boolean {
  return Boolean(getAccessToken());
}
