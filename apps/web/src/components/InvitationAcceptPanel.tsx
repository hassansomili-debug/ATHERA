"use client";

import { useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { getMessages, translator, type Locale } from "@/lib/i18n";

/**
 * قبولُ دعوةٍ برمزٍ وصل الباحثَ بيد إنسان (RC-T1C).
 *
 * **ولا بريدَ في V1 ولا تسليمَ آليّ، ولا يُتظاهر بواحدٍ منهما.** المديرُ
 * يرى الرمزَ مرّةً ويُرسله بقناةٍ يختارها، والمرشَّحُ يلصقه هنا. وجملةُ
 * «أُرسلت الدعوةُ إلى بريده» كذبةٌ صغيرةٌ تُنتج انتظارًا طويلًا.
 *
 * **ولا مسارَ يُرجع الرمز.** لا في «طلباتي» ولا في أيّ قراءة: الخادمُ
 * يحفظ تجزئتَه لا نصَّه، ولا API يُظهره — ولو وُجد لَصار مَن قرأ قائمةَ
 * الطلبات قادرًا على انتحال القبول. فالحقلُ هنا مُدخَلٌ لا مُخرَج.
 *
 * ومشتركٌ بين شاشتين عمدًا — «الفريق» و«طلباتي» — فنسختان تفترقان بأوّل
 * تعديل، فتصير إحداهما تعرض الرمزَ أو تبتلع خطأً تقوله الأخرى.
 */
export function InvitationAcceptPanel({
  locale,
  onAccepted,
  title,
  note,
}: {
  locale: Locale;
  /** يُستدعى بعد قبولٍ ناجح — لتحديث «طلباتي» و«أبحاثي» معًا. */
  onAccepted?: () => void | Promise<void>;
  /** عنوانٌ بديل حين تكون الدعوةُ معلومةً للسياق (شاشةُ الطلبات). */
  title?: string;
  note?: string;
}) {
  const t = translator(getMessages(locale));
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/api/v1/invitations/accept", {
        method: "POST",
        locale,
        body: JSON.stringify({ token: token.trim() }),
      });
      setToken("");
      setDone(true);
      await onAccepted?.();
    } catch (err) {
      // **ورمزُ غيرِك يُردّ ٤٠٤ لا ٤٠٣.** فالخادمُ لا يقول «هذه الدعوةُ
      // لشخصٍ آخر»، وذاك مقصود: لو قالها لصار المسارُ عدّادَ دعوات.
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
      setDone(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="card" style={{ marginBlockStart: 12 }} data-testid="invitation-accept">
      <strong>{title ?? t("team.joinByToken")}</strong>
      <p className="provenance-note">{note ?? t("team.joinNote")}</p>
      <label style={{ display: "block", marginBlockStart: 8 }}>
        {t("team.joinByToken")}
        <input
          type="text"
          data-testid="invitation-token-input"
          autoComplete="off"
          style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
      </label>
      {error ? <p className="error">{error}</p> : null}
      {done ? <p className="badge-ok">{t("collaborationOpportunities.membershipCreated")}</p> : null}
      <button
        type="button"
        data-testid="invitation-accept-submit"
        style={{ marginBlockStart: 8 }}
        disabled={busy || token.trim().length < 16}
        onClick={() => void accept()}
      >
        {t("team.acceptInvitation")}
      </button>
    </article>
  );
}
