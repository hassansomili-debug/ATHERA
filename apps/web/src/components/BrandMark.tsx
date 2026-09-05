/**
 * علامةُ المنتج | The product mark — **خيطُ البحث**.
 *
 * الفكرةُ التي ترسمها العلامة هي دعوى المنتج نفسها: البحث خطٌّ واحد
 * متّصل، من المشكلة إلى النشر، تمرّ عليه عقدٌ يقف عندها الباحث ويقرّر.
 * فالرسم خطٌّ **واحد** لا ينقطع، يصعد ثمّ يلتفّ فيقرأ حرفَ الاسم الأول،
 * ثمّ يمضي إلى عقدةٍ أخيرة — هي النشر.
 *
 * **ولا اسم مكتوبٌ في الرسم.** الاسم يُقرأ من كتالوج الرسائل ويُمرَّر
 * `label`؛ ومن كتبه في الشيفرة افترق موضعان لا يلتقيان بعد إعادة تسمية.
 * وحيث تُذكر العلامةُ بجانب الاسم مكتوبًا تُمرَّر بلا `label` — فتُخفى
 * عن قارئ الشاشة بدل أن تُقال مرّتين.
 *
 * والمعرّفات مُوسَّمة بـ`id` فريد: العلامةُ تظهر مرّتين في صفحةٍ واحدة
 * (الرأس والتذييل)، ومعرّفان متطابقان يجعلان الرسم الثاني يستعير تدرّج
 * الأول — وقد يختفي إن أُزيل الأول من الشجرة.
 */
export function BrandMark({
  label,
  size = 34,
  className = "brand-mark",
  idSuffix = "a",
}: {
  /** الاسم المُعلَن — يُقرأ من الكتالوج. وبلا اسمٍ تُخفى عن قارئ الشاشة. */
  label?: string;
  size?: number;
  className?: string;
  idSuffix?: string;
}) {
  const gradient = `thread-${idSuffix}`;
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      role={label ? "img" : undefined}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {label ? <title>{label}</title> : null}
      <defs>
        <linearGradient id={gradient} x1="8" y1="44" x2="40" y2="6" gradientUnits="userSpaceOnUse">
          <stop offset="0" style={{ stopColor: "var(--brand-indigo, #4B46A9)" }} />
          <stop offset=".58" style={{ stopColor: "var(--brand-violet, #7867F2)" }} />
          <stop offset="1" style={{ stopColor: "var(--brand-teal, #17BEBB)" }} />
        </linearGradient>
      </defs>
      {/*
        الخيط: قدمٌ ثمّ صعودٌ ثمّ التفافٌ يقرأ الحرف، ثمّ امتدادٌ إلى النشر.
        وهو مسارٌ واحد `stroke` لا شكلٌ ممتلئ — فيبقى مقروءًا عند ٱثني عشر
        بكسلًا (الأيقونة) كما هو عند مئة.
      */}
      <path
        d="M16 40V9c8.7 0 13.6 2.9 13.6 8.6 0 5.6-4.9 8.6-13.6 8.6"
        stroke={`url(#${gradient})`}
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M16 40h16"
        stroke={`url(#${gradient})`}
        strokeWidth="4"
        strokeLinecap="round"
      />
      {/* العقد: مواضعُ القرار على الخيط. */}
      <circle cx="16" cy="9" r="3.4" style={{ fill: "var(--brand-indigo, #4B46A9)" }} />
      <circle cx="29.6" cy="17.6" r="3.1" style={{ fill: "var(--brand-violet, #7867F2)" }} />
      <circle cx="16" cy="26.2" r="2.8" style={{ fill: "var(--brand-violet, #7867F2)" }} />
      <circle cx="32" cy="40" r="3.6" style={{ fill: "var(--brand-teal, #17BEBB)" }} />
    </svg>
  );
}
