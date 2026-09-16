"use client";

import { useState } from "react";

import { TeamOverlay } from "./TeamOverlay";
import type { Vocabulary } from "./permissionGroups";

/**
 * دعوةُ باحثٍ، ورمزُها الذي يُعرض مرّةً — **نافذةٌ واحدةٌ بخطوتين** (RC-T1C UX-1).
 *
 * ## العطبُ الذي يعالجه هذا الملفّ
 *
 * كان النموذجُ مفتوحًا دائمًا في أسفل صفحةٍ طويلة، ثمّ **يُدسّ الرمزُ في
 * بطاقةٍ فوقه** بعد الإرسال. فمن أرسل دعوةً يبحث في الصفحة عن رمزٍ لا
 * يعرف أنّه ظهر، ولا يعرف أنّه لن يظهر ثانيًا — **والرمزُ يُعرض مرّةً
 * واحدة**: الخادمُ يحفظ تجزئتَه لا نصَّه.
 *
 * فيُفتح النموذجُ عند الطلب، وحين ينجح **تتحوّل النافذةُ نفسُها إلى
 * إعلانِ نجاحٍ يحمل الرمزَ وزرَّ نسخه**. ونافذةٌ لا تُغلق حتى يقول صاحبُها
 * «تمّ» أوضحُ من بطاقةٍ تظهر في مكانٍ لا ينظر إليه.
 *
 * ## والرمزُ في ذاكرة React وحدها
 *
 * لا في المسار، ولا في `localStorage`، ولا في أيّ خزنٍ يبقى بعد إغلاق
 * اللسان. فرمزُ دعوةٍ في شريط العنوان يُنسخ في تاريخِ المتصفّح وفي أيّ
 * سجلِّ وسيط، ورمزٌ في الخزن المحلّي يبقى بعد أن ينتهي أمرُه. **وهو
 * اعتمادٌ يفتح عضويّة** — لا حالُ شاشةٍ تُستعاد.
 *
 * وحين تُغلق النافذةُ يُمحى من الحالة. ولا مسارَ في الـAPI يُرجعه، فلا
 * سبيل إلى إظهاره ثانيةً — وذاك مقصود: لو وُجد لصار من قرأ قائمةَ
 * الدعوات قادرًا على انتحال القبول.
 */
export function InviteDialog({
  open,
  t,
  busy,
  roleVocab,
  defaultRole,
  onClose,
  onInvite,
}: {
  open: boolean;
  t: (path: string) => string;
  busy: boolean;
  roleVocab: Vocabulary[];
  defaultRole: string;
  onClose: () => void;
  /** يردّ الرمزَ عند النجاح، و`null` إن رُدّت الدعوة. */
  onInvite: (input: { name: string; email: string; role: string }) => Promise<string | null>;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState(defaultRole);
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function close() {
    // **ولا يبقى الرمزُ في الذاكرة بعد إغلاق النافذة.**
    setToken(null);
    setCopied(false);
    setName("");
    setEmail("");
    onClose();
  }

  async function copy() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
    } catch {
      // سياقٌ لا يمنح الحافظة: يُنسخ بالطريق القديم بدل أن يُطلب من
      // الباحث تظليلُ رمزٍ من أربعين محرفًا بيده.
      const sink = document.createElement("textarea");
      sink.value = token;
      sink.setAttribute("readonly", "");
      sink.style.position = "fixed";
      sink.style.opacity = "0";
      document.body.appendChild(sink);
      sink.select();
      try {
        setCopied(document.execCommand("copy"));
      } finally {
        document.body.removeChild(sink);
      }
    }
  }

  if (!open) return null;

  // ══════════ الخطوة ٢ · نجحت الدعوة، وهذا رمزُها ══════════
  if (token) {
    return (
      <TeamOverlay
        open
        variant="modal"
        onClose={close}
        title={t("team.invitationCreated")}
        titleId="team-token-title"
        closeLabel={t("team.close")}
        testId="team-token"
        footer={
          <div className="team-actions">
            <button
              type="button"
              className="btn-primary"
              data-testid="team-token-copy"
              onClick={() => void copy()}
            >
              {copied ? t("team.tokenCopied") : t("team.copyToken")}
            </button>
            <button
              type="button"
              className="btn-quiet"
              data-testid="team-token-done"
              onClick={close}
            >
              {t("team.done")}
            </button>
          </div>
        }
      >
        {/* **ويُقال إنّه مرّةٌ واحدة، قبل الرمز لا بعده.** */}
        <p>{t("team.tokenOnceShort")}</p>
        <p className="provenance-note">{t("team.tokenChannel")}</p>
        {/* ورمزٌ طويلٌ لا يدفع النافذةَ أفقيًّا على ٣٧٥px. */}
        <code className="team-token-value">{token}</code>
        {copied ? <p className="badge-ok" role="status">{t("team.tokenCopied")}</p> : null}
      </TeamOverlay>
    );
  }

  // ══════════ الخطوة ١ · من تدعو، وبأيّ دور ══════════
  const ready = name.trim().length >= 2 && email.includes("@");
  return (
    <TeamOverlay
      open
      variant="modal"
      onClose={close}
      title={t("team.inviteMember")}
      titleId="team-invite-title"
      closeLabel={t("team.close")}
      testId="team-invite-dialog"
    >
      {/* **والدعوةُ تقترح دورًا ولا تمنح شيئًا**: لا عضويّةَ حتى يقبل بحسابه. */}
      <p className="provenance-note">{t("team.inviteNote")}</p>
      <div className="form team-form">
        <label htmlFor="team-invite-name">
          {t("team.displayName")}
          <input
            id="team-invite-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label htmlFor="team-invite-email">
          {t("team.email")}
          <input
            id="team-invite-email"
            type="email"
            autoComplete="off"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label htmlFor="team-invite-role">
          {t("team.role")}
          <select
            id="team-invite-role"
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            {roleVocab.map((item) => (
              <option key={item.key} value={item.key}>{item.label}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="team-actions">
        <button
          type="button"
          className="btn-primary"
          disabled={busy || !ready}
          data-testid="team-invite-submit"
          onClick={() => {
            void (async () => {
              const issued = await onInvite({ name: name.trim(), email: email.trim(), role });
              // **ولا تُعلن النافذةُ نجاحًا لم يقع.** فإن رُدّت الدعوة بقي
              // النموذجُ بحقوله، والخطأُ يُقرأ في موضعه من الشاشة.
              if (issued) setToken(issued);
            })();
          }}
        >
          {t("team.sendInvitation")}
        </button>
        <button type="button" className="btn-quiet" onClick={close}>
          {t("projectRecruitment.cancel")}
        </button>
      </div>
    </TeamOverlay>
  );
}
