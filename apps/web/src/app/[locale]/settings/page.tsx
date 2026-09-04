"use client";

import { use, useCallback, useState } from "react";

import { AtheraApiError, apiFetch } from "@/lib/api";
import { ChangePassword } from "@/components/ChangePassword";
import { useDeferredLoad } from "@/lib/useDeferredLoad";
import { DEFAULT_LOCALE, getMessages, isLocale, translator } from "@/lib/i18n";
import { ContextLinks } from "@/components/ContextLinks";

/**
 * الإعدادات ووضع التشغيل (§26.4، §32، §36).
 *
 * هذه الشاشة تُفصح ولا تُغيّر: الإعداد يقع في البيئة لا في المتصفح. والسبب
 * أن أخطر التباس في منصة كهذه أن يظن المستخدم أن النظام «فكّر» بينما هو
 * يعمل بقواعد حتمية، أو أنه بحث في سجل خارجي بينما هو معزول عن الشبكة.
 *
 * ولا يُعرض مفتاح: تُعرض حالته فقط.
 */
interface PostureItem {
  key: string;
  label: string;
  value: string;
  detail: string;
}

interface Posture {
  tenant_name: string;
  locale: string;
  supported_locales: string[];
  roles: string[];
  items: PostureItem[];
}

interface Notification {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string;
}

/** الحساب: ما يخص هوية الباحث وذاكرته الموثقة. */
const ACCOUNT_LINKS = [
  { key: "nav.profile", path: "profile", hint: "settings.profileHint" },
  { key: "nav.facts", path: "facts", hint: "settings.factsHint" },
  { key: "nav.memory", path: "memory", hint: "settings.memoryHint" },
  { key: "nav.agents", path: "agents", hint: "settings.agentsHint" },
];

/**
 * متقدّم — الشفافية والإدارة.
 *
 * سجل التشغيل وسجل التدقيق لا يظهران لباحث عادي: هما يصفان تنفيذ النظام
 * لا عمل الباحث. ويُعرضان لمن يحمل دورًا إداريًا وحده — والدور يُقرأ من
 * `/settings/posture`، أي من الخادم لا من ظنّ الواجهة. والمساران يبقيان
 * عاملين لمن يعرفهما بأي حال؛ الإخفاء تنظيمُ عرضٍ لا حاجزُ صلاحية،
 * والحاجز الحقيقي في الخادم حيث RBAC وRLS.
 */
const ADVANCED_LINKS = [
  { key: "nav.traces", path: "traces", hint: "settings.tracesHint" },
  { key: "nav.audit", path: "audit", hint: "settings.auditHint" },
];

const ADMIN_ROLES = new Set([
  "research_admin", "college_admin", "institution_admin", "system_admin",
]);

export default function SettingsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = use(params);
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  const t = translator(getMessages(locale));

  const [posture, setPosture] = useState<Posture | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  // «لا إشعارات» كانت تُعرض قبل عودة الطلب، ووضعُ التشغيل يبقى بلا أثرٍ
  // على الشاشة إطلاقًا ريثما يصل — فراغٌ صامت لا يُفرَّق فيه بين انتظارٍ
  // وخلوّ.
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const [state, notes] = await Promise.all([
        apiFetch<Posture>("/api/v1/settings/posture", { locale }),
        apiFetch<Notification[]>("/api/v1/notifications", { locale }),
      ]);
      setPosture(state);
      setNotifications(notes);
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setLoaded(true);
    }
  }, [locale, t]);

  useDeferredLoad(load);

  async function markRead(id: string) {
    setBusyId(id);
    try {
      await apiFetch(`/api/v1/notifications/${id}/read`, { method: "POST", locale });
      await load();
    } catch (err) {
      setError(err instanceof AtheraApiError ? err.localized(locale) : t("common.loadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>{t("settings.title")}</h1>
      <p style={{ color: "var(--muted)", marginBlockStart: 0 }}>{t("settings.subtitle")}</p>
      <p className="provenance-note">{t("settings.readOnlyNote")}</p>
      {error ? <p className="error">{error}</p> : null}
      {!loaded ? <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p> : null}

      {posture ? (
        <>
          <p className="metric-label">
            {t("settings.tenant")}: <strong>{posture.tenant_name}</strong> ·{" "}
            {t("settings.roles")}: {posture.roles.join("، ") || "—"} ·{" "}
            {t("common.language")}: {posture.supported_locales.join(" / ")}
          </p>

          <div style={{ display: "grid", gap: 8 }}>
            {posture.items.map((item) => (
              <article className="card" key={item.key}>
                <div
                  style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}
                >
                  <strong>{item.label}</strong>
                  <code>{item.value}</code>
                </div>
                <p style={{ color: "var(--muted)", marginBlock: 4 }}>{item.detail}</p>
              </article>
            ))}
          </div>
        </>
      ) : null}

      {/* الحساب أوّلًا: تغييرُ الكلمة فعلٌ يخصّ الباحث، لا إعدادَ نظام. */}
      <h2>{t("settings.changePassword")}</h2>
      <ChangePassword locale={locale} messages={getMessages(locale)} />

      <h2>{t("settings.notifications")}</h2>
      {!loaded ? (
        <p style={{ color: "var(--muted)" }}>{t("app.loading")}</p>
      ) : notifications.length === 0 && !error ? (
        <p style={{ color: "var(--muted)" }}>{t("settings.emptyNotifications")}</p>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {notifications.map((note) => (
          <article className="card" key={note.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{note.title}</strong>
              <span className="metric-label">
                {new Date(note.created_at).toLocaleString(locale)}
              </span>
            </div>
            {note.body ? <p style={{ marginBlock: 4 }}>{note.body}</p> : null}
            {note.read_at ? (
              <span className="metric-label">{t("settings.read")}</span>
            ) : (
              <button
                type="button"
                disabled={busyId === note.id}
                onClick={() => void markRead(note.id)}
              >
                {t("settings.markRead")}
              </button>
            )}
          </article>
        ))}
      </div>

      <ContextLinks
        locale={locale}
        messages={getMessages(locale)}
        label="settings.accountLabel"
        items={ACCOUNT_LINKS}
      />

      {(posture?.roles ?? []).some((role) => ADMIN_ROLES.has(role)) ? (
        <ContextLinks
          locale={locale}
          messages={getMessages(locale)}
          label="settings.advancedLabel"
          items={ADVANCED_LINKS}
          note="settings.advancedNote"
        />
      ) : null}
    </>
  );
}
