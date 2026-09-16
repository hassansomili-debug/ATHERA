/**
 * أشكالُ ما يردّه خادمُ الفريق — **موضعٌ واحدٌ تقرؤه الشاشةُ وأجزاؤها**.
 *
 * فبعد تفكيك شاشة الفريق إلى بطاقةٍ ولوحِ تفصيلٍ ونافذةِ دعوة، صار الشكلُ
 * الواحد يُقرأ في ثلاثة ملفّات. وإعادةُ كتابته في كلٍّ منها تعني ثلاثةَ
 * أشكالٍ تفترق بأوّل حقلٍ يضيفه الخادم.
 *
 * **ولا شكلَ هنا يُوسّع ما يقوله الخادم**: هذه أسماءُ حقولٍ تُقرأ، لا
 * عقدٌ يُفرض عليه. والعقدُ في `apps/api/athera_api/routers/team.py`.
 */

export interface TeamProject {
  id: string;
  working_title: string;
}

export interface Member {
  id: string;
  display_name: string;
  user_id: string | null;
  is_account_linked: boolean;
  invited_email: string | null;
  role: string;
  role_label: string;
  access_state: string;
  access_label: string;
  permissions: string[];
  permission_labels: string[];
  credit_roles: string[];
  credit_labels: string[];
  is_author: boolean;
  author_position: number | null;
  consent_state: string;
  consent_label: string;
  consent_method: string | null;
  consent_method_label: string | null;
  consent_recorded_at: string | null;
  consent_recorded_by: string | null;
  consent_needs_recollection: boolean;
}

export interface Invitation {
  id: string;
  invited_email: string;
  invited_display_name: string;
  proposed_role_label: string;
  proposed_permissions: string[];
  state: string;
  state_label: string;
  expires_at: string;
  /** يصل مرّةً واحدةً في جواب الإنشاء — ولا تُعيده أيُّ قراءةٍ بعدها. */
  token?: string;
}

export interface PendingAction {
  kind: string;
  kind_label: string;
  subject_id: string;
  statement: string;
  is_mine: boolean;
}

export interface Decision {
  id: string;
  decision_kind: string;
  kind_label: string;
  statement: string;
  gate: string | null;
  decided_at: string | null;
  supersedes_id: string | null;
  is_superseded: boolean;
  is_current: boolean;
  superseded_by_id: string | null;
}

export interface MemberEvent {
  id: string;
  member_id: string | null;
  invitation_id: string | null;
  event_kind: string;
  occurred_at: string;
  note_ar: string | null;
}

/**
 * حالُ المدخل ⇒ طرازُ الشريحة — **ولا لونَ وحده يقول الحال**.
 *
 * فالنصُّ يُقرأ دائمًا (`access_label` من الخادم)، واللونُ زيادةٌ عليه:
 * شاشةٌ تفرّق «نشِط» من «موقوف» باللون وحده لا يقرؤها من لا يميّزه.
 */
export function accessChip(state: string): string {
  if (state === "active") return "chip chip-ok";
  if (state === "suspended") return "chip chip-warn";
  return "chip chip-muted";
}

/**
 * جوابُ محاولةِ الدعوة — **والرفضُ قيمةٌ تُردّ لا لافتةٌ تُنشر في الصفحة**.
 *
 * ## العطبُ الذي يعالجه هذا النوع
 *
 * كانت `invite()` تُنشر رسالةَ الخطأ في حالِ الصفحة، فتُرسم **فوق** النافذة
 * المفتوحة — أي خلفها بصريًّا. فيضغط المديرُ «أرسل الدعوة» فلا يرى شيئًا
 * يتغيّر: النافذةُ باقيةٌ بحقولها، والعلّةُ مكتوبةٌ في موضعٍ يحجبه ما ينظر
 * إليه. فيُعيد الضغطَ ثمّ ينصرف.
 *
 * **فالعلّةُ تُردّ إلى من طلب الفعل**، ويعرضها هو في موضعه. ولا تُستبدل
 * دلالةُ الخادم: النصُّ هو `AtheraApiError.localized(locale)` بعينه.
 */
export type InviteOutcome =
  | { ok: true; token: string | null }
  | { ok: false; error: string };
