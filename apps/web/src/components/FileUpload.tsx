"use client";

import { useRef, useState } from "react";

import { AtheraApiError } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { usePosture } from "@/lib/posture";
import { getAccessToken } from "@/lib/session";

/**
 * رفع ملفات البحث.
 *
 * **الحالات المعروضة صادقة حرفيًا:** «جارٍ الرفع» ثم «تم الحفظ». ولا
 * «حُلِّل» ولا «فُهم» — التفكيك لم يقع، والادعاء به أسوأ من غيابه.
 *
 * والرفع مستقل عن حالة النموذج: التخزين قد يكون مُهيّأ بينما استدعاء
 * النموذج مطفأ، فالبوابتان تُقرآن من `/settings/posture` منفصلتين.
 *
 * ولا اسم مزوّد تخزين يظهر هنا: الباحث يرفع «ملف بحث»، لا كائنًا في دلو.
 */
type State = "idle" | "uploading" | "stored" | "failed";

interface StoredFile {
  id: string;
  original_filename: string;
  size_bytes: number;
  status: string;
}

const ACCEPT = ".pdf,.docx,.doc,.txt,.ris,.bib,.csv,.xls,.xlsx,.sav,.zsav";

export function FileUpload({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  const { items, loading } = usePosture(locale);
  const storageReady = items.find((i) => i.key === "storage")?.value !== "none";
  const inputRef = useRef<HTMLInputElement>(null);

  const [state, setState] = useState<State>("idle");
  const [file, setFile] = useState<StoredFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(selected: File) {
    setState("uploading");
    setError(null);
    setFile(null);
    try {
      const body = new FormData();
      body.append("upload", selected);
      const token = getAccessToken();
      const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      // `FormData` يضبط حدّ الأجزاء بنفسه — لا تُضبط Content-Type يدويًا.
      const response = await fetch(`${base}/api/v1/files/upload`, {
        method: "POST",
        headers: {
          "Accept-Language": locale,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new AtheraApiError(response.status, payload?.error ?? {
          code: "file.upload_failed", locale, message: t("upload.failed"),
          messages: { ar: t("upload.failed"), en: t("upload.failed") },
        });
      }
      setFile((await response.json()) as StoredFile);
      setState("stored");
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("upload.failed"));
      setState("failed");
    }
  }

  const disabled = loading || !storageReady || state === "uploading";

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
          if (selected) void send(selected);
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
