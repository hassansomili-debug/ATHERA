"use client";

import { use, useEffect, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

interface Profile {
  institution: string | null;
  current_rank: string | null;
  target_rank: string | null;
  primary_field: string | null;
  orcid: string | null;
  g0_approved_at: string | null;
  verified_memory_count: number;
}

export default function ProfilePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  // **الشرطة كانت تُعرض قبل الجواب.** بطاقة «معلومات موثّقة» تُصيَّر دائمًا،
  // وقيمتها `profile?.verified_memory_count ?? "—"` — فيقرأ الباحث «—» على
  // أنها الحال: لا معلومات. وهي في الحقيقة «لم يُسأل بعد».
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiFetch<Profile>("/api/v1/profile", { locale })
      .then(setProfile)
      .catch((err) =>
        setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed")),
      )
      // في دالّة رد نداء لا في جسم التأثير — `react-hooks/set-state-in-effect`.
      .finally(() => setLoaded(true));
  }, [locale, t]);

  const rows: Array<[string, string | null]> = profile
    ? [
        [t("profile.institution"), profile.institution],
        [t("profile.currentRank"), profile.current_rank],
        [t("profile.targetRank"), profile.target_rank],
        [t("profile.primaryField"), profile.primary_field],
        [t("profile.orcid"), profile.orcid],
      ]
    : [];

  return (
    <>
      <h1>{t("profile.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("profile.subtitle")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p> : null}

      {/* البطاقات لا تُصيَّر قبل الجواب: بطاقةُ رقمٍ محلّه «—» تُقرأ حكمًا. */}
      {profile ? (
        <section className="grid">
          {rows.map(([label, value]) => (
            <article className="card" key={label}>
              <div className="metric-label">{label}</div>
              <div style={{ fontWeight: 600 }}>{value ?? "—"}</div>
            </article>
          ))}
          <article className="card">
            <div className="metric-label">{t("profile.verifiedFacts")}</div>
            <div className="metric-value">{profile.verified_memory_count}</div>
          </article>
        </section>
      ) : null}

      {profile && !profile.g0_approved_at ? (
        <p className="provenance-note">G0 — {t("profile.notApproved")}</p>
      ) : null}
    </>
  );
}
