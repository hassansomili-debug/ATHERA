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
  /**
   * موضعُ الملف في المكتبة — **تنظيمٌ لا حالُ دليل**، و`null` هو الجذر.
   *
   * ولا يقول شيئًا عن ربط الملف ببحث ولا عن اعتماد ما استُخرج منه: نقلُه
   * بين مجلَّدين يغيّر هذا الحقل وحده.
   */
  folder_id: string | null;
  trashed_at: string | null;
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
  options: {
    limit?: number;
    after?: string;
    folder?: string;
    trash?: boolean;
    /** بحثٌ نصّيّ في اسم الملف وعنوان مستنده — لا بحث دلاليّ. */
    q?: string;
    /** واحدٌ من `LIBRARY_FILTERS` — والخادم يردّ 422 على ما لا يعرفه. */
    kind?: LibraryFilter;
  } = {},
) => {
  const limit = Math.min(options.limit ?? LIBRARY_PAGE, LIBRARY_MAX_FETCH);
  const cursor = options.after ? `&after=${encodeURIComponent(options.after)}` : "";
  // **غيابُ `folder` يعني كل الملفات**، وهو ما تحتاجه قوائم الاختيار في
  // شاشاتٍ أخرى. و`ROOT_FOLDER` تعني جذر المكتبة وحده: لو دلّ الغياب على
  // الجذر لاختفت من تلك القوائم كلُّ ورقةٍ نظّمها الباحث في مجلَّد.
  //
  // **وهو نفسه نطاقُ البحث**: بمعرّف مجلَّدٍ يبحث في هذا الرفّ وحده، وبغيابه
  // في المكتبة كلها. ولا معامل نطاقٍ ثانٍ يقول ما يقوله الأول ثم يفترق عنه.
  const scope = options.folder ? `&folder=${encodeURIComponent(options.folder)}` : "";
  const bin = options.trash ? "&trash=true" : "";
  const term = options.q?.trim() ? `&q=${encodeURIComponent(options.q.trim())}` : "";
  const filter = options.kind ? `&kind=${encodeURIComponent(options.kind)}` : "";
  return apiFetch<LibraryFile[]>(
    `/api/v1/files?limit=${limit}${cursor}${scope}${bin}${term}${filter}`, { locale });
};

/**
 * المرشّحات السبعة — **وهي ما يعرفه الخادم لا ما يزيّن الشاشة**.
 *
 * أربعةٌ نوعُ ملفٍ يُقرأ من `content_type`، وثلاثٌ حالُ معالجةٍ تُشتقّ من
 * تشغيلات الاستخراج الحقيقية — وهي بعينها الحال المعروضة في البطاقة. وأيّ
 * اسمٍ آخر يردّه الخادم بـ422 ولا يتجاهله: زرٌّ يَعِد بتصفيةٍ لا تقع يعرض
 * المكتبة كلها باسمٍ لا يصفها.
 */
export const LIBRARY_FILTERS = [
  "pdf", "docx", "datasets", "references",
  "processed", "awaiting_consent", "not_processed",
] as const;

export type LibraryFilter = (typeof LIBRARY_FILTERS)[number];

/** جذر المكتبة يُطلب باسمه — لا بغياب المعامل. */
export const ROOT_FOLDER = "root";

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
  folder_id: string | null;
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
  // الخادم يردّ المجلَّد الذي نزل فيه الملف؛ فتعرضه الشاشة في موضعه
  // الصحيح فورًا، لا في الجذر ثم ينتقل بعد قراءةٍ ثانية.
  folder_id: stored.folder_id ?? null,
  trashed_at: null,
});

// ══════════════════════════════════════════════════════════════════════
// المجلَّدات | Folders
//
// **المجلَّد تنظيمٌ لا حالُ دليل.** كل ما تفعله هذه الدوال هو تحريك صفوف
// تنظيمية: لا واحدة منها تمسّ ربط ملفٍّ ببحث، ولا حالَ مصدر، ولا اعتماد
// مرشّح. ولذلك «حذف» هنا نقلٌ إلى سلّة، والاستعادة ترجع كل شيء كما كان.
// ══════════════════════════════════════════════════════════════════════

export interface LibraryFolder {
  id: string;
  name: string;
  parent_folder_id: string | null;
  created_at: string;
  trashed_at: string | null;
  /** ما يحتويه مباشرةً — يُقرأ في العبارة نفسها، ولا تُحمَّل ذرّيته. */
  files: number;
  folders: number;
}

export interface Crumb {
  id: string;
  name: string;
}

export interface FolderListing {
  folder_id: string | null;
  breadcrumb: Crumb[];
  folders: LibraryFolder[];
}

export interface FolderOption {
  id: string;
  name: string;
  parent_folder_id: string | null;
  /** المسار كاملًا — فمجلَّدان بالاسم نفسه تحت أبوين لا يُفرَّق بينهما. */
  path: string;
}

const FOLDERS = "/api/v1/files/folders";

export const listFolders = (
  locale: Locale,
  options: { parent?: string | null; trash?: boolean } = {},
) => {
  const parent = options.parent ? `parent=${encodeURIComponent(options.parent)}` : "";
  const bin = options.trash ? "trash=true" : "";
  const query = [parent, bin].filter(Boolean).join("&");
  return apiFetch<FolderListing>(`${FOLDERS}${query ? `?${query}` : ""}`, { locale });
};

export const listAllFolders = (locale: Locale) =>
  apiFetch<FolderOption[]>(`${FOLDERS}/all`, { locale });

export const createFolder = (locale: Locale, name: string, parent: string | null) =>
  apiFetch<LibraryFolder>(FOLDERS, {
    method: "POST", locale,
    body: JSON.stringify({ name, parent_folder_id: parent }),
  });

export const renameFolder = (locale: Locale, id: string, name: string) =>
  apiFetch<LibraryFolder>(`${FOLDERS}/${id}`, {
    method: "PATCH", locale, body: JSON.stringify({ name }),
  });

export const moveFolder = (locale: Locale, id: string, parent: string | null) =>
  apiFetch<LibraryFolder>(`${FOLDERS}/${id}/move`, {
    method: "POST", locale, body: JSON.stringify({ parent_folder_id: parent }),
  });

export const trashFolder = (locale: Locale, id: string) =>
  apiFetch<LibraryFolder>(`${FOLDERS}/${id}/trash`, { method: "POST", locale });

export const restoreFolder = (locale: Locale, id: string) =>
  apiFetch<LibraryFolder>(`${FOLDERS}/${id}/restore`, { method: "POST", locale });

export const moveFile = (locale: Locale, id: string, folder: string | null) =>
  apiFetch<StoredFile>(`/api/v1/files/${id}/move`, {
    method: "POST", locale, body: JSON.stringify({ folder_id: folder }),
  });

/**
 * «حذف» ملفٍّ = نقلُه إلى السلّة.
 *
 * و`confirm` ليست زينة: ملفٌّ يسند بحوثًا يردّ الخادمُ عليه 409 بعددها،
 * فيُقال للباحث ما يترتّب **قبل** أن يقع، ثم يُعاد الطلب بإقراره.
 */
export const trashFile = (locale: Locale, id: string, confirm: boolean) =>
  apiFetch<{ id: string; trashed_at: string | null; project_links: number }>(
    `/api/v1/files/${id}/trash`,
    { method: "POST", locale, body: JSON.stringify({ confirm }) });

export const restoreFile = (locale: Locale, id: string) =>
  apiFetch<StoredFile>(`/api/v1/files/${id}/restore`, { method: "POST", locale });
