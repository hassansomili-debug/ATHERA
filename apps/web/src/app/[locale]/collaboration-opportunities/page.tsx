"use client";

import { use, useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { InvitationAcceptPanel } from "@/components/InvitationAcceptPanel";
import {
  type MyApplication,
  type PublicOpportunity,
  discoverOpportunities,
  myApplications,
  withdrawApplication,
} from "@/lib/recruitment";

/**
 * الفرصُ البحثية — **اكتشافُ تعاونٍ على أبحاثٍ قائمة** (RC-T1C).
 *
 * ## ولمَ ليس المسار `/{locale}/opportunities`
 *
 * لأنّ ذاك مأخوذٌ ومعناه آخر: هو **خريطةُ فرص النشر** — جاهزيةُ ورقةٍ
 * مقترحةٍ وتداخلُها وبوابةُ حقوقها. وثلاثةُ أشياء في هذه المنصّة تحمل
 * كلمةَ «فرصة»:
 *
 *   فرصةُ نشرٍ    ورقةٌ مقترحةٌ من رسالةٍ أو فجوة — علمٌ.
 *   فرصةٌ بحثيةٌ  فجوةٌ تستحقّ بحثًا — علمٌ أيضًا.
 *   **دعوةُ تعاونٍ على بحثٍ قائم** — وهي هذه الصفحة.
 *
 * فلو سُمّيت هذه `opportunities` لَدهست خريطةَ النشر أو اختلطت بها،
 * والباحثُ يفتح رابطًا يعرفه فيجد شيئًا آخر. **والاسمُ المعروضُ يبقى
 * «الفرص البحثية»**: الالتباسُ يُحلّ في المسار لا في اللغة.
 *
 * ## ولا لغةَ توظيف
 *
 * لا «وظائف»، ولا «رواتب»، ولا «سيرة ذاتية»، ولا «تقييمُ مرشَّح». ومن
 * يُقبل يصير عضوًا في فريقِ بحثٍ بصلاحياتٍ صريحة — لا موظَّفًا.
 *
 * ## وثلاثُ حالاتٍ لا تُطوى في واحدة
 *
 * **يُحمَّل**، و**لا فرصَ متاحة**، و**فشل التحميل**. وعرضُ «لا فرص» قبل
 * عودة الطلب أسوأُ من رسالة خطأ: يقرؤها الباحثُ حكمًا ويمضي.
 */
type Tab = "discover" | "mine";

function statusLabel(t: (k: string) => string, status: string): string {
  const label = t(`collaborationOpportunities.${status}`);
  return label === `collaborationOpportunities.${status}` ? status : label;
}

export default function CollaborationOpportunitiesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [tab, setTab] = useState<Tab>("discover");
  const [rows, setRows] = useState<PublicOpportunity[]>([]);
  const [mine, setMine] = useState<MyApplication[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [mineLoaded, setMineLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const say = useCallback(
    (err: unknown) =>
      setError(
        err instanceof AtheraApiError
          ? err.localized(locale)
          : t("collaborationOpportunities.loadFailed"),
      ),
    [locale, t],
  );

  const reloadMine = useCallback(() => {
    myApplications(locale)
      .then(setMine)
      .catch(say)
      .finally(() => setMineLoaded(true));
  }, [locale, say]);

  useEffect(() => {
    discoverOpportunities(locale)
      .then(setRows)
      .catch(say)
      .finally(() => setLoaded(true));
    myApplications(locale)
      .then(setMine)
      .catch(say)
      .finally(() => setMineLoaded(true));
  }, [locale, say]);

  async function withdraw(applicationId: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await withdrawApplication(locale, applicationId);
      setNotice(t("collaborationOpportunities.withdrawn"));
      reloadMine();
    } catch (err) {
      say(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>{t("collaborationOpportunities.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>
        {t("collaborationOpportunities.subtitle")}
      </p>
      <p className="provenance-note">{t("collaborationOpportunities.domainNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p className="badge-ok">{notice}</p> : null}

      {/* التبويبان — **دلالةٌ مفهومةٌ لقارئ الشاشة**، لا لونًا وحده. */}
      <nav aria-label={t("collaborationOpportunities.title")} style={{ marginBlock: "var(--space)" }}>
        <ul style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
          {(["discover", "mine"] as const).map((key) => (
            <li key={key}>
              <button
                type="button"
                className={tab === key ? "chip chip-stage" : "chip chip-muted"}
                aria-current={tab === key ? "page" : undefined}
                data-testid={`collab-tab-${key}`}
                onClick={() => setTab(key)}
              >
                {t(
                  key === "discover"
                    ? "collaborationOpportunities.tabDiscover"
                    : "collaborationOpportunities.tabMine",
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {tab === "discover" ? (
        <section aria-label={t("collaborationOpportunities.tabDiscover")}>
          {!loaded ? (
            <p data-testid="collab-loading" style={{ color: "var(--muted)" }}>
              {t("collaborationOpportunities.loading")}
            </p>
          ) : rows.length === 0 && !error ? (
            <p data-testid="collab-empty" style={{ color: "var(--muted)" }}>
              {t("collaborationOpportunities.empty")}
            </p>
          ) : null}
          <div style={{ display: "grid", gap: 8 }}>
            {rows.map((row) => (
              <article
                className="card"
                key={row.opportunity_id}
                data-testid={`collab-card-${row.opportunity_id}`}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  {/* **العنوانُ هو المدخل** — ولا يُنسخ معرّف. */}
                  <Link href={`/${locale}/collaboration-opportunities/${row.opportunity_id}`}>
                    <strong>{row.title}</strong>
                  </Link>
                  <span className="chip chip-stage">{statusLabel(t, row.effective_status)}</span>
                </div>
                {/* **ولا معرّفَ بحثٍ ولا مؤسسةٍ ولا اسمَ مديرٍ هنا** —
                    والخادمُ لا يردّها أصلًا: الإسقاطُ العامّ في RC-T1B
                    يخلو من الأعمدة نفسِها، فلا تُنسى في شاشة. */}
                <p style={{ marginBlock: 6 }}>{row.description}</p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {row.public_label ? (
                    <span className="chip chip-muted">{row.public_label}</span>
                  ) : null}
                  {row.specialization ? (
                    <span className="chip chip-muted">
                      {t("collaborationOpportunities.specialization")}: {row.specialization}
                    </span>
                  ) : null}
                  <span className="chip chip-muted">
                    {t("collaborationOpportunities.collaborationType")}: {row.collaboration_type}
                  </span>
                  <span className="chip chip-muted">
                    {t("collaborationOpportunities.openings")}: {row.openings_count}
                  </span>
                  {row.ends_at ? (
                    <span className="chip chip-muted">
                      {t("collaborationOpportunities.closesAt")}:{" "}
                      {new Date(row.ends_at).toLocaleDateString(locale)}
                    </span>
                  ) : null}
                </div>
                <p style={{ marginBlockStart: 10 }}>
                  <Link
                    className="chip chip-stage"
                    href={`/${locale}/collaboration-opportunities/${row.opportunity_id}`}
                    data-testid={`collab-open-${row.opportunity_id}`}
                  >
                    {t("collaborationOpportunities.openDetail")}
                  </Link>
                </p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "mine" ? (
        <section aria-label={t("collaborationOpportunities.tabMine")} data-testid="collab-mine">
          <p className="provenance-note">{t("collaborationOpportunities.statusNote")}</p>
          {!mineLoaded ? (
            <p style={{ color: "var(--muted)" }}>{t("collaborationOpportunities.loading")}</p>
          ) : mine.length === 0 && !error ? (
            <p style={{ color: "var(--muted)" }}>
              {t("collaborationOpportunities.emptyApplications")}
            </p>
          ) : null}
          <div style={{ display: "grid", gap: 8 }}>
            {mine.map((application) => (
              <article
                className="card"
                key={application.application_id}
                data-testid={`application-${application.application_id}`}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <strong>{application.title}</strong>
                  <span
                    className="chip chip-stage"
                    data-testid={`application-status-${application.application_id}`}
                  >
                    {t(`recruitment.applicationStatus.${application.status}`)}
                  </span>
                </div>
                {application.message ? (
                  <p style={{ marginBlock: 4 }}>{application.message}</p>
                ) : null}
                <p className="metric-label">
                  {t("collaborationOpportunities.submittedAt")}:{" "}
                  {new Date(application.submitted_at).toLocaleString(locale)}
                </p>

                {/* **و«مدعوّ» لا يعني «دعوةٌ قابلةٌ للاستعمال».**
                    حالُ الطلب وحالُ الدعوة حقيقتان منفصلتان: الطلبُ
                    يبقى «مدعوًّا» بعد انتهاء الدعوة، والخلطُ بينهما
                    يجعل المرشَّحَ ينتظر بابًا أُغلق. */}
                {application.invitation ? (
                  <div
                    className="card"
                    style={{ marginBlockStart: 8 }}
                    data-testid={`invitation-${application.application_id}`}
                  >
                    <strong>{t("collaborationOpportunities.invitationTitle")}</strong>
                    <p className="metric-label">
                      {t(`recruitment.invitationState.${application.invitation.state}`)} ·{" "}
                      <span
                        className={application.invitation.usable ? "badge-ok" : "metric-label"}
                        data-testid={`invitation-usable-${application.application_id}`}
                      >
                        {application.invitation.usable
                          ? t("collaborationOpportunities.invitationUsable")
                          : t("collaborationOpportunities.invitationUnusable")}
                      </span>
                    </p>
                    <p className="metric-label">
                      {t("collaborationOpportunities.invitationExpires")}:{" "}
                      {new Date(application.invitation.expires_at).toLocaleString(locale)}
                    </p>
                    {application.invitation.membership_created ? (
                      <p className="badge-ok" data-testid={`membership-${application.application_id}`}>
                        {t("collaborationOpportunities.membershipCreated")}
                      </p>
                    ) : null}
                    {/* **ولا مسارَ يُرجع الرمز.** المرشَّحُ يُدخل ما وصله
                        بيد إنسان — انظر `InvitationAcceptPanel`. */}
                    {application.invitation.usable ? (
                      <InvitationAcceptPanel
                        locale={locale}
                        title={t("collaborationOpportunities.invitationTitle")}
                        onAccepted={() => reloadMine()}
                      />
                    ) : null}
                    {application.invitation.membership_created ? (
                      <p style={{ marginBlockStart: 8 }}>
                        <Link className="chip chip-stage" href={`/${locale}/portfolio`}>
                          {t("collaborationOpportunities.openProject")}
                        </Link>
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {/* **المتقدّمُ يسحب، والمديرُ يُلغي.** */}
                {application.status === "pending" || application.status === "shortlisted" ||
                application.status === "invited" ? (
                  <>
                    <p className="provenance-note">
                      {t("collaborationOpportunities.withdrawNote")}
                    </p>
                    <button
                      type="button"
                      className="chip chip-muted"
                      disabled={busy}
                      data-testid={`application-withdraw-${application.application_id}`}
                      onClick={() => void withdraw(application.application_id)}
                    >
                      {t("collaborationOpportunities.withdraw")}
                    </button>
                  </>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
