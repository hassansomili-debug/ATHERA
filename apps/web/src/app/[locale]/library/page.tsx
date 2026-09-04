"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import {
  createFolder,
  listFolders,
  listLibraryFilePage,
  moveFile,
  moveFolder,
  renameFolder,
  restoreFile,
  restoreFolder,
  trashFile,
  trashFolder,
  LIBRARY_MAX_FETCH,
  LIBRARY_PAGE,
  ROOT_FOLDER,
  type Crumb,
  type LibraryFile,
  type LibraryFolder,
} from "@/lib/library";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { FileUpload } from "@/components/FileUpload";
import { FolderPicker } from "@/components/FolderPicker";
import { ProjectPicker } from "@/components/ProjectPicker";

/**
 * مكتبة الباحث (§14).
 *
 * **وكانت قائمةً واحدة لا تنتهي.** كل ما رفعه الباحث في صفٍّ واحد مرتَّبٍ
 * بتاريخ الرفع؛ فمن رفع ثلاثين كتابًا ومئة ورقة لا يجد كتاب المنهج بينها
 * إلا بأن يقرأ الأسماء واحدًا واحدًا. فصار للمكتبة مجلَّدات.
 *
 * **والمجلَّد تنظيمٌ لا حالُ دليل.** نقلُ ملفٍّ بين مجلَّدين يغيّر موضعه في
 * هذه الشاشة ولا شيء غير ذلك: ربطُه ببحثه باقٍ، وما اعتُمد منه باقٍ،
 * ومفتاح تخزينه لا يتحرّك حرفًا. ولذلك «حذف» هنا نقلٌ إلى سلّة تُستعاد
 * منها الأشياء — لا إتلاف.
 *
 * حالة الوصول تُعرض بجانب كل مصدر لأنها تحدد ما يجوز الاستشهاد به: مصدر
 * بيانات وصفية فقط لا يجوز اقتطاف نص منه (§14.5)، والواجهة تقول ذلك بدل
 * أن تتركه مفاجأة عند المحاولة.
 */
/** أنواع يقرؤها المفكِّك — والزرّ لا يُعرض على ما لا يُقرأ. */
const PARSEABLE = /\.(pdf|docx|txt|md)$/i;


/** حال المعالجة نصًّا — **لا لونًا وحده**، ولا وعدًا بما لم يقع. */
/** الحالات التي ما زال فيها عملٌ يجري — وما عداها مستقرّ يُنتظر عنده الباحث. */
const RUNNING: ReadonlySet<string> = new Set(["parsing", "extracting"]);
/** ومئتا استطلاع (نحو ثماني دقائق) حدُّ الانتظار — لا انتظارٌ مفتوح. */
const MAX_POLLS = 200;
/**
 * ترقّبُ ما بعد الإذن: أربعٌ وعشرون قراءة (نحو دقيقة).
 *
 * والخادم يستأنف في خمسٍ وثلاثين ثانية — قِيس في الإنتاج. فالدقيقة تكفي
 * وتزيد، ولا تُبقي الشاشة تسأل عن حالٍ قد تدوم أيامًا.
 */
const CONSENT_WATCH_POLLS = 24;

const PROCESSING_LABEL: Record<string, string> = {
  not_processed: "library.notProcessed",
  parsing: "library.processing",
  extracting: "library.processing",
  // **انتظارُ الباحث ليس معالجةً جارية.** والقراءة المحلية والاستخراج
  // الحتمي تمّا؛ وما يتوقف الآن هو أن يأذن صاحب المستند. فقولُ «قيد
  // المعالجة» هنا يجعله ينتظر النظام — والنظام ينتظره هو، فلا يتحرك أحد.
  awaiting_consent: "library.awaitingConsent",
  awaiting_review: "library.needsReview",
  completed: "library.processed",
  extract_failed: "library.failedState",
  parse_failed: "library.failedState",
};

interface Source {
  id: string;
  doi: string | null;
  title: string;
  publication_year: number | null;
  journal_name: string | null;
  retraction_status: string;
  access_state: string;
  last_verified_at: string | null;
  registry: string | null;
  can_carry_excerpt: boolean;
}

const RETRACTION_COLOR: Record<string, string> = {
  retracted: "#b3261e",
  expression_of_concern: "#b3261e",
  correction: "var(--athera-gold)",
  unknown: "var(--muted)",
  none: "var(--athera-teal)",
};

/**
 * لوحةٌ واحدة مفتوحة في كل لحظة.
 *
 * **وثلاث لوحاتٍ مفتوحة معًا تجعل الباحث لا يعرف على أيّ شيء يعمل.** فتُحمل
 * اللوحة معرّفَ ما تعمل عليه واسمَه: الاسم يُبنى منه كل عنوانٍ وصفيّ، فلا
 * يبقى زرٌّ يقول «نقل» ولا يقول ماذا يَنقل.
 */
type Panel =
  | { kind: "moveFile"; id: string; name: string }
  | { kind: "moveFolder"; id: string; name: string }
  | { kind: "link"; id: string; name: string }
  | { kind: "rename"; id: string; name: string }
  | { kind: "confirmDelete"; id: string; name: string; projects: number }
  | null;

export default function LibraryPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  // ── أين يقف الباحث الآن ──
  const [folderId, setFolderId] = useState<string | null>(null);
  const [breadcrumb, setBreadcrumb] = useState<Crumb[]>([]);
  const [folders, setFolders] = useState<LibraryFolder[]>([]);
  const [foldersLoad, setFoldersLoad] = useState<"loading" | "ready" | "failed">("loading");
  /** سلّة المهملات لسانٌ ثانٍ لا شاشةٌ أخرى — والاستعادة تقع منه. */
  const [inTrash, setInTrash] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [draftName, setDraftName] = useState("");
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [files, setFiles] = useState<LibraryFile[]>([]);
  /**
   * **قائمةٌ لم تصل ليست مكتبةً خالية.**
   *
   * كانت الشاشة تعرض «لم ترفع ملفًا بعد» ما دامت `files` فارغة — وهي فارغة
   * قبل وصول أول ردّ. فباحثٌ يملك عشرين ملفًا يُقال له إنه لا يملك شيئًا،
   * لا لأن مكتبته خالية بل لأنها لم تُقرأ بعد. وهما حالان مختلفتان تمامًا،
   * وخلطهما كذبٌ يراه المستخدم كذبًا.
   */
  const [filesLoad, setFilesLoad] = useState<"loading" | "ready" | "failed">("loading");
  const [processing, setProcessing] = useState<string | null>(null);
  /**
   * **ما طُلبت معالجته يُراقَب حتى تتحرّك حاله.**
   *
   * كان الاستطلاع يدور ما دام في القائمة ملفٌ في حالٍ **جارية**. وطلبُ
   * المعالجة يُنشئ التشغيلة في مهمّةٍ خلفية، فالقراءة التي تلي الطلب قد
   * تسبقها فتعود بـ`not_processed` — وهي ليست حالًا جارية، فلا يدور
   * الاستطلاع، ولا تُقرأ الحال ثانيةً أبدًا. فتبقى البطاقة تقول «لم
   * تُعالَج بعد» وقد بدأت معالجتها فعلًا، إلى أن يعيد الباحث التحميل
   * بنفسه — وهو لا يعرف أن عليه ذلك. وهذا ما سقطت عليه رحلة القبول: حالٌ
   * ثابتة على `not_processed` ثلاث دقائق كاملة.
   *
   * فالطلب نفسه سببٌ للمراقبة، لا الحالُ المعروضة وحدها.
   */
  const requested = useRef<Set<string>>(new Set());
  const [sources, setSources] = useState<Source[]>([]);
  const [doi, setDoi] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyImport, setBusyImport] = useState(false);

  /**
   * **ما بعد الصفحة الأولى لا يضيع بتحديث.**
   *
   * القائمة صارت مرقَّمة، وكل قراءةٍ تُعيد ما طُلب لا أكثر. فلو استُبدلت
   * القائمة كلها بردّ الصفحة الأولى، لأُلغي ما حمّله الباحث بـ«حمّل المزيد»
   * كلّما دار الاستطلاع. فتُقرأ بقدر ما هو معروض (إلى سقف الخادم)، ويبقى
   * ذيلُ ما بعده كما هو. و`shown` مرآةُ آخر ما عُرض فعلًا — تُكتب بعد
   * التصيير لا داخله.
   */
  const shown = useRef<LibraryFile[]>([]);
  useEffect(() => {
    shown.current = files;
  }, [files]);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  /**
   * **جوابٌ متأخّر لا يمحو جوابًا أحدث منه.**
   *
   * صار للشاشة استطلاعٌ دوري، فصارت قراءتان تجريان معًا: واحدة يطلقها
   * الاستطلاع، وأخرى يطلقها رفعُ ملفٍ للتوّ. ولا ترتيب بين ردَّيهما. فإن
   * وصل ردُّ الاستطلاع — وقد صدر قبل الرفع ولا يعرف بالملف — **بعد** ردّ
   * الرفع، حلّت القائمة الأقدم محلّ الأحدث: يرفع الباحث ملفه، يرى «تم
   * الحفظ»، ثم لا يجد الملف في مكتبته. وإن كان في المكتبة ملفٌ عالق في
   * حالٍ جارية بقي الاستطلاع دائرًا فتكرّر الأمر بلا انقطاع.
   *
   * فلكلّ قراءة رقمُها، ولا يُعرض إلا ردّ أحدثها. والقراءة الأحدث تصدر بعد
   * الرفع دائمًا، فترى ما رُفع.
   *
   * **والانتقال بين المجلَّدات يرفع الرقم أيضًا**: ردُّ مجلَّدٍ غادره الباحث
   * لا يحلّ محلّ محتوى المجلَّد الذي دخله.
   */
  const latest = useRef(0);
  const loadFiles = useCallback(() => {
    const ticket = (latest.current += 1);
    const take = Math.min(LIBRARY_MAX_FETCH, Math.max(LIBRARY_PAGE, shown.current.length));
    const tail = shown.current.slice(take);
    listLibraryFilePage(locale, {
      limit: take,
      // السلّة قائمةٌ مسطّحة: ما حُذف يُعرض كلُّه، لا بموضعه في شجرةٍ قد
      // يكون مجلَّدها نفسه محذوفًا.
      folder: inTrash ? undefined : (folderId ?? ROOT_FOLDER),
      trash: inTrash,
    })
      .then((page) => {
        const next = page.length < take ? page : page.concat(tail);
        if (ticket === latest.current) setFiles(next);
        if (ticket === latest.current) setFilesLoad("ready");
        // ونهايةُ القائمة لا يقرّرها إلا من بلغها: قراءةٌ لا تشمل الذيل
        // لا تعرف ما بعده، فلا تُبطل زرًّا لم تسأل عنه.
        if (ticket === latest.current && tail.length === 0) setHasMore(page.length === take);
      })
      .catch((err) => {
        if (ticket === latest.current) setFilesLoad("failed");
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
      });
  }, [locale, folderId, inTrash]);

  const foldersTicket = useRef(0);
  const loadFolders = useCallback(() => {
    const ticket = (foldersTicket.current += 1);
    listFolders(locale, { parent: inTrash ? null : folderId, trash: inTrash })
      .then((listing) => {
        if (ticket !== foldersTicket.current) return;
        // **ردٌّ ناقصُ الشكل يُعرض فارغًا، ولا يُسقط الشاشة.** فاستثناءٌ في
        // التصيير يترك الصفحة كاملةً بلا أزرارٍ تستجيب، وليس فيها ما يقول
        // ذلك — وهو أسوأ من قائمةٍ فارغة تُقرأ فتُفهم.
        setFolders(listing.folders ?? []);
        setBreadcrumb(listing.breadcrumb ?? []);
        setFoldersLoad("ready");
      })
      .catch((err) => {
        if (ticket !== foldersTicket.current) return;
        setFoldersLoad("failed");
        setActionError(
          err instanceof AtheraApiError ? err.localized(locale) : t("library.foldersFailed"));
      });
  }, [locale, folderId, inTrash]);

  /** قراءةٌ واحدة بعد كل فعلٍ يغيّر التنظيم — المجلَّدات والملفات معًا. */
  const refresh = useCallback(() => {
    shown.current = [];
    setFiles([]);
    setHasMore(false);
    loadFolders();
    loadFiles();
  }, [loadFiles, loadFolders]);

  /**
   * الانتقال إلى مجلَّد — **والحالُ تُصفَّر قبل القراءة لا بعدها**.
   *
   * ولو بقيت ملفات المجلَّد السابق معروضةً حتى يصل الردّ، لرأى الباحث
   * محتوى رفٍّ في رفٍّ آخر ثوانيَ كاملة — وهو أسوأ من انتظارٍ مُعلَن.
   */
  const openFolder = useCallback((next: string | null) => {
    setFolderId(next);
    setPanel(null);
    setNewFolderOpen(false);
    setActionError(null);
    setFilesLoad("loading");
    setFoldersLoad("loading");
    setFiles([]);
    setHasMore(false);
    shown.current = [];
  }, []);

  /**
   * «حمّل المزيد» — والمؤشّر معرّف آخر ملفٍ معروض.
   *
   * ويأخذ رقمه من الترتيب نفسه: لو وصل ردُّ صفحةٍ أولى بعده لكان يمحو ما
   * أُلحق للتوّ، فيضغط الباحث الزرّ ولا يرى شيئًا يزيد.
   */
  const loadMore = useCallback(() => {
    const after = shown.current[shown.current.length - 1]?.id;
    if (!after) return;
    const ticket = (latest.current += 1);
    const base = shown.current;
    setLoadingMore(true);
    listLibraryFilePage(locale, {
      limit: LIBRARY_PAGE,
      after,
      folder: inTrash ? undefined : (folderId ?? ROOT_FOLDER),
      trash: inTrash,
    })
      .then((page) => {
        if (ticket === latest.current) setFiles(base.concat(page));
        if (ticket === latest.current) setHasMore(page.length === LIBRARY_PAGE);
      })
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      .finally(() => setLoadingMore(false));
  }, [locale, folderId, inTrash]);

  /**
   * **الملف الذي رُفع للتوّ يُعرض فورًا.**
   *
   * كان العرض ينتظر قراءةً كاملة للمكتبة بعد الرفع؛ وتلك القراءة هي بعينها
   * ما ثبت بطؤه على حساب فيه ملفات كثيرة. فيرى الباحث «تم الحفظ» ومكتبته
   * خالية من ملفه، ولا شيء يقول له أن ينتظر. وقد سقطت رحلة القبول على ذلك
   * ثلاث مرات: صفر بطاقة ملف بعد رفعٍ نجح.
   *
   * والقيم المعروضة ليست اختلاقًا: الخادم أنشأ صفّ الملف وحده — لا رسالة
   * ولا تشغيلة ولا مرشّح — وهي نفسها ما يردّه المسار لو سُئل عنه الآن.
   * والقراءة تُطلق بعدها فتحلّ الحقيقةُ محلّ التوقّع، ورقمُ الترتيب يُرفع
   * أولًا فلا يمحو الملفَ ردٌّ صدر قبل رفعه.
   */
  const fileUploaded = useCallback((stored: LibraryFile) => {
    latest.current += 1;
    setFiles((previous) => [stored, ...previous.filter((row) => row.id !== stored.id)]);
    setFilesLoad("ready");
    loadFiles();
  }, [loadFiles]);

  /**
   * **المعالجة تجري، والبطاقة واقفة.**
   *
   * الحال تُقرأ مرّة واحدة عند فتح الشاشة ومرّة بعد ضغط «معالجة المستند»،
   * ثم لا تُقرأ أبدًا. فالخادم يمضي: يقرأ، يستخرج، ثم يقف عند حدّ الإذن —
   * والشاشة تبقى تقول «قيد المعالجة» إلى أن يعيد الباحث تحميلها بنفسه.
   * وهو لا يعرف أن عليه ذلك، ولا شيء في الشاشة يقوله له. فيظن أن مستنده
   * عالق، أو ينتظر شيئًا لا يأتي — بينما المنتج ينتظره هو.
   *
   * **والاستطلاع يقف عند حالٍ مستقرّة.** ما دام في المكتبة ملفٌ يُقرأ أو
   * يُستخرَج منه، تُعاد القراءة؛ فإذا لم يبقَ شيءٌ جارٍ توقّفت — فلا قصفٌ
   * للـAPI بعد انتهاء العمل.
   */
  /**
   * **إذنٌ يُمنح في شاشةٍ أخرى يجب أن يُرى في هذه.**
   *
   * `awaiting_consent` حالٌ مستقرّة بحقّ: المنتج ينتظر الباحث، وقد ينتظره
   * أيامًا — فاستطلاعُها دائمًا قصفٌ بلا سبب. لكنّ الباحث يمنح الإذن في
   * صفحة مراجعة الرسالة ثم يعود إلى مكتبته، والخادم يكون قد استأنف فعلًا:
   * قِيس في الإنتاج فمضى `parsing` ← `extracting` ← `awaiting_review` في
   * خمسٍ وثلاثين ثانية. والبطاقة تبقى «بانتظار موافقتك للمتابعة» إلى أن
   * يعيد الباحث التحميل بنفسه — تطلب منه إذنًا **قد منحه**.
   *
   * فالعودة إلى الشاشة سببُ ترقّبٍ **محدود**: ميزانيةٌ تُمنح عند التركيب
   * وعند رجوع الرؤية، وتُستهلك بالقراءة. فإن تحرّكت الحال تولّى الترقّبَ
   * شرطُ «حالٍ جارية»، وإن لم تتحرّك سكتت الشاشة ولم تسأل بلا نهاية.
   */
  const consentWatch = useRef(CONSENT_WATCH_POLLS);
  useEffect(() => {
    const wake = () => {
      if (document.visibilityState !== "visible") return;
      consentWatch.current = CONSENT_WATCH_POLLS;
      polls.current = 0;
      loadFiles();
    };
    document.addEventListener("visibilitychange", wake);
    return () => document.removeEventListener("visibilitychange", wake);
  }, [loadFiles]);

  const polls = useRef(0);
  useEffect(() => {
    const watching = files.some(
      (file) => RUNNING.has(file.processing_status)
        || (requested.current.has(file.id) && file.processing_status === "not_processed")
        || (file.processing_status === "awaiting_consent" && consentWatch.current > 0),
    );
    if (!watching) return;
    // **وحدٌّ للانتظار.** تشغيلةٌ ماتت في منتصفها تترك حالًا «جارية» لا
    // تنتهي أبدًا — ولولا حدٌّ لظلّت الشاشة تسأل عنها ما دامت مفتوحة.
    if (polls.current >= MAX_POLLS) return;
    const timer = window.setTimeout(() => {
      polls.current += 1;
      if (consentWatch.current > 0) consentWatch.current -= 1;
      loadFiles();
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [files, loadFiles]);

  useEffect(() => {
    loadFiles();
    loadFolders();
  }, [loadFiles, loadFolders]);

  useEffect(() => {
    apiFetch<Source[]>("/api/v1/sources", { locale })
      .then(setSources)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      );
  }, [locale]);

  /** رسالةُ الخادم كما هي — فهي التي تقول **لماذا** رُفض الفعل. */
  const say = useCallback((err: unknown) => {
    setActionError(
      err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
  }, [locale]);

  function submitNewFolder(event: React.FormEvent) {
    event.preventDefault();
    const name = draftName.trim();
    if (!name) return;
    setBusy("new-folder");
    setActionError(null);
    createFolder(locale, name, folderId)
      .then(() => {
        setDraftName("");
        setNewFolderOpen(false);
        loadFolders();
      })
      .catch(say)
      .finally(() => setBusy(null));
  }

  function submitRename(event: React.FormEvent) {
    event.preventDefault();
    if (panel?.kind !== "rename") return;
    const name = draftName.trim();
    if (!name) return;
    const { id } = panel;
    setBusy(id);
    setActionError(null);
    renameFolder(locale, id, name)
      .then(() => {
        setPanel(null);
        loadFolders();
      })
      .catch(say)
      .finally(() => setBusy(null));
  }

  function chooseFolderTarget(target: string | null) {
    if (!panel) return;
    const { id, kind } = panel;
    setBusy(id);
    setActionError(null);
    // النوعان مختلفان (`LibraryFolder` و`StoredFile`)، والقراءة بعدهما
    // واحدة — فلا يُستعمل أيّهما، ويُوحَّد العقد صراحةً بدل الاتحاد.
    const action: Promise<unknown> = kind === "moveFolder"
      ? moveFolder(locale, id, target)
      : moveFile(locale, id, target);
    action
      .then(() => {
        setPanel(null);
        refresh();
      })
      .catch(say)
      .finally(() => setBusy(null));
  }

  function deleteFile(file: LibraryFile, confirmed: boolean) {
    setBusy(file.id);
    setActionError(null);
    trashFile(locale, file.id, confirmed)
      .then(() => {
        setPanel(null);
        refresh();
      })
      .catch((err) => {
        // **الملفُ الذي يسند بحوثًا لا يختفي بلا أن يُقال بكم.** الخادم يردّ
        // العدد، فتُعرض جملةٌ فيها رقمٌ حقيقي — لا تحذيرٌ عامّ يُقرأ ولا
        // يُفهم منه شيء.
        if (err instanceof AtheraApiError
            && err.payload.code === "library.file_linked_to_projects") {
          setPanel({
            kind: "confirmDelete", id: file.id, name: file.original_filename,
            projects: Number(err.payload.context?.projects ?? 0),
          });
          return;
        }
        say(err);
      })
      .finally(() => setBusy(null));
  }

  function deleteFolder(folder: LibraryFolder) {
    setBusy(folder.id);
    setActionError(null);
    trashFolder(locale, folder.id)
      .then(() => {
        setPanel(null);
        refresh();
      })
      .catch(say)
      .finally(() => setBusy(null));
  }

  function undelete(kind: "file" | "folder", id: string) {
    setBusy(id);
    setActionError(null);
    const back: Promise<unknown> =
      kind === "file" ? restoreFile(locale, id) : restoreFolder(locale, id);
    back
      .then(refresh)
      .catch(say)
      .finally(() => setBusy(null));
  }

  function linkToProject(projectId: string) {
    if (panel?.kind !== "link") return;
    const { id } = panel;
    setBusy(id);
    setActionError(null);
    apiFetch(`/api/v1/workspace/projects/${projectId}/files`, {
      method: "POST", locale, body: JSON.stringify({ asset_id: id }),
    })
      .then(() => setPanel(null))
      .catch(say)
      .finally(() => setBusy(null));
  }

  function importDoi(event: React.FormEvent) {
    event.preventDefault();
    setBusyImport(true);
    setError(null);
    apiFetch<Source>("/api/v1/sources/import", {
      method: "POST", locale, body: JSON.stringify({ doi }),
    })
      .then((source) => {
        setSources((previous) => [source, ...previous]);
        setDoi("");
      })
      // §14.5 / TC-02 — الرسالة تشرح أنه لن يُنشأ بديل، لا مجرد «فشل».
      .catch((err) => setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("library.notFound")))
      .finally(() => setBusyImport(false));
  }

  const here = breadcrumb.length ? breadcrumb[breadcrumb.length - 1].name : t("library.rootCrumb");

  return (
    <>
      <h1>{t("library.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("library.subtitle")}</p>

      {/* ── لسانان: المكتبة وسلّة المهملات ── */}
      <div style={{ display: "flex", gap: 8, marginBlock: "12px 8px" }}>
        <button
          type="button"
          disabled={!inTrash}
          aria-label={`${t("library.libraryTab")}: ${t("library.rootCrumb")}`}
          onClick={() => {
            setInTrash(false);
            openFolder(null);
          }}
        >
          {t("library.libraryTab")}
        </button>
        <button
          type="button"
          disabled={inTrash}
          aria-label={`${t("library.trashTab")}: ${t("library.rootCrumb")}`}
          onClick={() => {
            setInTrash(true);
            openFolder(null);
          }}
        >
          {t("library.trashTab")}
        </button>
      </div>

      {inTrash ? (
        <p className="note" data-testid="library-trash-note">{t("library.trashNote")}</p>
      ) : (
        <>
          {/* ── فتات الطريق: مكتبتي > كتب المنهج > المنهج الكمي ── */}
          <nav
            aria-label={t("library.breadcrumbLabel")}
            data-testid="library-breadcrumb"
            style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center",
                     marginBlockEnd: 12 }}
          >
            {folderId === null ? (
              <strong>{t("library.rootCrumb")}</strong>
            ) : (
              <button
                type="button"
                aria-label={`${t("library.openFolder")}: ${t("library.rootCrumb")}`}
                onClick={() => openFolder(null)}
              >
                {t("library.rootCrumb")}
              </button>
            )}
            {breadcrumb.map((crumb, index) => (
              <span key={crumb.id} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span aria-hidden="true">›</span>
                {index === breadcrumb.length - 1 ? (
                  <strong>{crumb.name}</strong>
                ) : (
                  <button
                    type="button"
                    aria-label={`${t("library.openFolder")}: ${crumb.name}`}
                    onClick={() => openFolder(crumb.id)}
                  >
                    {crumb.name}
                  </button>
                )}
              </span>
            ))}
          </nav>

          {/* ── الفعلان الرئيسان ── */}
          <div style={{ display: "flex", gap: 8, marginBlockEnd: 12 }}>
            <button
              type="button"
              data-testid="library-new-folder"
              aria-label={`${t("library.newFolder")}: ${here}`}
              onClick={() => {
                setNewFolderOpen((open) => !open);
                setDraftName("");
                setActionError(null);
              }}
            >
              {t("library.newFolder")}
            </button>
          </div>

          {newFolderOpen ? (
            <form className="form" onSubmit={submitNewFolder} style={{ maxInlineSize: 420 }}>
              <label>
                {t("library.folderName")}
                <input
                  value={draftName}
                  aria-label={`${t("library.folderName")}: ${here}`}
                  onChange={(event) => setDraftName(event.target.value)}
                  required
                />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="submit"
                  disabled={busy === "new-folder" || !draftName.trim()}
                  aria-label={`${t("library.createFolder")}: ${here}`}
                >
                  {busy === "new-folder" ? t("library.creatingFolder") : t("library.createFolder")}
                </button>
                <button
                  type="button"
                  aria-label={`${t("library.cancelFolder")}: ${here}`}
                  onClick={() => setNewFolderOpen(false)}
                >
                  {t("library.cancelFolder")}
                </button>
              </div>
            </form>
          ) : null}

          <div style={{ marginBlock: "18px 24px" }}>
            {/* **الفعلُ الثاني بعنوانه، لا بزرٍّ ثانٍ يفتح الأول.** مدخل
                الملف داخل بطاقة الرفع وهو الفعل الحقيقي؛ وزرٌّ فوقه يضغطه
                نيابةً عنه ضجيجٌ يقول ما يقوله ما تحته. فيُقال الموضع الذي
                ينزل فيه الملف — وهو ما لا تعرفه بطاقة الرفع. */}
            <p className="metric-label">
              {t("library.uploadFile")} · {t("library.uploadInto")} {here}
            </p>
            <FileUpload
              locale={locale}
              messages={getMessages(locale)}
              folderId={folderId}
              onUploaded={fileUploaded}
            />
          </div>
        </>
      )}

      {actionError ? (
        <p className="error" role="alert" data-testid="library-action-error">{actionError}</p>
      ) : null}

      {/* ── المجلَّدات في هذا الموضع ── */}
      <section>
        <h2>{inTrash ? t("library.trashTab") : t("library.libraryTab")}</h2>
        {foldersLoad === "loading" ? (
          <p data-testid="library-folders-loading" role="status" aria-live="polite">
            {t("library.loadingFolders")}
          </p>
        ) : foldersLoad === "failed" ? (
          <p className="error" role="alert" data-testid="library-folders-error">
            {t("library.foldersFailed")}
          </p>
        ) : folders.length === 0 ? (
          <p data-testid="library-no-folders">{t("library.noFolders")}</p>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {folders.map((folder) => (
              <div className="card" data-testid="library-folder-row" key={folder.id}>
                {panel?.kind === "rename" && panel.id === folder.id ? (
                  <form className="form" onSubmit={submitRename} style={{ maxInlineSize: 420 }}>
                    <label>
                      {t("library.folderName")}
                      <input
                        value={draftName}
                        aria-label={`${t("library.renameFolder")}: ${folder.name}`}
                        onChange={(event) => setDraftName(event.target.value)}
                        required
                      />
                    </label>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        type="submit"
                        disabled={busy === folder.id || !draftName.trim()}
                        aria-label={`${t("library.renameSave")}: ${folder.name}`}
                      >
                        {t("library.renameSave")}
                      </button>
                      <button
                        type="button"
                        aria-label={`${t("library.renameCancel")}: ${folder.name}`}
                        onClick={() => setPanel(null)}
                      >
                        {t("library.renameCancel")}
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <strong>📁 {folder.name}</strong>
                    <div className="metric-label">
                      {t("library.folderContents")} {folder.files} {t("library.filesCount")} ·{" "}
                      {folder.folders} {t("library.foldersCount")}
                    </div>
                  </>
                )}

                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBlockStart: 8 }}>
                  {inTrash ? (
                    <button
                      type="button"
                      disabled={busy === folder.id}
                      aria-label={`${t("library.restoreFolder")}: ${folder.name}`}
                      onClick={() => undelete("folder", folder.id)}
                    >
                      {t("library.restoreFolder")}
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        aria-label={`${t("library.openFolder")}: ${folder.name}`}
                        onClick={() => openFolder(folder.id)}
                      >
                        {t("library.openFolder")}
                      </button>
                      <button
                        type="button"
                        disabled={busy === folder.id}
                        aria-label={`${t("library.renameFolder")}: ${folder.name}`}
                        onClick={() => {
                          setDraftName(folder.name);
                          setActionError(null);
                          setPanel({ kind: "rename", id: folder.id, name: folder.name });
                        }}
                      >
                        {t("library.renameFolder")}
                      </button>
                      <button
                        type="button"
                        disabled={busy === folder.id}
                        aria-label={`${t("library.moveFolder")}: ${folder.name}`}
                        onClick={() => {
                          setActionError(null);
                          setPanel({ kind: "moveFolder", id: folder.id, name: folder.name });
                        }}
                      >
                        {t("library.moveFolder")}
                      </button>
                      <button
                        type="button"
                        disabled={busy === folder.id}
                        aria-label={`${t("library.deleteFolder")}: ${folder.name}`}
                        onClick={() => deleteFolder(folder)}
                      >
                        {t("library.deleteFolder")}
                      </button>
                    </>
                  )}
                </div>

                {panel?.kind === "moveFolder" && panel.id === folder.id ? (
                  <FolderPicker
                    locale={locale}
                    messages={getMessages(locale)}
                    targetName={folder.name}
                    excludeId={folder.id}
                    currentFolderId={folder.parent_folder_id}
                    busy={busy === folder.id}
                    onChoose={chooseFolderTarget}
                    onCancel={() => setPanel(null)}
                  />
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── ملفاتي: ما يملكه الباحث فعلًا ── */}
      <section>
        <h2>{t("library.myFiles")}</h2>
        <p style={{ color: "var(--muted)" }}>{t("library.filesNote")}</p>
        {/*
          الحالات الثلاث تُقال منفصلة: «تُقرأ الآن» غير «لا ملفات» غير
          «تعذّرت القراءة». وجمعُها في نصٍّ واحد يجعل بطء الخادم يبدو
          مكتبةً خالية — وهو أسوأ ما تقوله شاشةٌ لمن يملك ملفاته.
        */}
        {filesLoad === "loading" ? (
          <p data-testid="library-files-loading" role="status" aria-live="polite">
            {t("library.loadingFiles")}
          </p>
        ) : filesLoad === "failed" ? (
          <p className="error" role="alert" data-testid="library-files-error">
            {t("library.filesFailed")}
          </p>
        ) : files.length === 0 ? (
          <p>
            {inTrash
              ? t("library.trashEmpty")
              : folderId === null ? t("library.noFiles") : t("library.emptyFolder")}
          </p>
        ) : (
          <div className="cards">
            {files.map((file) => (
              // بطاقةُ ملفٍ تُميَّز عن بطاقةِ مرجع: `article.card` يطابق
              // الاثنتين، فعدُّها لا يفرّق بين مكتبةٍ بلا ملفات ومكتبةٍ لم
              // تُقرأ — والسمة لا تحمل اسمًا ولا سرًّا.
              <article className="card" data-testid="library-file-card" key={file.id}>
                <h3>{file.original_filename}</h3>
                <div className="metric-label">
                  {file.content_type} · {Math.max(1, Math.round(file.size_bytes / 1024))} KB ·{" "}
                  {new Date(file.created_at).toLocaleDateString(locale)}
                </div>
                {/* الحالة نصًّا صريحًا — ولا يُقال «حُلِّل» لملفٍ لم يُقرأ. */}
                {/*
                  الحال القانونية بجانب نصّها المترجَم.

                  والنصّ للإنسان، والسمة للآلة: فحصٌ يطابق نصًّا مترجَمًا
                  يسقط بأول تحسينٍ للصياغة، أو يقرأ نصَّ شاشةٍ أخرى ويظنّه
                  هذه. وليس فيها سرٌّ ولا معرّف — الحال نفسها لا غير.
                */}
                <div className="metric-label" data-processing-state={file.processing_status}>
                  {t(PROCESSING_LABEL[file.processing_status] ?? "library.notProcessed")}
                  {file.candidates > 0
                    ? ` · ${file.candidates} ${t("library.candidatesCount")} · ${file.reviewed} ${t("library.reviewedCount")}`
                    : ""}
                </div>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBlockStart: 8 }}>
                  {inTrash ? (
                    <button
                      type="button"
                      disabled={busy === file.id}
                      aria-label={`${t("library.restoreFile")}: ${file.original_filename}`}
                      onClick={() => undelete("file", file.id)}
                    >
                      {t("library.restoreFile")}
                    </button>
                  ) : (
                    <>
                      {/* المعالجة تُعرض لما يمكن قراءته وحده — ووعدٌ لا يُنجَز
                          أسوأ من غياب الزرّ. */}
                      {file.processing_status === "not_processed" ? (
                        PARSEABLE.test(file.original_filename) ? (
                          <button
                            type="button"
                            disabled={processing === file.id}
                            aria-label={`${t("library.processDoc")}: ${file.original_filename}`}
                            onClick={() => {
                              setProcessing(file.id);
                              requested.current.add(file.id);
                              polls.current = 0;
                              setError(null);
                              void apiFetch(`/api/v1/theses/process-file/${file.id}`, {
                                method: "POST", locale,
                              })
                                .then(() => loadFiles())
                                .catch((err) => setError(
                                  err instanceof AtheraApiError
                                    ? err.localized(locale) : t("common.loadFailed")))
                                .finally(() => setProcessing(null));
                            }}
                          >
                            {processing === file.id
                              ? t("library.processing2") : t("library.processDoc")}
                          </button>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>{t("library.cannotProcess")}</span>
                        )
                      ) : null}
                      {/* **إلى رسالته هو، لا إلى قائمةٍ يبحث فيها.** المعرّف
                          معروفٌ هنا، فالرابط يقصده — ولا يُطلب من الباحث أن
                          يتعرّف على مستنده بين بطاقاتٍ متشابهة. */}
                      {file.thesis_id ? (
                        <a
                          href={`/${locale}/theses/${file.thesis_id}/review`}
                          aria-label={`${t("library.openReview")}: ${file.original_filename}`}
                        >
                          {t("library.openReview")}
                        </a>
                      ) : null}
                      {/* **المعرفة المعتمَدة كان لا يُسأل عنها.** الباحث يعالج
                          مستنده ويعتمد منه معلومات، ثم يفتح بُبريفا AI فلا يجد
                          طريقًا إليه: المرفق يقبل رفعًا جديدًا وحده، والنسخة
                          الجديدة غير مقروءة — فما اعتُمد لا يُبلَغ إليه أبدًا.
                          فمن هنا يُسأل عن هذا المستند بعينه. */}
                      {file.processing_status === "awaiting_review"
                        || file.processing_status === "completed" ? (
                        <a
                          href={`/${locale}/ai?file=${file.id}`}
                          aria-label={`${t("library.askAi")}: ${file.original_filename}`}
                        >
                          {t("library.askAi")}
                        </a>
                      ) : null}
                      <button
                        type="button"
                        disabled={busy === file.id}
                        aria-label={`${t("library.moveFile")}: ${file.original_filename}`}
                        onClick={() => {
                          setActionError(null);
                          setPanel({ kind: "moveFile", id: file.id,
                                     name: file.original_filename });
                        }}
                      >
                        {t("library.moveFile")}
                      </button>
                      <button
                        type="button"
                        disabled={busy === file.id}
                        aria-label={`${t("library.linkToProject")}: ${file.original_filename}`}
                        onClick={() => {
                          setActionError(null);
                          setPanel({ kind: "link", id: file.id,
                                     name: file.original_filename });
                        }}
                      >
                        {t("library.linkToProject")}
                      </button>
                      <button
                        type="button"
                        aria-label={`${t("library.downloadFile")}: ${file.original_filename}`}
                        onClick={() => {
                          void apiFetch<{ download_url: string }>(
                            `/api/v1/files/${file.id}/download`, { locale })
                            .then((r) => window.open(r.download_url, "_blank", "noopener"))
                            .catch((err) => setError(
                              err instanceof AtheraApiError
                                ? err.localized(locale) : t("common.loadFailed")));
                        }}
                      >
                        {t("library.downloadFile")}
                      </button>
                      <button
                        type="button"
                        disabled={busy === file.id}
                        aria-label={`${t("library.deleteFile")}: ${file.original_filename}`}
                        onClick={() => deleteFile(file, false)}
                      >
                        {t("library.deleteFile")}
                      </button>
                    </>
                  )}
                </div>

                {panel?.kind === "moveFile" && panel.id === file.id ? (
                  <FolderPicker
                    locale={locale}
                    messages={getMessages(locale)}
                    targetName={file.original_filename}
                    currentFolderId={file.folder_id}
                    busy={busy === file.id}
                    onChoose={chooseFolderTarget}
                    onCancel={() => setPanel(null)}
                  />
                ) : null}

                {panel?.kind === "link" && panel.id === file.id ? (
                  <ProjectPicker
                    locale={locale}
                    messages={getMessages(locale)}
                    fileName={file.original_filename}
                    busy={busy === file.id}
                    onChoose={linkToProject}
                    onCancel={() => setPanel(null)}
                  />
                ) : null}

                {panel?.kind === "confirmDelete" && panel.id === file.id ? (
                  <div data-testid="library-delete-confirm" role="alert"
                       className="card" style={{ marginBlockStart: 8, padding: 12 }}>
                    <strong>⚠ {t("library.deleteLinkedTitle")}</strong>
                    <p style={{ marginBlockStart: 4 }}>
                      {t("library.deleteLinkedBody")} {panel.projects}
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        type="button"
                        disabled={busy === file.id}
                        aria-label={`${t("library.deleteLinkedConfirm")}: ${file.original_filename}`}
                        onClick={() => deleteFile(file, true)}
                      >
                        {t("library.deleteLinkedConfirm")}
                      </button>
                      <button
                        type="button"
                        aria-label={`${t("library.deleteLinkedCancel")}: ${file.original_filename}`}
                        onClick={() => setPanel(null)}
                      >
                        {t("library.deleteLinkedCancel")}
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )}
        {/* ما عُرض لا يُستبدل بما يُضاف: الزرّ يُلحق ولا يعيد البناء. */}
        {filesLoad === "ready" && hasMore ? (
          <button
            type="button"
            data-testid="library-load-more"
            disabled={loadingMore}
            aria-label={`${t("library.loadMore")}: ${here}`}
            onClick={loadMore}
            style={{ marginBlockStart: 12 }}
          >
            {loadingMore ? t("library.loadingMore") : t("library.loadMore")}
          </button>
        ) : null}
      </section>

      <h2>{t("library.sourcesTab")}</h2>

      <form className="form" onSubmit={importDoi} style={{ maxInlineSize: 480 }}>
        <label>
          {t("library.importByDoi")}
          <input
            value={doi}
            onChange={(e) => setDoi(e.target.value)}
            placeholder={t("library.doiPlaceholder")}
            dir="ltr"
            required
          />
        </label>
        {error ? (
          <p className="error" role="alert" data-testid="library-source-error">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={busyImport}>
          {busyImport ? t("app.loading") : t("library.import")}
        </button>
      </form>

      {sources.length === 0 ? (
        <p style={{ color: "var(--muted)", marginBlockStart: "var(--space)" }}>{t("library.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8, marginBlockStart: "var(--space)" }}>
        {sources.map((source) => (
          <article className="card" key={source.id}>
            <strong>{source.title}</strong>
            <div className="metric-label" style={{ marginBlockStart: 4 }} dir="ltr">
              {source.doi ?? "—"} · {source.publication_year ?? "—"} · {source.journal_name ?? "—"}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBlockStart: 8, fontSize: 13 }}>
              <span>
                {t("library.accessState")}: {t(`library.access.${source.access_state}`)}
              </span>
              <span style={{ color: RETRACTION_COLOR[source.retraction_status] }}>
                {t("library.retraction")}: {t(`library.retractionState.${source.retraction_status}`)}
              </span>
              <span style={{ color: source.can_carry_excerpt ? "var(--athera-teal)" : "var(--muted)" }}>
                {source.can_carry_excerpt ? t("library.canQuote") : t("library.cannotQuote")}
              </span>
            </div>
            {source.last_verified_at ? (
              <div className="metric-label">
                {t("library.lastVerified")}: {new Date(source.last_verified_at).toLocaleString(locale)}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}
