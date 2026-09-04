"use client";

import { useEffect, useState } from "react";

import { AtheraApiError } from "@/lib/api";
import { type Locale, type Messages, translator } from "@/lib/i18n";
import { listAllFolders, type FolderOption } from "@/lib/library";

/**
 * «نقل إلى…» — اختيارُ وجهةٍ من مجلَّدات المكتبة.
 *
 * **والوجهة تُعرض بمسارها كاملًا.** مجلَّدان باسم «المنهج» تحت أبوين
 * مختلفين لا يُفرَّق بينهما بالاسم، فيختار الباحث غير ما أراد ولا يعلم أنه
 * أخطأ إلا حين يفقد ملفه.
 *
 * **والقائمة تُقرأ عند فتح اللوحة لا عند فتح الشاشة.** فأكثر زياراتِ
 * المكتبة لا نقل فيها، وقراءةُ كل المجلَّدات في كل زيارة رحلةٌ تُدفع بلا
 * سؤال.
 */
export function FolderPicker({
  locale, messages, targetName, excludeId, currentFolderId, busy, onChoose, onCancel,
}: {
  locale: Locale;
  messages: Messages;
  /** اسمُ ما يُنقل — تُبنى منه تسميات الأزرار فتقول على أيّ شيء تعمل. */
  targetName: string;
  /** مجلَّدٌ لا يصلح وجهةً لنفسه. وذرّيتُه يرفضها الخادم برسالةٍ مفهومة. */
  excludeId?: string;
  currentFolderId: string | null;
  busy: boolean;
  onChoose: (folderId: string | null) => void;
  onCancel: () => void;
}) {
  const t = translator(messages);
  const [options, setOptions] = useState<FolderOption[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string>("");

  useEffect(() => {
    let live = true;
    listAllFolders(locale)
      .then((rows) => {
        if (!live) return;
        setOptions(rows);
        setState("ready");
      })
      .catch((err) => {
        if (!live) return;
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
        setState("failed");
      });
    return () => {
      live = false;
    };
  }, [locale]);

  // الجذر خيارٌ صريح: «انقل إلى مكتبتي» فعلٌ يطلبه الباحث كثيرًا، ولا
  // يُترك بلا مدخل لأن قيمته `null`.
  const selectable = options.filter((row) => row.id !== excludeId);

  return (
    <div className="card" style={{ marginBlockStart: 8, padding: 12 }}>
      {state === "loading" ? (
        <p role="status" aria-live="polite">{t("library.loadingFolders")}</p>
      ) : state === "failed" ? (
        <p className="error" role="alert">{error ?? t("library.foldersFailed")}</p>
      ) : (
        <>
          <label style={{ display: "block", marginBlockEnd: 8 }}>
            {t("library.moveTarget")}
            <select
              value={chosen}
              aria-label={`${t("library.moveTarget")}: ${targetName}`}
              onChange={(event) => setChosen(event.target.value)}
              style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
            >
              <option value="">{t("library.moveToRoot")}</option>
              {selectable.map((row) => (
                <option key={row.id} value={row.id}>{row.path}</option>
              ))}
            </select>
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              disabled={busy || (chosen || null) === currentFolderId}
              aria-label={`${t("library.moveHere")}: ${targetName}`}
              onClick={() => onChoose(chosen || null)}
            >
              {t("library.moveHere")}
            </button>
            <button
              type="button"
              disabled={busy}
              aria-label={`${t("library.moveCancel")}: ${targetName}`}
              onClick={onCancel}
            >
              {t("library.moveCancel")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
