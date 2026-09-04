"use client";

import { useRef, useState } from "react";

import { AtheraApiError } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { libraryFileFromUpload, type LibraryFile, type StoredFile } from "@/lib/library";
import { usePosture } from "@/lib/posture";
import { uploadWithProgress } from "@/lib/upload";

/**
 * رفع ملفات البحث.
 *
 * **الحالات المعروضة صادقة حرفيًا:** «جارٍ الرفع» ثم «تم الحفظ». ولا
 * «حُلِّل» ولا «فُهم» — التفكيك لم يقع، والادعاء به أسوأ من غيابه. و«تم
 * الحفظ» لا تُعرض إلا بعد ردّ الخادم ٢٠١، وهو لا يُصدره إلا بعد أن يستقرّ
 * الكائن في التخزين ويُكتب صفّه — فالكلمة مسنودة لا متفائلة.
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
 */
type State = "idle" | "uploading" | "stored" | "failed";

const ACCEPT = ".pdf,.docx,.doc,.txt,.ris,.bib,.csv,.xls,.xlsx,.sav,.zsav";

/** ميجابايت بخانةٍ عشرية واحدة — والباحث يقرأ الحجم لا البايتات. */
const mb = (bytes: number) => (bytes / (1024 * 1024)).toFixed(1);

export function FileUpload({
  locale, messages, onUploaded, folderId = null,
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
   * رفع، ويسقط صامتًا لو فشل النقل بعد نجاح الرفع.
   */
  folderId?: string | null;
}) {
  const t = translator(messages);
  const { items, loading } = usePosture(locale);
  const storageReady = items.find((i) => i.key === "storage")?.value !== "none";
  const inputRef = useRef<HTMLInputElement>(null);

  const [state, setState] = useState<State>("idle");
  const [file, setFile] = useState<StoredFile | null>(null);
  const [sent, setSent] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);

  function send(selected: File) {
    setState("uploading");
    setError(null);
    setFile(null);
    setSent({ loaded: 0, total: selected.size });

    const body = new FormData();
    body.append("upload", selected);
    if (folderId) body.append("folder_id", folderId);
    // **عبر عميل الـAPI لا `fetch` خامًّا.** كان يبني الطلب بنفسه ليتجنّب
    // ترويسة JSON التي تكسر `FormData` — فيفقد حارس الإعداد المفقود
    // وتوحيد رسائل الخطأ ومعالجة انتهاء الجلسة. وهذه الأداة تحفظ الثلاثة
    // وتزيد عليها نسبة التقدّم التي لا يعطيها `fetch` أصلًا.
    uploadWithProgress<StoredFile>("/api/v1/files/upload", body, {
      locale,
      onProgress: (progress) =>
        setSent({ loaded: progress.loaded, total: progress.total || selected.size }),
    })
      .then((stored) => {
        setFile(stored);
        setState("stored");
        onUploaded?.(libraryFileFromUpload(stored));
      })
      .catch((err) => {
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("upload.failed"));
        setState("failed");
      });
  }

  const disabled = loading || !storageReady || state === "uploading";
  const percent = sent.total > 0 ? Math.min(100, Math.round((sent.loaded / sent.total) * 100)) : 0;

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
        className="sr-only"
        onChange={(e) => {
          const selected = e.target.files?.[0];
          if (selected) send(selected);
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
          📎 {state === "uploading" ? t("upload.uploading") : t("upload.pick")}
        </button>
        {state === "stored" && file ? (
          <span className="chip chip-ok">
            ✓ {t("upload.stored")} — {file.original_filename} · {Math.round(file.size_bytes / 1024)} KB
          </span>
        ) : null}
        {state === "failed" ? <span className="chip chip-warn">{error}</span> : null}
      </div>

      {/* التقدّم بالأرقام أولًا: النسبة تُقرأ بلمحة، والميجابايتات تقول
          إن شيئًا يتحرّك فعلًا — والشريط زينةٌ فوقهما لا بديلٌ عنهما. */}
      {state === "uploading" && sent.total > 0 ? (
        <div style={{ marginBlockStart: 12 }} data-testid="upload-progress">
          <div
            className="metric-label"
            role="status"
            aria-live="polite"
            data-upload-percent={percent}
          >
            {t("upload.progress")}: {percent}% — {mb(sent.loaded)} / {mb(sent.total)} MB
          </div>
          <div
            role="progressbar"
            aria-valuenow={percent}
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
                blockSize: "100%", inlineSize: `${percent}%`, borderRadius: 2,
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

      {!loading && !storageReady ? (
        <div className="gate" style={{ marginBlockStart: 12 }}>
          <span aria-hidden="true">⏻</span>
          <span><strong>{t("upload.gateTitle")}</strong> {t("upload.gateBody")}</span>
        </div>
      ) : null}

      {state === "stored" ? (
        <p className="note" style={{ marginBlockStart: 12 }}>{t("upload.readyNote")}</p>
      ) : null}
    </section>
  );
}
