"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AtheraApiError } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { libraryFileFromUpload, type LibraryFile, type StoredFile } from "@/lib/library";
import { usePosture } from "@/lib/posture";
import { uploadWithProgress } from "@/lib/upload";

/**
 * رفع ملفات البحث.
 *
 * **الحالات المعروضة صادقة حرفيًا:** «في الانتظار» ثم «جارٍ الرفع» ثم «تم
 * الحفظ». ولا «حُلِّل» ولا «فُهم» — التفكيك لم يقع، والادعاء به أسوأ من
 * غيابه. و«تم الحفظ» لا تُعرض إلا بعد ردّ الخادم ٢٠١، وهو لا يُصدره إلا بعد
 * أن يستقرّ الكائن في التخزين ويُكتب صفّه — فالكلمة مسنودة لا متفائلة.
 *
 * والرفع مستقل عن حالة النموذج: التخزين قد يكون مُهيّأ بينما استدعاء
 * النموذج مطفأ، فالبوابتان تُقرآن من `/settings/posture` منفصلتين.
 *
 * ولا اسم مزوّد تخزين يظهر هنا: الباحث يرفع «ملف بحث»، لا كائنًا في دلو.
 *
 * **والانتظار يُقاس بالأرقام لا بنقاطٍ ثلاث.** كتابٌ بمئة ميجابايت يستغرق
 * دقائق، وزرٌّ مكتوب عليه «جارٍ الرفع…» لا يتحرّك يقول للباحث إن الشاشة
 * ماتت — فيغلقها وقد كان رفعه يمضي. فتُعرض البايتات المرسلة من إجماليها
 * بنسبةٍ حقيقية من `upload.onprogress`، لا بشريطٍ يتحرّك من تلقائه.
 *
 * ## الرفع المتعدّد — مكتبةً لا تحليلًا
 *
 * **و`multiple` اختيارٌ صريح، افتراضُه الإطفاء.** المكتبة تجمع: الباحث
 * يعود من قاعدة بياناتٍ بعشرين ورقة، واختيارُها واحدةً واحدةً عشرون فتحًا
 * لنافذة الملفات. وشاشةُ البيانات والتحليل تتعامل مع مجموعةٍ واحدة في
 * المرّة، فتبقى كما هي — ولو صار المتعدّد افتراضًا لتغيّرت شاشةٌ لم يطلب
 * أحدٌ تغييرها.
 *
 * **ومحرّكُ الرفع واحد، والعرضُ عرضان.** الطابور هو المحرّك في الحالين
 * (الملف الواحد طابورٌ من واحد)، فلا نسختان من منطق الرفع تفترقان بأول
 * تعديل. والعرضُ القديم يبقى حرفيًّا لمن لا يطلب المتعدّد.
 *
 * **ولا عشرون طلبًا في وقتٍ واحد.** متصفّحٌ يفتح عشرين اتصالًا يخنق نفسه
 * أولًا (حدُّ الاتصالات لكلّ مضيف)، ثم يخنق الخادمَ والتخزين بعشرين تدفّقًا
 * متزامنًا. فثلاثةٌ تجري والبقيةُ تنتظر، ويبدأ التالي حين ينتهي واحد.
 */
type ItemState = "queued" | "uploading" | "stored" | "failed";

const ACCEPT = ".pdf,.docx,.doc,.txt,.ris,.bib,.csv,.xls,.xlsx,.sav,.zsav";

/**
 * أقصى ما يُختار في المرّة الواحدة.
 *
 * **والزائدُ يُرفض بصراحة ولا يُقتطع صامتًا.** لو أخذنا أول عشرين من ثلاثين
 * لظنّ الباحث أن الثلاثين رُفعت، ولا شيء في الشاشة يقول إن عشرة سقطت —
 * فيكتشف النقص بعد أسابيع، أو لا يكتشفه.
 */
const MAX_FILES = 20;

/** ما يجري متزامنًا من الطابور. */
const MAX_PARALLEL = 3;

/** ميجابايت بخانةٍ عشرية واحدة — والباحث يقرأ الحجم لا البايتات. */
const mb = (bytes: number) => (bytes / (1024 * 1024)).toFixed(1);

/**
 * يعبّئ متغيّرات النصّ المترجَم.
 *
 * والنصوص كلُّها في كتالوجَي الرسائل — وهذا إحلالُ أرقامٍ فيها، لا كتابةُ
 * نصٍّ في المكوّن. و`translator` لا يعبّئ، فيُعبّأ هنا بلا تغيير المشترك.
 */
const fill = (template: string, values: Record<string, string | number>) =>
  Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), template);

interface QueueItem {
  /** مفتاحٌ محليّ ثابت — والاسم وحده لا يكفي: ملفّان بالاسم نفسه جائزان. */
  id: string;
  /** الملف نفسه — يبقى محفوظًا لتصحّ إعادةُ المحاولة عليه وحده. */
  file: File;
  /**
   * المجلَّد وقتَ الاختيار — **لا وقتَ الرفع**.
   *
   * فالدفعةُ تنزل حيث اختارها صاحبُها. ولو قُرئ المجلَّد عند إرسال كلِّ
   * ملفٍ لانقسمت الدفعةُ على مجلَّدين متى تنقّل الباحثُ وهي تجري: ثلاثةٌ
   * في «أوراق المنهج» وسبعةَ عشرَ في الذي انتقل إليه — ولا شيء يقول له
   * ذلك. والتثبيتُ عند الاختيار يجعل النيّةَ واحدةً من أوّلها.
   */
  folderId: string | null;
  state: ItemState;
  loaded: number;
  total: number;
  stored?: StoredFile;
  error?: string;
}

let sequence = 0;
const nextId = () => `u${(sequence += 1)}`;

export function FileUpload({
  locale, messages, onUploaded, folderId = null, multiple = false, onBatchSettled,
}: {
  locale: Locale;
  messages: Messages;
  /** الملف كما أنشأه الخادم — لتعرضه الشاشة فورًا بلا انتظار قراءةٍ ثانية. */
  onUploaded?: (file: LibraryFile) => void;
  /**
   * المجلَّد الذي يقف فيه الباحث — و`null` جذر المكتبة.
   *
   * **والملف ينزل حيث يقف صاحبه.** والبديل — رفعٌ إلى الجذر ثم نقلٌ ثانٍ —
   * يترك نافذةً يظهر فيها الملف في غير موضعه، ويكلّف طلبًا زائدًا على كل
   * رفع، ويسقط صامتًا لو فشل النقل بعد نجاح الرفع. **وكلُّ ملفات الدفعة
   * تحمل هذا المعرّف نفسه**، فالعشرون تنزل حيث يقف صاحبها لا في الجذر.
   */
  folderId?: string | null;
  /**
   * اختيارُ أكثر من ملفٍ في فتحةٍ واحدة — **للمكتبة وحدها**.
   *
   * وافتراضُه `false` كي لا يتغيّر مستدعٍ قائم بلا أن يطلب التغيير.
   */
  multiple?: boolean;
  /**
   * تُنادى مرّةً واحدة حين يفرغ الطابور — لا مرّةً لكلّ ملف.
   *
   * **وقراءةٌ واحدة في آخر الدفعة لا عشرون.** الإدراجُ المتفائل عبر
   * `onUploaded` يُظهر كلَّ ملفٍ فور حفظه، وهذه لمصالحة القائمة مع الخادم
   * بعد أن يهدأ كلُّ شيء: عشرون قراءةً كاملة للمكتبة تُثقل الشاشة والخادم
   * بلا أن تُظهر شيئًا لم يُظهره الإدراج.
   */
  onBatchSettled?: () => void;
}) {
  const t = translator(messages);
  const { items: posture, loading } = usePosture(locale);
  const storageReady = posture.find((i) => i.key === "storage")?.value !== "none";
  const inputRef = useRef<HTMLInputElement>(null);

  const [items, setItems] = useState<QueueItem[]>([]);
  const [tooMany, setTooMany] = useState<number | null>(null);

  /** ما بُدئ فعلًا — فلا يُبدأ ملفٌّ مرّتين حين تتغيّر الحالة. */
  const startedRef = useRef<Set<string>>(new Set());
  /**
   * ما هو في الطيران الآن — **عدّادٌ لا حالةُ عرض**.
   *
   * واشتقاقُ العدد من `items` كان يكفي في الغالب ويسقط في الحدّ: بين
   * إطلاق الرفع وحفظ حالته «جارٍ» تمرّ لحظةٌ يكون فيها العدد المشتقّ
   * أقلَّ من الواقع، فتُفتح طاقةٌ ليست موجودة. والمرجعُ يزيد قبل الإطلاق
   * وينقص في `finally`، فلا يعتمد الحدُّ على توقيت إعادة العرض إطلاقًا.
   */
  const inflightRef = useRef(0);
  /** هل نُوديت مصالحةُ القائمة لهذه الدفعة؟ */
  const settledRef = useRef(true);

  const patch = useCallback((id: string, change: Partial<QueueItem>) => {
    setItems((previous) =>
      previous.map((item) => (item.id === id ? { ...item, ...change } : item)));
  }, []);

  const run = useCallback(async (item: QueueItem) => {
    inflightRef.current += 1;
    patch(item.id, {
      state: "uploading", loaded: 0, total: item.file.size, error: undefined,
    });

    const body = new FormData();
    body.append("upload", item.file);
    if (item.folderId) body.append("folder_id", item.folderId);

    try {
      // **عبر أداة الرفع لا `fetch` خامًّا.** هي تحفظ حارس الإعداد المفقود
      // وتوحيد رسائل الخطأ وتجديد الجلسة الواحد في الطيران، وتزيد عليها
      // نسبة التقدّم التي لا يعطيها `fetch` أصلًا.
      const stored = await uploadWithProgress<StoredFile>(
        "/api/v1/files/upload", body, {
          locale,
          // **هُويّةُ العنصرِ هي هُويّةُ النيّة** (Stage 6): ملفّان مختلفان
          // قد يتّفقان في الاسم والحجم والنوع، فلا يُميَّزان بها. و`retry`
          // يُبقي المعرّفَ نفسَه — فإعادةُ محاولةِ ملفٍّ تحمل مفتاحَه هو،
          // ونجاحُ ملفٍّ لا يُحرّر مفتاحَ غيره.
          intentId: item.id,
          onProgress: (progress) => patch(item.id, {
            loaded: progress.loaded, total: progress.total || item.file.size,
          }),
        });
      patch(item.id, { state: "stored", stored, loaded: item.file.size });
      onUploaded?.(libraryFileFromUpload(stored));
    } catch (err) {
      // **وسقوطُ ملفٍ لا يُسقط الدفعة.** الخطأ يبقى على صفّه، والطابور يمضي
      // إلى ما بعده — فمن رفع عشرين ورقةً وسقطت واحدة يحصل على تسع عشرة.
      patch(item.id, {
        state: "failed",
        error: err instanceof AtheraApiError ? err.localized(locale) : t("upload.failed"),
      });
    } finally {
      inflightRef.current -= 1;
    }
  }, [locale, onUploaded, patch, t]);

  // **قائدُ الطابور.** يُوقظ عند كل تغيّر حالة، فيملأ الطاقة الفارغة بما
  // ينتظر: الطاقةُ من عدّاد الطيران، والمُنتظِرون من الحالة، و`startedRef`
  // يمنع إطلاق الملف مرّتين. وثلاثتها معًا تجعل الحدَّ صحيحًا بلا اعتمادٍ
  // على توقيت إعادة العرض.
  useEffect(() => {
    let capacity = MAX_PARALLEL - inflightRef.current;
    if (capacity <= 0) return;
    for (const item of items) {
      if (capacity <= 0) break;
      if (item.state !== "queued" || startedRef.current.has(item.id)) continue;
      startedRef.current.add(item.id);
      capacity -= 1;
      void run(item);
    }
  }, [items, run]);

  // مصالحةُ القائمة مرّةً واحدة حين يهدأ كلُّ شيء.
  useEffect(() => {
    if (!items.length) return;
    const pending = items.some((i) => i.state === "queued" || i.state === "uploading");
    if (pending) {
      settledRef.current = false;
      return;
    }
    if (settledRef.current) return;
    settledRef.current = true;
    onBatchSettled?.();
  }, [items, onBatchSettled]);

  function accept(chosen: File[]) {
    if (!chosen.length) return;
    if (chosen.length > MAX_FILES) {
      // يُرفض الاختيار كلُّه ولا يُقتطع: القبولُ الجزئي يكذب على صاحبه.
      setTooMany(chosen.length);
      return;
    }
    setTooMany(null);
    startedRef.current = new Set();
    inflightRef.current = 0;
    settledRef.current = false;
    setItems(chosen.map((file) => ({
      id: nextId(), file, folderId, state: "queued" as ItemState,
      loaded: 0, total: file.size,
    })));
  }

  function retry(id: string) {
    // إعادةُ المحاولة لهذا الملف وحده — ولا تكرارَ تلقائيًّا بلا حدّ.
    startedRef.current.delete(id);
    settledRef.current = false;
    patch(id, { state: "queued", loaded: 0, error: undefined });
  }

  const counts = useMemo(() => ({
    queued: items.filter((i) => i.state === "queued").length,
    uploading: items.filter((i) => i.state === "uploading").length,
    stored: items.filter((i) => i.state === "stored").length,
    failed: items.filter((i) => i.state === "failed").length,
    total: items.length,
  }), [items]);

  const busy = counts.queued > 0 || counts.uploading > 0;
  const disabled = loading || !storageReady || busy;
  const percentOf = (item: QueueItem) =>
    item.total > 0 ? Math.min(100, Math.round((item.loaded / item.total) * 100)) : 0;

  const single = items[0];

  return (
    <section className="card" style={{ maxInlineSize: "62ch" }}>
      <h2 style={{ marginBlockStart: 0, fontSize: "1.02rem" }}>{t("upload.title")}</h2>
      <p style={{ color: "var(--muted)", fontSize: 13.5, marginBlockStart: 4 }}>
        {t("upload.hint")}
      </p>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple={multiple}
        className="sr-only"
        onChange={(e) => {
          accept(Array.from(e.target.files ?? []));
          // يُفرَّغ المدخل ليصحّ اختيارُ الملف نفسه مرّةً أخرى.
          e.target.value = "";
        }}
      />

      <div className="ai-tools" style={{ borderBlockStart: "none", paddingBlockStart: 4 }}>
        <button
          type="button"
          className="ai-tool"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          📎 {busy
            ? t("upload.uploading")
            : multiple ? t("upload.pickMany") : t("upload.pick")}
        </button>

        {/* العرضُ القديم يبقى حرفيًّا للملف الواحد. */}
        {!multiple && single?.state === "stored" && single.stored ? (
          <span className="chip chip-ok">
            ✓ {t("upload.stored")} — {single.stored.original_filename}
            {" "}· {Math.round(single.stored.size_bytes / 1024)} KB
          </span>
        ) : null}
        {!multiple && single?.state === "failed" ? (
          <span className="chip chip-warn">{single.error}</span>
        ) : null}
      </div>

      {tooMany !== null ? (
        <p className="error" role="alert" data-testid="upload-too-many"
           style={{ marginBlockStart: 10 }}>
          {fill(t("upload.tooMany"), { count: tooMany })}
        </p>
      ) : null}

      {/* التقدّم بالأرقام أولًا: النسبة تُقرأ بلمحة، والميجابايتات تقول
          إن شيئًا يتحرّك فعلًا — والشريط زينةٌ فوقهما لا بديلٌ عنهما. */}
      {!multiple && single?.state === "uploading" && single.total > 0 ? (
        <div style={{ marginBlockStart: 12 }} data-testid="upload-progress">
          <div
            className="metric-label"
            role="status"
            aria-live="polite"
            data-upload-percent={percentOf(single)}
          >
            {t("upload.progress")}: {percentOf(single)}%
            {" "}— {mb(single.loaded)} / {mb(single.total)} MB
          </div>
          <div
            role="progressbar"
            aria-valuenow={percentOf(single)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("upload.progress")}
            style={{
              blockSize: 4, marginBlockStart: 6, borderRadius: 2,
              background: "var(--surface-2, rgba(128,128,128,0.2))",
            }}
          >
            <div
              style={{
                blockSize: "100%", inlineSize: `${percentOf(single)}%`, borderRadius: 2,
                background: "var(--athera-teal)", transition: "inline-size 120ms linear",
              }}
            />
          </div>
          {/* الرفع لم ينتهِ بعد، والحفظ لم يُؤكَّد — فلا كلمة «تم» هنا. */}
          <p className="metric-label" style={{ marginBlockStart: 6 }}>
            {t("upload.keepOpen")}
          </p>
        </div>
      ) : null}

      {/* ── الدفعة: ملخّصٌ صادق، ثم صفٌّ لكلّ ملفٍ بحاله ── */}
      {multiple && items.length ? (
        <div style={{ marginBlockStart: 12 }} data-testid="upload-batch">
          <div className="metric-label" role="status" aria-live="polite"
               data-testid="upload-batch-summary">
            {busy
              ? [
                  fill(t("upload.batchBusy"),
                       { uploading: counts.uploading, total: counts.total }),
                  counts.stored ? fill(t("upload.batchStored"), { stored: counts.stored }) : "",
                  counts.queued ? fill(t("upload.batchQueued"), { queued: counts.queued }) : "",
                  counts.failed ? fill(t("upload.batchFailed"), { failed: counts.failed }) : "",
                ].filter(Boolean).join(" · ")
              : [
                  fill(t("upload.batchDone"),
                       { stored: counts.stored, total: counts.total }),
                  counts.failed
                    ? fill(t("upload.batchDoneFailed"), { failed: counts.failed })
                    : "",
                ].filter(Boolean).join(" · ")}
          </div>

          <ul
            data-testid="upload-queue"
            style={{
              listStyle: "none", padding: 0, margin: "10px 0 0",
              display: "flex", flexDirection: "column", gap: 8,
            }}
          >
            {items.map((item) => (
              <li
                key={item.id}
                data-testid="upload-row"
                data-upload-state={item.state}
                data-upload-name={item.file.name}
                data-upload-percent={item.state === "uploading" ? percentOf(item) : undefined}
                style={{
                  display: "flex", flexWrap: "wrap", alignItems: "center",
                  gap: "4px 10px", fontSize: 13.5,
                }}
              >
                {/* الاسمُ الطويل يُقصّ ولا يدفع الصفَّ خارج الشاشة. */}
                <span
                  style={{
                    flex: "1 1 12ch", minInlineSize: 0, overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}
                  title={item.file.name}
                >
                  {item.file.name}
                </span>

                {item.state === "queued" ? (
                  <span className="metric-label">{t("upload.queued")}</span>
                ) : null}

                {item.state === "uploading" ? (
                  <span className="metric-label" style={{ whiteSpace: "nowrap" }}>
                    {percentOf(item)}% — {mb(item.loaded)} / {mb(item.total)} MB
                  </span>
                ) : null}

                {item.state === "stored" ? (
                  <span className="chip chip-ok">✓ {t("upload.stored")}</span>
                ) : null}

                {item.state === "failed" ? (
                  <>
                    <span className="chip chip-warn" style={{ minInlineSize: 0 }}>
                      {item.error}
                    </span>
                    <button
                      type="button"
                      className="ai-tool"
                      data-testid="upload-retry"
                      onClick={() => retry(item.id)}
                    >
                      {t("upload.retry")}
                    </button>
                  </>
                ) : null}

                {item.state === "uploading" ? (
                  <div
                    role="progressbar"
                    aria-valuenow={percentOf(item)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${t("upload.progress")} — ${item.file.name}`}
                    style={{
                      flexBasis: "100%", blockSize: 3, borderRadius: 2,
                      background: "var(--surface-2, rgba(128,128,128,0.2))",
                    }}
                  >
                    <div
                      style={{
                        blockSize: "100%", inlineSize: `${percentOf(item)}%`,
                        borderRadius: 2, background: "var(--athera-teal)",
                        transition: "inline-size 120ms linear",
                      }}
                    />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>

          {busy ? (
            <p className="metric-label" style={{ marginBlockStart: 8 }}>
              {t("upload.keepOpen")}
            </p>
          ) : null}
        </div>
      ) : null}

      {!loading && !storageReady ? (
        <div className="gate" style={{ marginBlockStart: 12 }}>
          <span aria-hidden="true">⏻</span>
          <span><strong>{t("upload.gateTitle")}</strong> {t("upload.gateBody")}</span>
        </div>
      ) : null}

      {counts.stored > 0 && !busy ? (
        <p className="note" style={{ marginBlockStart: 12 }}>{t("upload.readyNote")}</p>
      ) : null}
    </section>
  );
}
