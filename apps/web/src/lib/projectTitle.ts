/**
 * عنوانُ المشروع كما يُعرض | The shared project-title presentation contract.
 *
 * **عيبٌ حقيقيّ وقع**: عُرضت للباحث بحوثٌ عناوينها من هذا النوع —
 *
 *     قبول 2026-09-09T17:12:41.883012+00:00
 *
 * وهذه ليست عنوانًا. هي نصُّ حدثٍ في سجلّ التدقيق ووقتُه، لُصقا معًا
 * وعُرضا في موضع العنوان. فيقرأ الباحث قائمة بحوثه ولا يعرف أيّها بحثه.
 *
 * ## القاعدة
 *
 *   **لا يُصنَع عنوانٌ من شيء.** لا من نصِّ تدقيق، ولا من طابعٍ زمني، ولا
 *   من أول جملةٍ في وصف، ولا من اسم ملفٍّ مرفوع.
 *
 * فإن لم يكن للبحث عنوانُ عملٍ ذو معنًى، قيل ذلك صراحةً، وعُرض تاريخ
 * الإنشاء **في حقلٍ منفصل**، وأُتيحت إعادة التسمية. وثلاثتها معًا:
 * الإعلان بلا سبيلٍ إلى التصحيح يترك الباحث حيث هو.
 *
 * ## ولماذا هنا لا في الشاشة
 *
 * أربعُ شاشاتٍ تعرض عناوين بحوث (المحفظة، الفريق، الخيط الذهبي، السلّة).
 * ولو نُسخت القاعدة في كلٍّ منها لعادت الخامسةُ تعرض `قبول 2026-…` بعد أن
 * أُصلحت أربع. فالقاعدة هنا، ونظيرتها الحرفية في
 * `apps/api/athera_api/services/project_management/titles.py`، ويقابل
 * بينهما اختبارٌ في حزمة القبول.
 */

/** العنوانُ الذي يُعرض حين لا عنوان — **وبلا رقمٍ فيه**. */
export const PLACEHOLDER_AR = "مشروع بدون عنوان";
export const PLACEHOLDER_EN = "Untitled project";

/**
 * طابعٌ زمنيّ بصيغة ISO — `2026-09-09T17:12:41` وما شابهها.
 *
 * **لا يكتب باحثٌ هذا في عنوان ورقة**، فوجودُه شاهدُ تلفيقٍ لا اختيارِ
 * صاحبه.
 */
const ISO_TIMESTAMP = /\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/;

/** نصٌّ لا يحمل حرفًا واحدًا — أرقامٌ وتواريخُ وعلاماتُ ترقيم وحدها. */
const HAS_A_LETTER = /\p{L}/u;

export type PlaceholderReason = "blank" | "audit_timestamp" | "no_letters";

export interface ProjectTitleFields {
  display_ar: string;
  display_en: string;
  is_placeholder: boolean;
  placeholder_reason: PlaceholderReason | null;
  created_at: string | null;
  can_rename: boolean;
}

/**
 * ثلاثُ حالاتٍ ترفض، ولا رابعة — **والتضييق مقصود**.
 *
 * رفضُ عنوانٍ صحيح أسوأ من قبول عنوانٍ رديء: باحثٌ سمّى بحثه «دراسة 2024»
 * يجب أن يرى اسمه كما كتبه، لا بديلًا يمحو اختياره.
 */
function manufacturedReason(value: string): PlaceholderReason | null {
  if (!value) return "blank";
  if (ISO_TIMESTAMP.test(value)) return "audit_timestamp";
  if (!HAS_A_LETTER.test(value)) return "no_letters";
  return null;
}

/**
 * العقد: نصٌّ يُعرض كما كتبه صاحبه، أو بديلٌ يقول إنه بديل.
 *
 * **ولا حالة ثالثة** — ولا تركيبَ عنوانٍ من التاريخ ولا من غيره.
 */
export function projectTitle(
  workingTitleAr: string | null | undefined,
  createdAt: string | null = null,
): ProjectTitleFields {
  const trimmed = (workingTitleAr ?? "").trim();
  const reason = manufacturedReason(trimmed);
  if (reason !== null) {
    return {
      display_ar: PLACEHOLDER_AR,
      display_en: PLACEHOLDER_EN,
      is_placeholder: true,
      placeholder_reason: reason,
      created_at: createdAt,
      can_rename: true,
    };
  }
  return {
    display_ar: trimmed,
    display_en: trimmed,
    is_placeholder: false,
    placeholder_reason: null,
    created_at: createdAt,
    can_rename: true,
  };
}

/**
 * ما يُعرض من عقدٍ جاء من الخادم — والخادم يطبّق القاعدة نفسها.
 *
 * وهذه الدالّة للشاشات: تأخذ ما ردّه الخادم وتعطي النصّ بلغة العرض، ولا
 * تعيد الحساب. وشاشةٌ تحسب بنفسها فوق حساب الخادم تُنتج حكمين قد يفترقان.
 */
export function displayTitle(fields: ProjectTitleFields, locale: string): string {
  return locale === "en" ? fields.display_en : fields.display_ar;
}
