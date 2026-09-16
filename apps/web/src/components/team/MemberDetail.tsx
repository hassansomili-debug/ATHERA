"use client";

import { useState } from "react";

import { TeamOverlay } from "./TeamOverlay";
import { groupPermissions, type Vocabulary } from "./permissionGroups";
import { accessChip, type Member } from "./types";

/**
 * تفصيلُ العضو — **لوحٌ يُفتح عند الطلب، لا عمودٌ مفتوحٌ دائمًا** (RC-T1C UX-1).
 *
 * ## العطبُ الذي يعالجه هذا الملفّ
 *
 * كانت بطاقةُ كلِّ عضوٍ تطبع: الصلاحياتِ التسع، وأدوارَ CRediT، وحالَ
 * التأليف، وحالَ الموافقة وطريقَتها ومن سجّلها — ثمّ مُنتقي دورٍ ومحرّرَ
 * صلاحياتٍ وثلاثةَ أزرارٍ للمدخل. فصار من يبحث عن «من في هذا البحث؟»
 * يقرأ نموذجَ البيانات كلَّه ليجد اسمًا ودورًا. **والمالكُ ردّ الشاشةَ
 * لهذا**: صحيحةٌ ومُعجِزة.
 *
 * فالبطاقةُ تقول أربعةً (اسمٌ، دورٌ، حالُ مدخلٍ، أرتباطُ حساب)، وما عداها
 * يُفتح هنا. **ولا حقلَ حُذف**: التفصيلُ كاملٌ في موضعه، والبسيطُ بسيطٌ في
 * موضعه — وذاك هو الكشفُ التدريجيّ لا التبسيطُ بالحذف.
 *
 * ## وثلاثةُ أقسامٍ لأنّها ثلاثةُ أشياء
 *
 *     الوصولُ والصلاحيات   ما يقدر عليه في المنصّة
 *     المساهمةُ العلمية    ما فعله في البحث (CRediT)
 *     التأليفُ والموافقة   ما يُنشر باسمه، وبإقراره هو
 *
 * وجمعُها في قسمٍ واحدٍ هو ما كان يجعل القارئَ يقرأ «عضو» فيفترض
 * «مؤلفٌ وافق». **فالدورُ ليس صلاحية، والصلاحيةُ ليست مساهمة، والمساهمةُ
 * ليست تأليفًا، والعضويةُ ليست موافقة** — أربعةُ تمييزاتٍ تُعرض في ثلاثة
 * أقسامٍ لا في سطرٍ واحد.
 *
 * ## وإخفاءُ زرٍّ ليس حدَّ أمان
 *
 * فما يُعرض هنا مرهونٌ بـ`manage_team` من `/projects/{id}/access` — إجابةُ
 * خادمٍ لا حالُ شاشة. وكلُّ مسارٍ خلف كلِّ زرٍّ يسأل عن صلاحيّته بنفسه؛
 * وهذا الشرطُ يمنع أن يُعرض زرٌّ ثمّ يُردّ، لا أن يُمنع فعلٌ.
 */
type Tab = "access" | "contribution" | "authorship";

const TABS: readonly Tab[] = ["access", "contribution", "authorship"];

export function MemberDetail({
  member,
  t,
  locale,
  canManageTeam,
  busy,
  roleVocab,
  permissionVocab,
  onClose,
  onChangeRole,
  onSavePermissions,
  onChangeAccess,
}: {
  member: Member;
  t: (path: string) => string;
  locale: string;
  canManageTeam: boolean;
  busy: boolean;
  roleVocab: Vocabulary[];
  permissionVocab: Vocabulary[];
  onClose: () => void;
  onChangeRole: (memberId: string, next: string) => void;
  /** يردّ `true` إن قبل الخادمُ الحفظ — وعليه وحده يُغلق المحرّر. */
  onSavePermissions: (memberId: string, permissions: string[]) => Promise<boolean>;
  onChangeAccess: (memberId: string, next: string) => void;
}) {
  // **ولا تأثيرَ يُصفّر هذه الحالات عند تغيّر العضو.** الأبُ يُركّب هذا
  // اللوحَ بـ`key={member.id}`، فعضوٌ آخر مُركّبٌ آخر وحالاتُه ابتدائيّة
  // بحكم React — لا بـ`setState` في `useEffect` (وهو ممنوعٌ بقاعدة
  // `react-hooks/set-state-in-effect`، ويُنتج تصييرةً زائدةً يرى القارئُ
  // فيها لوحَ العضو السابق لوهلة).
  const [tab, setTab] = useState<Tab>("access");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>(member.permissions);
  const [confirming, setConfirming] = useState(false);

  const groups = groupPermissions(permissionVocab);

  return (
    <TeamOverlay
      open
      onClose={onClose}
      variant="drawer"
      title={member.display_name}
      titleId={`team-member-detail-title-${member.id}`}
      closeLabel={t("team.close")}
      testId={`team-member-detail-${member.id}`}
    >
      <p className="metric-label" style={{ marginBlockStart: 0 }}>
        {member.role_label} ·{" "}
        <span className={accessChip(member.access_state)}>{member.access_label}</span>
      </p>

      <nav aria-label={member.display_name}>
        <ul className="team-subtabs" role="tablist">
          {TABS.map((key) => (
            <li key={key} role="none">
              <button
                type="button"
                role="tab"
                id={`team-member-tab-${key}-${member.id}`}
                aria-selected={tab === key}
                aria-controls={`team-member-panel-${key}-${member.id}`}
                className={tab === key ? "chip chip-stage" : "chip chip-muted"}
                data-testid={`team-member-tab-${key}`}
                onClick={() => setTab(key)}
              >
                {t(`team.detail.${key}`)}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* ══════════ ١ · الوصولُ والصلاحيات ══════════ */}
      {tab === "access" ? (
        <section
          role="tabpanel"
          id={`team-member-panel-access-${member.id}`}
          aria-labelledby={`team-member-tab-access-${member.id}`}
          data-testid={`team-member-panel-access-${member.id}`}
        >
          {/* **والفرقُ يُقال قبل الحقلين، لا بعدهما.** */}
          <p className="provenance-note">{t("team.roleIsNotPermission")}</p>

          <div className="team-field">
            <span className="metric-label">{t("team.role")}</span>
            {canManageTeam ? (
              <label className="sr-only" htmlFor={`team-role-${member.id}`}>
                {t("team.changeRole")}
              </label>
            ) : null}
            {canManageTeam ? (
              <select
                id={`team-role-${member.id}`}
                value={member.role}
                disabled={busy}
                data-testid={`team-role-${member.id}`}
                onChange={(event) => onChangeRole(member.id, event.target.value)}
              >
                {roleVocab.map((item) => (
                  <option key={item.key} value={item.key}>{item.label}</option>
                ))}
              </select>
            ) : (
              <strong>{member.role_label}</strong>
            )}
          </div>

          <div className="team-field">
            <span className="metric-label">{t("team.accessState")}</span>
            <strong>{member.access_label}</strong>
          </div>

          <div className="team-field">
            <span className="metric-label">
              {member.is_account_linked ? t("team.accountLinked") : t("team.nameOnly")}
            </span>
            {member.invited_email ? <strong>{member.invited_email}</strong> : null}
          </div>

          <h3 className="team-subhead">{t("team.permissions")}</h3>
          {editing && canManageTeam ? (
            <div data-testid={`team-permission-editor-${member.id}`}>
              {groups.map((group) => (
                <fieldset key={group.id} className="team-permission-group">
                  <legend className="metric-label">{t(`team.permissionGroup.${group.id}`)}</legend>
                  {group.items.map((item) => (
                    <label key={item.key} className="team-check">
                      <input
                        type="checkbox"
                        data-testid={`team-permission-${member.id}-${item.key}`}
                        checked={draft.includes(item.key)}
                        onChange={(event) =>
                          setDraft((prev) =>
                            event.target.checked
                              ? [...prev, item.key]
                              : prev.filter((key) => key !== item.key),
                          )
                        }
                      />{" "}
                      <span>{item.label}</span>
                    </label>
                  ))}
                </fieldset>
              ))}
              <div className="team-actions">
                <button
                  type="button"
                  className="btn-primary"
                  disabled={busy || !draft.length}
                  data-testid={`team-permission-save-${member.id}`}
                  // **والمحرّرُ يُغلق بقبول الخادم لا بضغط الزرّ.** فإغلاقُه
                  // على النيّة يُظهر «حُفظ» على حفظٍ رُدّ، والباحثُ يمضي
                  // ظانًّا أنّه منح صلاحيةً لم تُمنح.
                  onClick={() => {
                    void (async () => {
                      if (await onSavePermissions(member.id, draft)) setEditing(false);
                    })();
                  }}
                >
                  {t("team.savePermissions")}
                </button>
                <button
                  type="button"
                  className="btn-quiet"
                  onClick={() => {
                    setEditing(false);
                    setDraft(member.permissions);
                  }}
                >
                  {t("projectRecruitment.cancel")}
                </button>
              </div>
            </div>
          ) : (
            <>
              <ul className="team-permission-list" data-testid={`team-member-permissions-${member.id}`}>
                {member.permission_labels.length > 0 ? (
                  member.permission_labels.map((label) => <li key={label}>{label}</li>)
                ) : (
                  <li className="metric-label">{t("team.noPermissions")}</li>
                )}
              </ul>
              {canManageTeam ? (
                <button
                  type="button"
                  className="btn-quiet"
                  data-testid={`team-edit-permissions-${member.id}`}
                  onClick={() => {
                    setDraft(member.permissions);
                    setEditing(true);
                  }}
                >
                  {t("team.managePermissions")}
                </button>
              ) : null}
            </>
          )}

          {/* ══ إدارةُ الوصول — **مفصولةٌ بصريًّا عمدًا** ══
              فإيقافُ عضوٍ وإزالتُه ليسا تحريرَ حقل، وزرٌّ بينهما يُضغط سهوًا. */}
          {canManageTeam ? (
            <section className="team-danger" data-testid={`team-access-management-${member.id}`}>
              <h3 className="team-subhead">{t("team.accessManagement")}</h3>
              <p className="provenance-note">{t("team.accessManagementNote")}</p>
              <div className="team-actions">
                {member.access_state === "active" ? (
                  <button
                    type="button"
                    className="btn-quiet"
                    disabled={busy}
                    data-testid={`team-suspend-${member.id}`}
                    onClick={() => onChangeAccess(member.id, "suspended")}
                  >
                    {t("team.suspend")}
                  </button>
                ) : null}
                {member.access_state === "suspended" ? (
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy}
                    data-testid={`team-restore-${member.id}`}
                    onClick={() => onChangeAccess(member.id, "active")}
                  >
                    {t("team.restore")}
                  </button>
                ) : null}
                {member.access_state !== "removed" ? (
                  <button
                    type="button"
                    className="btn-danger"
                    disabled={busy}
                    data-testid={`team-remove-${member.id}`}
                    onClick={() => setConfirming(true)}
                  >
                    {t("team.remove")}
                  </button>
                ) : null}
              </div>

              {/* **والإزالةُ تُؤكَّد، ويُقال ما تفعله بالضبط.** ولا يُقال
                  «حذف»: التاريخُ والمساهمةُ يبقيان، والذي يُنزع هو المدخل. */}
              {confirming ? (
                <TeamOverlay
                  open
                  variant="modal"
                  onClose={() => setConfirming(false)}
                  title={t("team.removeConfirmTitle")}
                  titleId={`team-remove-confirm-title-${member.id}`}
                  closeLabel={t("team.close")}
                  testId={`team-remove-confirm-${member.id}`}
                >
                  <p>{t("team.removeConfirmBody").replace("{name}", member.display_name)}</p>
                  <p className="provenance-note">{t("team.removeKeepsHistory")}</p>
                  <div className="team-actions">
                    <button
                      type="button"
                      className="btn-danger"
                      disabled={busy}
                      data-testid={`team-remove-confirm-submit-${member.id}`}
                      onClick={() => {
                        setConfirming(false);
                        onChangeAccess(member.id, "removed");
                      }}
                    >
                      {t("team.removeConfirmAction")}
                    </button>
                    <button
                      type="button"
                      className="btn-quiet"
                      onClick={() => setConfirming(false)}
                    >
                      {t("projectRecruitment.cancel")}
                    </button>
                  </div>
                </TeamOverlay>
              ) : null}
            </section>
          ) : null}
        </section>
      ) : null}

      {/* ══════════ ٢ · المساهمةُ العلمية ══════════ */}
      {tab === "contribution" ? (
        <section
          role="tabpanel"
          id={`team-member-panel-contribution-${member.id}`}
          aria-labelledby={`team-member-tab-contribution-${member.id}`}
          data-testid={`team-member-panel-contribution-${member.id}`}
        >
          <h3 className="team-subhead">{t("team.creditRoles")}</h3>
          {/* **ولا اقتراحَ لأدوار CRediT من نشاطٍ في المنصّة.** */}
          <p className="provenance-note">{t("team.creditNote")}</p>
          <ul className="team-permission-list" data-testid={`team-member-credit-${member.id}`}>
            {member.credit_labels.length > 0 ? (
              member.credit_labels.map((label) => <li key={label}>{label}</li>)
            ) : (
              <li className="metric-label">{t("common.none")}</li>
            )}
          </ul>
        </section>
      ) : null}

      {/* ══════════ ٣ · التأليفُ والموافقة ══════════ */}
      {tab === "authorship" ? (
        <section
          role="tabpanel"
          id={`team-member-panel-authorship-${member.id}`}
          aria-labelledby={`team-member-tab-authorship-${member.id}`}
          data-testid={`team-member-panel-authorship-${member.id}`}
        >
          <div className="team-field">
            <span className="metric-label">{t("team.authorship")}</span>
            <strong data-testid={`team-member-authorship-${member.id}`}>
              {member.is_author ? t("team.declaredAuthor") : t("team.notAnAuthor")}
            </strong>
          </div>
          {member.is_author && member.author_position ? (
            <div className="team-field">
              <span className="metric-label">{t("team.authorPosition")}</span>
              <strong>{member.author_position}</strong>
            </div>
          ) : null}

          <h3 className="team-subhead">{t("team.consent")}</h3>
          {/* **والموافقةُ فعلُ صاحبها** — تُقرأ هنا ولا تُكتب عن أحد. */}
          <p className="provenance-note">{t("team.consentIsPersonal")}</p>
          {member.consent_needs_recollection ? (
            <p className="error" data-testid={`team-member-consent-${member.id}`}>
              {t("team.consentUnverified")}
            </p>
          ) : (
            <p
              className={member.consent_state === "granted" ? "badge-ok" : "metric-label"}
              data-testid={`team-member-consent-${member.id}`}
            >
              {member.consent_label}
              {member.consent_method_label ? ` · ${member.consent_method_label}` : ""}
            </p>
          )}
          {member.consent_recorded_at ? (
            <p className="metric-label">
              {new Date(member.consent_recorded_at).toLocaleString(locale)}
            </p>
          ) : null}
        </section>
      ) : null}
    </TeamOverlay>
  );
}
