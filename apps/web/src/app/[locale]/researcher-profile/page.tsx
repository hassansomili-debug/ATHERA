"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";

/**
 * ملفي البحثي | Researcher Profile (الموجة الثانية، §12).
 *
 * **والمؤكَّدُ يختلف عن المرشَّح بغير اللون وحده.** المرشَّحات في قسمٍ
 * مستقلٍّ أسفل الملفّ، ولكلّ بطاقةٍ منها شارةٌ مكتوبةٌ تقول ما هي، وسطرٌ
 * صريحٌ يقول «ليس في ملفّك». فمن قرأ الشاشة بلا ألوان — أو قرأها قارئُ
 * شاشة — عرف الفرق كما يعرفه المبصر.
 *
 * **ولا نسبةَ جاهزيةٍ في هذه الشاشة ولا رقمَ يلخّص حال الباحث.**
 */

interface Profile {
  id: string;
  institution_ar: string | null;
  institution_en: string | null;
  college_ar: string | null;
  department_ar: string | null;
  current_rank: string | null;
  target_rank: string | null;
  primary_field_ar: string | null;
  country: string | null;
  orcid: string | null;
  orcid_status: "unverified" | "user_declared" | "externally_verified";
  preferred_working_language: "ar" | "en" | null;
  preferred_manuscript_language: "ar" | "en" | null;
  ai_response_language: "ar" | "en" | null;
}

interface Candidate {
  id: string;
  field_name: string;
  candidate_value: string;
  source_type: string;
  provenance: string | null;
  profile_state: string;
  status: string;
  in_active_profile: boolean;
  decided_at: string | null;
}

/** الحقولُ النصّية التي تُحرَّر هنا — والقائمةُ مغلقةٌ كما في الخادم. */
const TEXT_FIELDS = [
  ["institution_ar", "researcherProfile.institution"],
  ["college_ar", "researcherProfile.college"],
  ["department_ar", "researcherProfile.department"],
  ["current_rank", "researcherProfile.currentRank"],
  ["target_rank", "researcherProfile.targetRank"],
  ["primary_field_ar", "researcherProfile.primaryField"],
  ["country", "researcherProfile.country"],
  ["orcid", "researcherProfile.orcid"],
] as const;

/** حقولُ اللغة الثلاثة — **ولغةُ الواجهة ليست منها ولا تُحفظ هنا.** */
const LANGUAGE_FIELDS = [
  ["preferred_working_language", "researcherProfile.workingLanguage"],
  ["preferred_manuscript_language", "researcherProfile.manuscriptLanguage"],
  ["ai_response_language", "researcherProfile.aiResponseLanguage"],
] as const;

const ORCID_STATUS_KEYS: Record<string, string> = {
  unverified: "researcherProfile.statusUnverified",
  user_declared: "researcherProfile.statusUserDeclared",
  externally_verified: "researcherProfile.statusExternallyVerified",
};

const STATE_KEYS: Record<string, string> = {
  user_declared: "researcherProfile.stateUserDeclared",
  document_extracted: "researcherProfile.stateDocumentExtracted",
  confirmed: "researcherProfile.stateConfirmed",
  externally_verified: "researcherProfile.stateExternallyVerified",
  model_suggested: "researcherProfile.stateModelSuggested",
};

type Draft = Record<string, string>;

export default function ResearcherProfilePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [profile, setProfile] = useState<Profile | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [draft, setDraft] = useState<Draft>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [newField, setNewField] = useState<string>("institution_ar");
  const [newValue, setNewValue] = useState<string>("");
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const [me, pending] = await Promise.all([
        apiFetch<Profile>("/api/v1/researcher/profile", { locale }),
        apiFetch<Candidate[]>(
          "/api/v1/researcher/profile/candidates?candidate_status=proposed",
          { locale },
        ),
      ]);
      setProfile(me);
      setCandidates(pending);
      const next: Draft = {};
      for (const [field] of TEXT_FIELDS) next[field] = (me[field] ?? "") as string;
      for (const [field] of LANGUAGE_FIELDS) next[field] = (me[field] ?? "") as string;
      setDraft(next);
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusyId("profile");
    setSaved(false);
    setError(null);
    try {
      // **ولا تُرسل لغةُ الواجهة قط.** ما يُرسل هو ما في النموذج وحده،
      // و`locale` ليست منه — فتبديلُ لغة الشاشة لا يكتب في الملفّ شيئًا.
      const body: Record<string, string | null> = {};
      for (const [field] of [...TEXT_FIELDS, ...LANGUAGE_FIELDS]) {
        body[field] = draft[field] ? draft[field] : null;
      }
      await apiFetch("/api/v1/researcher/profile", {
        method: "PATCH",
        locale,
        body: JSON.stringify(body),
      });
      setSaved(true);
      await load();
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function decide(id: string, verdict: "confirm" | "reject") {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/researcher/profile/candidates/${id}/${verdict}`, {
        method: "POST",
        locale,
        body: JSON.stringify({ reason: reasons[id] || null }),
      });
      await load();
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function propose(event: React.FormEvent) {
    event.preventDefault();
    setBusyId("new-candidate");
    setError(null);
    try {
      await apiFetch("/api/v1/researcher/profile/candidates", {
        method: "POST",
        locale,
        body: JSON.stringify({ field_name: newField, candidate_value: newValue }),
      });
      setNewValue("");
      await load();
    } catch (err) {
      setError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("researcherProfile.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>
        {t("researcherProfile.subtitle")}
      </p>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {!loaded ? <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p> : null}

      {profile ? (
        <>
          <h2>{t("researcherProfile.identity")}</h2>
          <form className="form" onSubmit={(event) => void save(event)}>
            {TEXT_FIELDS.map(([field, label]) => (
              <div key={field}>
                <label htmlFor={`profile-${field}`}>{t(label)}</label>
                <input
                  id={`profile-${field}`}
                  value={draft[field] ?? ""}
                  onChange={(event) =>
                    setDraft({ ...draft, [field]: event.target.value })
                  }
                />
              </div>
            ))}

            <p className="provenance-note">{t("researcherProfile.orcidNote")}</p>
            <p className="metric-label">
              {t("researcherProfile.orcidStatus")}:{" "}
              <span className="chip chip-muted" data-testid="orcid-status">
                {t(ORCID_STATUS_KEYS[profile.orcid_status] ?? "common.none")}
              </span>
            </p>

            <h2>{t("researcherProfile.languages")}</h2>
            {/* §8 — أربعةُ مفاهيمَ لا واحد، وهذا السطرُ يقولها للباحث نفسه. */}
            <p className="provenance-note">{t("researcherProfile.languagesNote")}</p>
            {LANGUAGE_FIELDS.map(([field, label]) => (
              <div key={field}>
                <label htmlFor={`profile-${field}`}>{t(label)}</label>
                <select
                  id={`profile-${field}`}
                  value={draft[field] ?? ""}
                  onChange={(event) =>
                    setDraft({ ...draft, [field]: event.target.value })
                  }
                >
                  <option value="">{t("researcherProfile.unset")}</option>
                  <option value="ar">{t("researcherProfile.arabic")}</option>
                  <option value="en">{t("researcherProfile.english")}</option>
                </select>
              </div>
            ))}

            <div className="actions">
              <button type="submit" disabled={busyId === "profile"}>
                {t("researcherProfile.save")}
              </button>
              {saved ? (
                <span className="chip chip-ok">{t("researcherProfile.saved")}</span>
              ) : null}
            </div>
          </form>
        </>
      ) : null}

      {/* ── المرشَّحات: قسمٌ منفصلٌ بموضعه، لا صفٌّ ملوَّنٌ بين الحقول ── */}
      <h2>{t("researcherProfile.candidates")}</h2>
      <p className="provenance-note">{t("researcherProfile.candidatesNote")}</p>
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : candidates.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("researcherProfile.candidatesEmpty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {candidates.map((candidate) => (
          <article className="card" key={candidate.id} data-testid="profile-candidate">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <span className="chip chip-candidate" data-state="candidate">
                {t(STATE_KEYS[candidate.profile_state] ?? "common.none")}
              </span>
              {/* الحقيقةُ الحاسمة مكتوبةٌ نصًّا، لا مرموزةٌ بلون. */}
              <span className="chip chip-warn">
                {candidate.in_active_profile
                  ? t("researcherProfile.inProfile")
                  : t("researcherProfile.notInProfile")}
              </span>
            </div>
            <p className="metric-label">{candidate.field_name}</p>
            <p style={{ fontWeight: 600, marginBlock: 4 }}>{candidate.candidate_value}</p>
            <p className="provenance-note">{t("researcherProfile.candidateBadge")}</p>
            {candidate.provenance ? (
              <p className="metric-label">
                {t("researcherProfile.provenance")}: {candidate.provenance}
              </p>
            ) : null}

            <label className="sr-only" htmlFor={`reason-${candidate.id}`}>
              {t("researcherProfile.reasonLabel")} — {candidate.candidate_value}
            </label>
            <input
              id={`reason-${candidate.id}`}
              value={reasons[candidate.id] ?? ""}
              onChange={(event) =>
                setReasons({ ...reasons, [candidate.id]: event.target.value })
              }
            />

            <div className="actions">
              <button
                type="button"
                disabled={busyId === candidate.id}
                onClick={() => void decide(candidate.id, "confirm")}
              >
                {t("researcherProfile.confirm")}
              </button>
              <button
                type="button"
                disabled={busyId === candidate.id}
                onClick={() => void decide(candidate.id, "reject")}
              >
                {t("researcherProfile.reject")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <h2>{t("researcherProfile.addTitle")}</h2>
      <form className="form" onSubmit={(event) => void propose(event)}>
        <div>
          <label htmlFor="new-candidate-field">{t("researcherProfile.fieldLabel")}</label>
          <select
            id="new-candidate-field"
            value={newField}
            onChange={(event) => setNewField(event.target.value)}
          >
            {TEXT_FIELDS.map(([field, label]) => (
              <option value={field} key={field}>
                {t(label)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="new-candidate-value">{t("researcherProfile.valueLabel")}</label>
          <input
            id="new-candidate-value"
            value={newValue}
            onChange={(event) => setNewValue(event.target.value)}
          />
        </div>
        <div className="actions">
          <button type="submit" disabled={busyId === "new-candidate" || !newValue.trim()}>
            {t("researcherProfile.addCta")}
          </button>
        </div>
      </form>

      {/* **ويُقال تأجيلُها حين تُلمس** (§13) — فلا يُقرأ الغيابُ عطبًا. */}
      <p className="provenance-note">{t("researcherProfile.deferredNote")}</p>
    </>
  );
}
