/**
 * توجيه اللغة | Locale routing (§26.4).
 *
 * `/` ⇄ العربية افتراضيًا، مع احترام تفضيل محفوظ أو ترويسة Accept-Language.
 * كل مسار في التطبيق يحمل لغته صراحةً — لا حالة لغة مخفية في الجلسة.
 */
import { NextRequest, NextResponse } from "next/server";

const LOCALES = ["ar", "en"] as const;
const DEFAULT_LOCALE = "ar";
const COOKIE = "athera_locale";

function pickLocale(request: NextRequest): string {
  const saved = request.cookies.get(COOKIE)?.value;
  if (saved && (LOCALES as readonly string[]).includes(saved)) return saved;

  const header = request.headers.get("accept-language") ?? "";
  for (const part of header.split(",")) {
    const code = part.split(";")[0]?.trim().toLowerCase().split("-")[0];
    if (code && (LOCALES as readonly string[]).includes(code)) return code;
  }
  return DEFAULT_LOCALE;
}

/**
 * **الجذرُ موقعٌ عام، لا بابُ تطبيق.**
 *
 * كان `/` يُحوَّل إلى `‎/ar` — وهو تطبيقٌ محميّ يقذف من لا جلسة له إلى
 * الدخول. فمن كتب اسم النطاق بلغ نموذج دخولٍ لمنتجٍ لا يعرف ما هو.
 *
 * فالجذرُ **يُعاد كتابته** إلى الصفحة العامّة بلغة الزائر، ولا يُحوَّل:
 * الرابط يبقى النطاق وحده كما كتبه، والمستند يحمل `lang` و`dir` صحيحين
 * لأن اللغة صارت في المسار الداخلي لا في استعلام لا يراه التخطيط.
 */
const MARKETING_ROOT = "/welcome";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // والجذرُ و`‎/welcome` بلا لغةٍ سواء: كلاهما يُعاد كتابته إلى لغة الزائر.
  if (pathname === "/" || pathname === MARKETING_ROOT) {
    const url = request.nextUrl.clone();
    url.pathname = `${MARKETING_ROOT}/${pickLocale(request)}`;
    return NextResponse.rewrite(url);
  }

  // الموقع العام يحمل لغته في مساره، فلا يمرّ على توجيه اللغة.
  if (pathname.startsWith(`${MARKETING_ROOT}/`)) {
    return NextResponse.next();
  }

  const hasLocale = LOCALES.some(
    (locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`),
  );

  if (hasLocale) {
    const active = pathname.split("/")[1]!;
    const response = NextResponse.next();
    response.cookies.set(COOKIE, active, { path: "/", sameSite: "lax" });
    return response;
  }

  const url = request.nextUrl.clone();
  url.pathname = `/${pickLocale(request)}${pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!api|_next|favicon.ico|.*\\..*).*)"],
};
