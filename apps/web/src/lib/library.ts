/**
 * مكتبة الباحث | The researcher's library.
 *
 * **تعريفٌ واحد لملف المكتبة.** كان الشكل مُعلنًا داخل صفحة المكتبة وحدها،
 * فأول شاشةٍ أخرى تحتاجه تنسخه — ونسختان تفترقان بأول حقلٍ يُضاف، فتقرأ
 * إحداهما حقلًا لا تعرفه الأخرى. فيُستخرج إلى موضعٍ واحد تقرأه الشاشتان.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

export interface LibraryFile {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
  processing_status: string;
  thesis_id: string | null;
  candidates: number;
  reviewed: number;
}

/** صفحة المكتبة الواحدة، وسقفُ ما يقبله الخادم في طلبٍ واحد. */
export const LIBRARY_PAGE = 25;
export const LIBRARY_MAX_FETCH = 100;

/**
 * صفحةٌ واحدة من الملفات — `after` معرّف آخر ملفٍ رآه المستدعي.
 *
 * **والمسار صار محدودًا.** كان يردّ كل ملفات المستأجر دفعةً واحدة ويشتقّ
 * حال كلٍّ منها باستعلامٍ مستقل، فمكتبةٌ تكبر تُبطئ نفسها حتى تسقط.
 */
export const listLibraryFilePage = (
  locale: Locale,
  options: { limit?: number; after?: string } = {},
) => {
  const limit = Math.min(options.limit ?? LIBRARY_PAGE, LIBRARY_MAX_FETCH);
  const cursor = options.after ? `&after=${encodeURIComponent(options.after)}` : "";
  return apiFetch<LibraryFile[]>(`/api/v1/files?limit=${limit}${cursor}`, { locale });
};

/**
 * **قائمةٌ للاختيار منها** — لا صفحةٌ تُتصفَّح.
 *
 * شاشة البحث تعرض ملفات الباحث ليختار منها ما يربطه ببحثه، ومن يختار يحتاج
 * أن يرى ما يملك. فلمّا صار المسار محدودًا كانت الصفحة الأولى وحدها تعني أن
 * أقدم ملفاته تختفي من قائمة الاختيار بلا أن يقال له شيء — نقصٌ صامت أسوأ
 * من بطء. فتُطلب الصفحات تباعًا حتى تنتهي أو يُبلغ سقفٌ معلن: قائمة اختيار
 * تُصدر طلباتٍ بلا حدّ ليست أفضل من قائمةٍ بلا حدّ.
 */
export const LIBRARY_PICKER_CAP = 300;

export async function listLibraryFiles(locale: Locale): Promise<LibraryFile[]> {
  const all: LibraryFile[] = [];
  let after: string | undefined;
  while (all.length < LIBRARY_PICKER_CAP) {
    const page = await listLibraryFilePage(locale, { limit: LIBRARY_MAX_FETCH, after });
    all.push(...page);
    if (page.length < LIBRARY_MAX_FETCH) break;
    after = page[page.length - 1]?.id;
    if (!after) break;
  }
  return all;
}

/** الشكل الذي يردّه `POST /files/upload` — أقلُّ من `LibraryFile` بحقول الحال. */
export interface StoredFile {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  classification: string;
  status: string;
  created_at: string;
}

/**
 * الملف الذي رُفع للتوّ، بشكل بطاقة المكتبة.
 *
 * **وليست حقول الحال اختلاقًا.** `POST /files/upload` يُنشئ صفّ الملف
 * وحده: لا رسالة، ولا تشغيلة استخراج، ولا مرشّح واحد — والقراءة والاستخراج
 * مسارٌ لاحق لا يبدأ إلا بضغط الباحث «معالجة المستند». فهذه بعينها القيم
 * التي يردّها المسار لهذا الملف لو سُئل عنه في اللحظة نفسها، ويحرسها
 * `test_at_library_scale.py` قيمةً بقيمة. والعرض الفوري هنا حتى لا يرى
 * الباحث «تم الحفظ» ومكتبته خالية منه.
 */
export const libraryFileFromUpload = (stored: StoredFile): LibraryFile => ({
  id: stored.id,
  original_filename: stored.original_filename,
  content_type: stored.content_type,
  size_bytes: stored.size_bytes,
  status: stored.status,
  created_at: stored.created_at,
  processing_status: "not_processed",
  thesis_id: null,
  candidates: 0,
  reviewed: 0,
});
