import {
  GRADIENT,
  NODES,
  STROKE_WIDTH,
  THREAD_PATH,
  TONE_HEX,
  VIEW_BOX,
} from "@/lib/brandMarkGeometry";

/**
 * علامةُ المنتج | The product mark — **خيطُ البحث**.
 *
 * الفكرةُ التي ترسمها العلامة هي دعوى المنتج نفسها: البحث خطٌّ واحد
 * متّصل، من السؤال إلى النشر، تمرّ عليه عقدٌ يقف عندها الباحث ويقرّر.
 *
 * **والهندسةُ ليست هنا.** كلُّ إحداثيّ يأتي من `@/lib/brandMarkGeometry`،
 * وهو المصدرُ الذي تُشتقّ منه الصيغُ الأربع أيضًا. ومن كتب المسار هنا
 * وكرّره في الملفّات افترق موضعان لا يلتقيان بعد أوّل تعديل.
 *
 * **ولا اسم مكتوبٌ في الرسم.** الاسم يُقرأ من كتالوج الرسائل ويُمرَّر
 * `label`؛ وحيث تُذكر العلامةُ بجانب الاسم مكتوبًا تُمرَّر بلا `label` —
 * فتُخفى عن قارئ الشاشة بدل أن تُقال مرّتين.
 *
 * والمعرّفات مُوسَّمة بـ`idSuffix` فريد: العلامةُ تظهر مرّتين في صفحةٍ
 * واحدة (الرأس والتذييل)، ومعرّفان متطابقان يجعلان الرسم الثاني يستعير
 * تدرّج الأول — وقد يختفي إن أُزيل الأول من الشجرة.
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
      viewBox={VIEW_BOX}
      fill="none"
      role={label ? "img" : undefined}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {label ? <title>{label}</title> : null}
      <defs>
        <linearGradient
          id={gradient}
          x1={GRADIENT.x1}
          y1={GRADIENT.y1}
          x2={GRADIENT.x2}
          y2={GRADIENT.y2}
          gradientUnits="userSpaceOnUse"
        >
          <stop
            offset="0"
            style={{ stopColor: `var(${GRADIENT.from}, ${GRADIENT.fromHex})` }}
          />
          <stop
            offset="1"
            style={{ stopColor: `var(${GRADIENT.to}, ${GRADIENT.toHex})` }}
          />
        </linearGradient>
      </defs>
      {/*
        الخيطُ مسارٌ `stroke` لا شكلٌ ممتلئ — فيبقى مقروءًا عند ستّة عشر
        بكسلًا كما هو عند مئةٍ وستّين، ولا تنطبق حوافّه على بعضها.
      */}
      <path
        d={THREAD_PATH}
        stroke={`url(#${gradient})`}
        strokeWidth={STROKE_WIDTH}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {NODES.map((node) => (
        <circle
          key={`${node.cx}-${node.cy}`}
          cx={node.cx}
          cy={node.cy}
          r={node.r}
          style={{
            fill: `var(--brand-${node.tone}, ${TONE_HEX[node.tone]})`,
          }}
        />
      ))}
    </svg>
  );
}
