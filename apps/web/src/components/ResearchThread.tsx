/**
 * خيط البحث | The Research Thread — لغةُ الهويّة البصريّة.
 *
 * **دعوى المنتج مرسومة:** البحث خطٌّ واحد متّصل، من المشكلة إلى النشر،
 * تمرّ عليه عقدٌ يقف عندها الباحث ويقرّر. فالرسم خطٌّ لا ينقطع، وأربعُ
 * عقدٍ عليه تكبر كلّما تقدّم الخيط.
 *
 * **ولا يُستعمل ورقَ حائط.** موضعُه الصفحةُ العامّة وقشرةُ الحساب
 * والفراغُ الذي لا شيء فيه بعد — لا خلفيّةً لكلّ شاشة. وزخرفةٌ تتكرّر في
 * كلّ موضعٍ تكفّ عن أن تقول شيئًا.
 *
 * وهو مخفيٌّ عن شجرة الإتاحة: ما يقوله الرسمُ مكتوبٌ بجانبه نصًّا، فلو
 * نُطق لقيل الشيءُ مرّتين.
 */
export function ResearchThread({
  className,
  idSuffix = "a",
}: {
  className?: string;
  idSuffix?: string;
}) {
  const gradient = `rt-${idSuffix}`;
  return (
    <svg
      className={className}
      viewBox="0 0 320 180"
      fill="none"
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <linearGradient id={gradient} x1="0" y1="180" x2="320" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" style={{ stopColor: "var(--brand-indigo, #4B46A9)" }} />
          <stop offset=".55" style={{ stopColor: "var(--brand-violet, #7867F2)" }} />
          <stop offset="1" style={{ stopColor: "var(--brand-teal, #17BEBB)" }} />
        </linearGradient>
      </defs>
      {/* الخيط: صعودٌ متعرّج لا خطٌّ مستقيم — البحث لا يمضي في خطٍّ مستقيم. */}
      <path
        d="M14 150C60 150 62 96 104 96s44-58 88-58 46 34 106 34"
        stroke={`url(#${gradient})`}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="14" cy="150" r="6" style={{ fill: "var(--brand-indigo, #4B46A9)" }} />
      <circle cx="104" cy="96" r="7.5" style={{ fill: "var(--brand-violet, #7867F2)" }} />
      <circle cx="192" cy="38" r="9" style={{ fill: "var(--brand-violet, #7867F2)" }} />
      <circle cx="306" cy="72" r="10.5" style={{ fill: "var(--brand-teal, #17BEBB)" }} />
    </svg>
  );
}
