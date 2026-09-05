import type { Locale, Messages } from "@/lib/i18n";
import { NavLinks, type NavGroup } from "./NavLinks";
import { SessionControl } from "./SessionControl";
import { translator } from "@/lib/i18n";

/**
 * التنقّل الرئيسي — **مرتَّبٌ على رحلة الباحث، لا على تاريخ بناء الشاشات**.
 *
 * كان قبل هذا أربعةَ عناصر ظاهرة، وتسعةً مطويّة تحت «أدوات أخرى». وثلاثة
 * أعطاب في ذلك:
 *
 * **١ «أدوات أخرى» ليست تصنيفًا.** هي ما تبقّى بعد أن صُنِّف غيره؛ لا تقول
 * للباحث متى يفتحها ولا ما الذي فيها. فمن أراد «استوديو الورقة» يفتح
 * السلّة ويقرأ تسعةَ أسماء بحثًا عن واحد. والمطويّ لا يُقاس بالنقرة
 * الواحدة التي تكلّفه، بل بأنّه يختفي من ذاكرة الباحث فلا يعرف أن المنصّة
 * تفعله أصلًا.
 *
 * **٢ ومسارٌ بحثيّ لا يُقرأ من قائمة أبجدية.** فالمجموعات هنا مراحلُ عمل:
 * يكتشف، ثمّ يبني، ثمّ يراجع وينشر. والعنوان مكتوبٌ ظاهرٌ فوق كلٍّ منها،
 * لا مطويٌّ خلف مثلّث.
 *
 * **٣ و«البحث العلمي» و«اكتشاف المراجع» كانا بابين إلى الغرفة نفسها.**
 * الأول ينادي `POST /sources/search` فيتوقّف عند أوّل فهرسٍ ردّ بشيء، ولا
 * يفهم DOI، ويبقى معطَّلًا ما دام `LITERATURE_REGISTRY=offline` — وهي حاله
 * في الإنتاج. والثاني ينادي `POST /references/search` فيسأل Crossref
 * وOpenAlex معًا، ويفهم الـDOI، ويُعلن الفهرس المتعذّر باسمه، ويعمل بلا
 * إعدادٍ أصلًا. فبابان أحدهما مغلقٌ ويحمل الاسم الأعمّ («البحث العلمي»)
 * ليس تنوّعًا، بل قسمةُ الباحث بين طريقٍ يعمل وطريقٍ يبدو أنه يعمل.
 * فصارا واحدًا، و`/search` يُحوَّل إلى `/references` فلا يكسر رابطًا محفوظًا.
 */
function groups(t: (key: string) => string): NavGroup[] {
  return [
    {
      id: "start",
      label: null,
      items: [
        { key: "nav.dashboard", label: t("nav.dashboard"), segment: "" },
        { key: "nav.ai", label: t("nav.ai"), segment: "ai" },
        {
          key: "nav.portfolio",
          label: t("nav.portfolio"),
          segment: "portfolio",
          // ما يُفتح من داخل بحثٍ أو من صندوق قراراته — يبقى مسارُه، ويضيء
          // موضعُه في القائمة بدل أن يُترك الباحث بلا موضع.
          owns: ["approvals", "briefs", "claims", "thread", "opportunities", "team"],
        },
        { key: "nav.library", label: t("nav.library"), segment: "library" },
      ],
    },
    {
      id: "discover",
      label: t("nav.groupDiscovery"),
      items: [
        // `search` مسارٌ محوَّل إلى هنا — فيضيء هذا العنصر لمن فتح الرابط القديم.
        {
          key: "nav.references",
          label: t("nav.references"),
          segment: "references",
          owns: ["search"],
        },
        { key: "nav.trends", label: t("nav.trends"), segment: "trends" },
      ],
    },
    {
      id: "build",
      label: t("nav.groupBuild"),
      items: [
        { key: "nav.theses", label: t("nav.theses"), segment: "theses" },
        { key: "nav.analysis", label: t("nav.analysis"), segment: "analysis" },
        { key: "nav.manuscripts", label: t("nav.manuscripts"), segment: "manuscripts" },
      ],
    },
    {
      id: "publish",
      label: t("nav.groupPublish"),
      items: [
        { key: "nav.review", label: t("nav.review"), segment: "review" },
        { key: "nav.journals", label: t("nav.journals"), segment: "journals" },
      ],
    },
    {
      id: "account",
      label: null,
      items: [
        {
          key: "nav.settings",
          label: t("nav.settings"),
          segment: "settings",
          // ما تُفتح من الإعدادات يبقى منسوبًا إليها — بما فيه حالُ التشغيل.
          owns: ["researcher-profile", "research-goals", "profile", "facts",
                 "memory", "agents", "traces", "audit"],
        },
      ],
    },
  ];
}

export function SideNav({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = translator(messages);
  // **الترجمة تقع هنا لا في المتصفّح.** لو مرّ الكتالوج كلّه إلى مكوّن
  // عميل لعبَرَ السلكَ في كل صفحة، وهو تسعون كيلوبايت من نصوصٍ لا تخصّ
  // القائمة. فيُمرَّر ما تحتاجه القائمة وحده: اسمٌ ومقطعٌ لكل عنصر.
  return (
    <>
      <NavLinks locale={locale} groups={groups(t)} label={t("nav.primaryLabel")} />
      <SessionControl locale={locale} messages={messages} />
    </>
  );
}
