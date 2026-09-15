"use client";

import { use, useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { AtheraApiError } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import {
  type PublicOpportunity,
  applyToOpportunity,
  myApplications,
  opportunityDetail,
} from "@/lib/recruitment";

/**
 * تفصيلُ فرصةٍ بحثية، والتقدّمُ إليها (RC-T1C).
 *
 * **وما يُعرض هو ما يردّه الخادم في إسقاطه العامّ**: لا معرّفَ بحث، ولا
 * مؤسسة، ولا عنوانَ البحث الخاصّ، ولا اسمَ مديره. والخادمُ لا يردّ تلك
 * الأعمدةَ أصلًا — الجدولُ العامُّ يخلو منها بنيويًّا (RC-T1B) — فلا
 * تُنسى في شاشةٍ تُكتب غدًا.
 *
 * **وحقلُ الرسالة وحده في V1.** لا سيرةً ذاتية، ولا مرفقات، ولا أجرًا،
 * ولا تاريخَ عملٍ، ولا درجةً يحسبها نموذج. وترتيبُ المتقدّمين بذكاءٍ
 * آليّ قرارٌ لم يُتّخذ، فلا تُبنى له خانةٌ اليوم.
 *
 * **والحدُّ الأخيرُ للتكرار في القاعدة** — فهرسٌ فريدٌ على الطلبات
 * الحيّة. وتعطيلُ الزرّ بعد النجاح تحسينُ عرضٍ لا ضمانة: نقرتان
 * متسابقتان تصلان معًا، والقاعدةُ ترفض الثانية.
 */
export default function OpportunityDetailPage({
  params,
}: {
  params: Promise<{ locale: string; opportunityId: string }>;
}) {
  const { locale: raw, opportunityId } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [row, setRow] = useState<PublicOpportunity | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [applied, setApplied] = useState(false);
  const [alreadyOpen, setAlreadyOpen] = useState(false);

  const say = useCallback(
    (err: unknown) => {
      if (err instanceof AtheraApiError && err.status === 404) {
        setError(t("collaborationOpportunities.detailNotFound"));
        return;
      }
      setError(
        err instanceof AtheraApiError
          ? err.localized(locale)
          : t("collaborationOpportunities.loadFailed"),
      );
    },
    [locale, t],
  );

  useEffect(() => {
    opportunityDetail(locale, opportunityId)
      .then(setRow)
      .catch(say)
      .finally(() => setLoaded(true));
    // **ولا يُعرض زرُّ تقدّمٍ لمن له طلبٌ حيّ** — والقاعدةُ ترفضه بـ٤٠٩،
    // لكنّ عرضَه يجعل الباحثَ يحاول ثمّ يُردّ.
    myApplications(locale)
      .then((rows) =>
        setAlreadyOpen(
          rows.some(
            (item) =>
              item.opportunity_id === opportunityId &&
              !["withdrawn", "declined"].includes(item.status),
          ),
        ),
      )
      .catch(() => setAlreadyOpen(false));
  }, [locale, opportunityId, say]);

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      await applyToOpportunity(locale, opportunityId, message);
      setApplied(true);
      setMessage("");
      setAlreadyOpen(true);
    } catch (err) {
      if (err instanceof AtheraApiError && err.status === 409) {
        setError(t("collaborationOpportunities.alreadyApplied"));
        setAlreadyOpen(true);
      } else {
        say(err);
      }
    } finally {
      setBusy(false);
    }
  }

  const open = row?.effective_status === "open";

  return (
    <>
      <p style={{ marginBlockEnd: 4 }}>
        <Link href={`/${locale}/collaboration-opportunities`}>
          {t("collaborationOpportunities.backToList")}
        </Link>
      </p>
      <h1 style={{ marginBlockStart: 0 }}>
        {row?.title ?? (loaded ? t("collaborationOpportunities.detailNotFound") : t("app.loading"))}
      </h1>
      {error ? <p className="error">{error}</p> : null}
      {applied ? (
        <p className="badge-ok" data-testid="apply-confirmed">
          {t("collaborationOpportunities.applied")}
        </p>
      ) : null}

      {row ? (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlock: 10 }}>
            <span className="chip chip-stage" data-testid="detail-status">
              {t(`collaborationOpportunities.${row.effective_status}`) ===
              `collaborationOpportunities.${row.effective_status}`
                ? row.effective_status
                : t(`collaborationOpportunities.${row.effective_status}`)}
            </span>
            {row.public_label ? <span className="chip chip-muted">{row.public_label}</span> : null}
            <span className="chip chip-muted">
              {t("collaborationOpportunities.openings")}: {row.openings_count}
            </span>
            <span className="chip chip-muted">
              {t("collaborationOpportunities.collaborationType")}: {row.collaboration_type}
            </span>
            {row.specialization ? (
              <span className="chip chip-muted">
                {t("collaborationOpportunities.specialization")}: {row.specialization}
              </span>
            ) : null}
            {row.starts_at ? (
              <span className="chip chip-muted">
                {t("collaborationOpportunities.startsAt")}:{" "}
                {new Date(row.starts_at).toLocaleString(locale)}
              </span>
            ) : null}
            {row.ends_at ? (
              <span className="chip chip-muted">
                {t("collaborationOpportunities.closesAt")}:{" "}
                {new Date(row.ends_at).toLocaleString(locale)}
              </span>
            ) : null}
          </div>

          <h2>{t("collaborationOpportunities.description")}</h2>
          <p>{row.description}</p>

          {row.contributions ? (
            <>
              <h2>{t("collaborationOpportunities.contributions")}</h2>
              <p>{row.contributions}</p>
            </>
          ) : null}
          {row.requirements ? (
            <>
              <h2>{t("collaborationOpportunities.requirements")}</h2>
              <p>{row.requirements}</p>
            </>
          ) : null}

          <article className="card" style={{ marginBlockStart: 12 }}>
            <strong>{t("collaborationOpportunities.apply")}</strong>
            {!open ? (
              <p style={{ color: "var(--muted)" }} data-testid="apply-closed">
                {t("collaborationOpportunities.notOpen")}
              </p>
            ) : alreadyOpen ? (
              <p style={{ color: "var(--muted)" }} data-testid="apply-existing">
                {t("collaborationOpportunities.alreadyApplied")}
              </p>
            ) : (
              <>
                <label htmlFor="apply-message" style={{ display: "block", marginBlockStart: 8 }}>
                  {t("collaborationOpportunities.messageLabel")}
                  <textarea
                    id="apply-message"
                    rows={4}
                    data-testid="apply-message"
                    style={{ display: "block", inlineSize: "100%", marginBlockStart: 4 }}
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                  />
                  <span className="metric-label">
                    {t("collaborationOpportunities.messageHint")}
                  </span>
                </label>
                <button
                  type="button"
                  style={{ marginBlockStart: 8 }}
                  data-testid="apply-submit"
                  disabled={busy}
                  onClick={() => void apply()}
                >
                  {busy
                    ? t("collaborationOpportunities.applying")
                    : t("collaborationOpportunities.apply")}
                </button>
              </>
            )}
          </article>
        </>
      ) : null}
    </>
  );
}
