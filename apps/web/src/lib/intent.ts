/**
 * ما الذي لصقه الباحث في مربّع البداية — **وأين يذهب به صدقًا**.
 *
 * الرئيسية تسأل «ماذا تريد أن تنجز؟»، وجوابُ الباحث قد يكون فكرةً مكتوبة،
 * أو DOI نسخه من ورقة، أو رابطًا، أو ملفًا. وكلٌّ من هذه له طريقٌ **قائمٌ
 * يعمل الآن** — فلا يجوز أن يُقال لواحدٍ منها «قريبًا».
 *
 * **والـDOI كان يُقال عنه «قريبًا» وهو يعمل.** زرّ «🔗 DOI أو رابط» في
 * مربّع أثيرا AI كان معطَّلًا بعنوان «قريبًا»، بينما `POST /references/search`
 * يقرأ الـDOI ويحلّه في Crossref وOpenAlex منذ أن وصل اكتشاف المراجع —
 * بلا مفتاح ولا إعداد. فالباحث يُمنع من قدرةٍ يملكها، ويُقال له إنها لم
 * تُبنَ بعد. وذاك أسوأ من زرٍّ ميت: هو ادّعاءٌ عن المنتج مخالفٌ للواقع.
 *
 * ولا يقع هنا حكمٌ على المعنى: التمييز شكليٌّ محض (نمطُ DOI، أو مخطَّط
 * URL)، ولو أخطأ فالباحث يرى نصّه كما هو في الوجهة ويصحّحه.
 */
export type IntentKind = "doi" | "url" | "idea";

export interface DetectedIntent {
  kind: IntentKind;
  /** ما يُرسل إلى الوجهة — الـDOI مجرّدًا من سابقته، والباقي كما كُتب. */
  value: string;
}

/**
 * نمطُ DOI كما تعرّفه Crossref: `10.` ثمّ سجلٌّ رقمي، ثمّ `/` ثمّ لاحقة.
 * ويُقبل مسبوقًا بـ`doi:` أو بعنوان `doi.org`، لأن ذلك ما يُنسخ فعلًا.
 */
const DOI = /(?:^|\b(?:doi:|https?:\/\/(?:dx\.)?doi\.org\/))(10\.\d{4,9}\/\S+)$/i;

const URL_LIKE = /^https?:\/\/\S+$/i;

export function detectIntent(raw: string): DetectedIntent | null {
  const text = raw.trim();
  if (!text) return null;

  // نصٌّ بسطرٍ واحد وحده يُفحص كمعرّف؛ فقرةٌ فيها DOI هي فكرةٌ لا معرّف.
  if (!/\s/.test(text) || /^doi:\s*\S+$/i.test(text)) {
    const compact = text.replace(/^doi:\s*/i, "");
    const doi = DOI.exec(compact);
    if (doi) return { kind: "doi", value: doi[1] };
    if (URL_LIKE.test(compact)) return { kind: "url", value: compact };
  }
  return { kind: "idea", value: text };
}

/**
 * الوجهة — **ومسارٌ يعمل لكل نوع**.
 *
 *   doi/url  اكتشاف المراجع: يحلّ المعرّف في فهرسين ويعرض ما قاله كلٌّ منهما
 *   idea     بُبريفا AI: سطحُ التفكير والتنفيذ، والرئيسية توجّه إليه ولا تحلّ محلّه
 */
export function destinationFor(intent: DetectedIntent, locale: string): string {
  const query = encodeURIComponent(intent.value);
  if (intent.kind === "idea") return `/${locale}/ai?q=${query}`;
  return `/${locale}/references?q=${query}`;
}
