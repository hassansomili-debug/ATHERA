/**
 * §38.6.8 — الواجهة لا تتصل بأي مزود نموذج، إطلاقًا.
 * The web client never reaches a model provider. CSP enforces it in the browser;
 * AT-S0-09 enforces it in CI. `connect-src` allows only our own API.
 */
/**
 * عنوان الـAPI يدخل في `connect-src` **وقت البناء** لا وقت التشغيل.
 *
 * لو نُشرت الواجهة بلا ضبطه، لبُنيت بسياسة تسمح بـlocalhost وحده: الصفحات
 * تُعرض، وكل طلب يُحجب في المتصفح بلا رسالة مفهومة. لذلك يفشل البناء صراحةً
 * — بناء فاشل أرخص من نشر يبدو ناجحًا ولا يعمل.
 */
const API_ORIGIN = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const isHostedBuild = Boolean(process.env.VERCEL) || process.env.CI === "1";
if (isHostedBuild && !process.env.NEXT_PUBLIC_API_BASE_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_BASE_URL is required for a hosted build: it is baked into the " +
      "Content-Security-Policy at build time, so a missing value silently blocks every " +
      "API call in the browser. Set it in the Vercel project's environment variables.",
  );
}

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${API_ORIGIN}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
