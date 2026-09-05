import { redirect } from "next/navigation";

import { DEFAULT_LOCALE, isLocale } from "@/lib/i18n";

/**
 * «البحث العلمي» — **بابٌ ثانٍ إلى الغرفة نفسها، وأضيقُ البابين**.
 *
 * كانت هذه الشاشة تنادي `POST /api/v1/sources/search`. وهو مسارٌ **يتوقّف
 * عند أوّل فهرسٍ ردّ بشيء** (`if results: break`) — فيرى الباحث ما يعرفه
 * فهرسٌ واحد ويظنّه ما يعرفه العالم. ولا يفهم DOI. ولا يقول أيّ فهرسٍ
 * تعذّر. وزرُّه يبقى معطَّلًا ما دام `LITERATURE_REGISTRY=offline` — وتلك
 * حالُه في الإنتاج، فالشاشة معروضةٌ في القائمة ولا تعمل أصلًا.
 *
 * و`/references` تنادي `POST /api/v1/references/search`: تسأل Crossref
 * وOpenAlex **معًا**، وتنسب كلّ رقمٍ إلى قائله، وتفهم الـDOI، وتُعلن
 * الفهرس المتعذّر باسمه بدل أن تقول «لا نتائج»، وتعمل بلا مفتاحٍ ولا
 * إعداد. فليس بين الشاشتين اختيار: إحداهما تفعل ما تفعله الأخرى وتزيد.
 *
 * **والمسار لا يُحذف، يُحوَّل.** من حفظ `‎/ar/search` يصل إلى الشاشة التي
 * تعمل، ولا يُقابَل بـ404 على رابطٍ كان يعمل بالأمس.
 */
export default async function SearchPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;
  redirect(`/${locale}/references`);
}
