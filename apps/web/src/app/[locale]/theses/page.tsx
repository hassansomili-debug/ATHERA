"use client";

import Link from "next/link";
import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { ThesisIntake } from "@/components/ThesisIntake";

/**
 * مكتبة الرسائل (§23).
 *
 * «أساس حق الاستخدام» يُعرض بوصفه ادعاءً سجّله الباحث، لا اعتمادًا: الاعتماد
 * قرار مستقل عند بوابة GT1 (§23.2 مقابل §23.9). الخلط بينهما هو ما يجعل
 * منصةً تظن أنها حصلت على الحقوق لأن أحدهم كتب أنه يملكها.
 */
interface Thesis {
  id: string;
  // `null` تعني «لم يُستخرَج بعد» — ولا تُملأ باسم ملف ولا بتخمين.
  title: string | null;
  degree: string | null;
  processing_status: string | null;
  defended_on: string | null;
  data_collected_on: string | null;
  rights_basis: string | null;
  parsed_at: string | null;
  sections_extracted: number;
  opportunities_found: number;
}

export default function ThesesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [theses, setTheses] = useState<Thesis[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [titleAr, setTitleAr] = useState("");
  const [titleEn, setTitleEn] = useState("");
  const [degree, setDegree] = useState("masters");
  const [defendedOn, setDefendedOn] = useState("");
  const [dataCollectedOn, setDataCollectedOn] = useState("");
  const [institutionAr, setInstitutionAr] = useState("");
  const [rightsBasis, setRightsBasis] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [supervisorName, setSupervisorName] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // **«لا رسائل مسجّلة» بعد رفعٍ ناجح رسالةٌ تُفزع.** القائمة تبدأ فارغة،
  // فكانت تُقال قبل عودة الطلب — ومن رفع رسالته للتوّ يقرأ أنها ليست هناك.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setTheses(await apiFetch<Thesis[]>("/api/v1/theses", { locale }));
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  /** خانة فارغة تُرسل `null` لا سلسلة فارغة: العقد يميّز «غير مذكور» عن «فارغ». */
  function orNull(value: string): string | null {
    return value.trim() === "" ? null : value.trim();
  }

  async function onRegister(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await apiFetch("/api/v1/theses", {
        method: "POST",
        locale,
        body: JSON.stringify({
          title_ar: titleAr.trim(),
          title_en: orNull(titleEn),
          degree,
          defended_on: orNull(defendedOn),
          data_collected_on: orNull(dataCollectedOn),
          institution_ar: orNull(institutionAr),
          // §23.2 — الأساس ادعاء يُسجَّل، والاعتماد قرار مستقل عند GT1.
          rights_basis: orNull(rightsBasis),
          owner_name: orNull(ownerName),
          supervisor_name: orNull(supervisorName),
        }),
      });
      setTitleAr("");
      setTitleEn("");
      setDefendedOn("");
      setDataCollectedOn("");
      setInstitutionAr("");
      setRightsBasis("");
      setOwnerName("");
      setSupervisorName("");
      await load();
    } catch (err) {
      setFormError(
        err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"),
      );
    } finally {
      setSaving(false);
    }
  }

  async function run(id: string, action: "parse" | "mine-opportunities") {
    setBusyId(id);
    setError(null);
    try {
      await apiFetch(`/api/v1/theses/${id}/${action}`, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("theses.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("theses.subtitle")}</p>
      {/* الرفع أولًا: الباحث يرفع رسالته فتُقرأ — لا يملأ نموذجًا عنها. */}
      <div style={{ marginBlock: "18px 24px" }}>
        <ThesisIntake locale={locale} messages={getMessages(locale)} />
      </div>
      <p className="provenance-note">{t("theses.rightsNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : theses.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("theses.empty")}</p>
      ) : null}

      <div style={{ display: "grid", gap: 8 }}>
        {theses.map((thesis) => (
          <article className="card" key={thesis.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>
                {thesis.title ?? (
                  <span style={{ color: "var(--muted)", fontWeight: 400 }}>
                    {t("theses.noTitleYet")}
                  </span>
                )}
              </strong>
              <span className="metric-label">
                {t("theses.degree")}:{" "}
                {thesis.degree === null
                  ? t("theses.noDegreeYet")
                  : t(`theses.${thesis.degree === "phd" ? "phd" : "masters"}`)}
              </span>
            </div>

            <div className="metric-label" style={{ marginBlockStart: 6 }}>
              {t("theses.rightsBasis")}:{" "}
              {thesis.rights_basis ? t(`theses.basis.${thesis.rights_basis}`) : t("theses.noRights")}
              {thesis.defended_on ? ` · ${t("theses.defended")}: ${thesis.defended_on}` : ""}
            </div>

            <div className="metric-label">
              {t("theses.sections")}: {thesis.sections_extracted} ·{" "}
              {t("theses.opportunities")}: {thesis.opportunities_found}
            </div>

            <div style={{ display: "flex", gap: 8, marginBlockStart: 12, flexWrap: "wrap" }}>
              {thesis.processing_status ? (
                <Link
                  href={`/${locale}/theses/${thesis.id}/review`}
                  style={{
                    padding: "8px 16px", borderRadius: "var(--radius)",
                    background: "var(--athera-teal)", color: "#fff", textDecoration: "none",
                  }}
                >
                  {t("theses.reviewCta")}
                </Link>
              ) : null}
              <button
                type="button"
                onClick={() => run(thesis.id, "parse")}
                disabled={busyId === thesis.id}
                style={{
                  padding: "8px 16px", border: "1px solid var(--border)",
                  borderRadius: "var(--radius)", background: "transparent",
                  color: "inherit", font: "inherit", cursor: "pointer",
                }}
              >
                {t("theses.parse")}
              </button>
              <button
                type="button"
                onClick={() => run(thesis.id, "mine-opportunities")}
                disabled={busyId === thesis.id || !thesis.parsed_at}
                style={{
                  padding: "8px 16px", border: "none", borderRadius: "var(--radius)",
                  background: "var(--athera-teal)", color: "#fff", font: "inherit",
                  cursor: thesis.parsed_at ? "pointer" : "not-allowed",
                  opacity: thesis.parsed_at ? 1 : 0.5,
                }}
              >
                {t("theses.mine")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <h2 style={{ marginBlockStart: "calc(var(--space) * 1.5)", fontSize: 18 }}>
        {t("theses.addTitle")}
      </h2>
      <form className="form" onSubmit={onRegister}>
        <label>
          {t("theses.addTitleAr")}
          <input value={titleAr} onChange={(e) => setTitleAr(e.target.value)} required minLength={3} />
        </label>
        <label>
          {t("theses.addTitleEn")}
          <input value={titleEn} onChange={(e) => setTitleEn(e.target.value)} />
        </label>
        <label>
          {t("theses.addDegree")}
          <select value={degree} onChange={(e) => setDegree(e.target.value)}>
            <option value="masters">{t("theses.masters")}</option>
            <option value="phd">{t("theses.phd")}</option>
          </select>
        </label>
        <label>
          {t("theses.addDefendedOn")}
          <input type="date" value={defendedOn} onChange={(e) => setDefendedOn(e.target.value)} />
        </label>
        <label>
          {t("theses.addDataCollectedOn")}
          <input
            type="date"
            value={dataCollectedOn}
            onChange={(e) => setDataCollectedOn(e.target.value)}
          />
        </label>
        <label>
          {t("theses.addInstitution")}
          <input value={institutionAr} onChange={(e) => setInstitutionAr(e.target.value)} />
        </label>
        <label>
          {t("theses.addRightsBasis")}
          <select value={rightsBasis} onChange={(e) => setRightsBasis(e.target.value)}>
            <option value="">{t("theses.noRights")}</option>
            <option value="thesis_owner">{t("theses.basis.thesis_owner")}</option>
            <option value="supervisor_with_consent">
              {t("theses.basis.supervisor_with_consent")}
            </option>
            <option value="institution_policy">{t("theses.basis.institution_policy")}</option>
          </select>
        </label>
        <label>
          {t("theses.addOwner")}
          <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} />
        </label>
        <label>
          {t("theses.addSupervisor")}
          <input value={supervisorName} onChange={(e) => setSupervisorName(e.target.value)} />
        </label>
        {formError ? <p className="error">{formError}</p> : null}
        <button type="submit" disabled={saving}>
          {saving ? t("app.loading") : t("theses.addSubmit")}
        </button>
      </form>
      <p className="provenance-note">{t("theses.addNote")}</p>
    </>
  );
}
