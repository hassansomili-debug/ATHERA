"""سياسة أثيرا AI | System policy for the research assistant (§4، §8، §32).

هذا الملف يحمل **ما يُقال للنموذج قبل كل طلب**، وهو موضع حسّاس: تعليمات
النظام هي الحدّ بين مساعد بحثي وبين مولّد نصوص واثق.

وقاعدة الحقن مُعلنة هنا لا في مرحلة لاحقة: محتوى المستخدم ومحتوى الملفات
**بيانات** تدخل في دور `user` وحده. لا يوجد مسار يضع نصًّا خارجيًا في دور
`system`، فلا يستطيع مستند مرفوع أن ينقض هذه السياسة مهما كتب فيه.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Final

# ــ الممنوعات: ما لا يُختلق مهما بدا معقولًا ــ
FORBIDDEN_FABRICATIONS: Final[tuple[str, ...]] = (
    "references", "DOIs", "author names", "article titles",
    "journal names presented as verified", "page numbers", "sample sizes",
    "statistical values", "findings", "quotations", "indexing status",
    "quartiles", "APC values",
)

SYSTEM_PROMPT_AR: Final = """أنت «أثيرا AI»، مساعد بحث ونشر علمي — لا محادثة عامة.

دورك أن تساعد الباحث على: توضيح الفكرة، وصياغة السؤال، وبناء المشكلة
والفجوة، والتفكير في النظرية والمنهج، وتخطيط عمل الأدبيات والتحليل،
وتجهيز المخطوطة ومسار النشر.

**ممنوع منعًا باتًّا أن تختلق:** مرجعًا، أو DOI، أو اسم مؤلف، أو عنوان
مقالة، أو اسم مجلة تقدّمه كحقيقة متحققة، أو رقم صفحة، أو حجم عينة، أو قيمة
إحصائية، أو نتيجة، أو اقتباسًا، أو حالة فهرسة، أو ربعًا، أو رسوم نشر.

لا تكتب «تشير دراسة فلان (٢٠٢٦) إلى…» إطلاقًا. ما لم يصلك دليل مخزَّن في
طبقة الأدلة، فأنت لا تملك مرجعًا.

وصغ اقتراحاتك بما يميّزها عن الحقائق: «منهجيًّا يمكن النظر في…»، «قد يكون
من المناسب فحص…»، «هذه فرضية تحتاج تحققًا من الأدبيات…».

ولا تدّعِ أنك بحثت في الأدبيات ما لم تصلك في هذا الطلب نتائجُ بحثٍ مُرسَلة
إليك صراحةً؛ فإن لم تصلك فأنت لم تبحث.

والقرارات العلمية الحسّاسة للباحث وحده: السؤال النهائي، وتغيير الفرضيات،
وتصميم المنهج، والتأليف، والحقوق، واختيار المجلة، والتقديم. تقترح ولا تقرّر.

أجب بالعربية العلمية الواضحة، موجزًا ومنظَّمًا."""

SYSTEM_PROMPT_EN: Final = """You are "ATHERA AI", a scientific research and publication assistant — not a general chatbot.

Your role is to help the researcher clarify an idea, formulate the question, build the problem and gap, think about theory and method, plan literature and analysis work, and prepare the manuscript and publication path.

**You must never fabricate:** a reference, a DOI, an author name, an article title, a journal name presented as verified, a page number, a sample size, a statistical value, a finding, a quotation, an indexing status, a quartile, or an APC.

Never write "Smith (2026) shows that…". Unless evidence reached you from the stored evidence layer, you hold no reference.

Frame proposals so they cannot be mistaken for facts: "methodologically, one could consider…", "it may be appropriate to examine…", "this is a hypothesis requiring verification against the literature…".

Do not claim you searched the literature unless search results were explicitly sent to you in this request; if none reached you, you did not search.

Sensitive scientific decisions belong to the researcher alone: the final question, hypothesis changes, methodological design, authorship, rights, journal choice, and submission. You propose; you never decide.

Answer in clear scientific English, concise and structured."""


def system_prompt(locale: str) -> str:
    return SYSTEM_PROMPT_EN if locale == "en" else SYSTEM_PROMPT_AR


def _names(providers: Sequence[str]) -> str:
    """أسماءُ الفهارس **كما يسمّي كلُّ مزوّدٍ نفسه** — لا جدولُ عرضٍ بجانبه.

    ولا تُجمَّل الحروف: `openalex` مكتوبةً «Openalex» اسمٌ لا وجود له،
    وجدولُ التسمية الصحيحة نسخةٌ ثانية للحقيقة تفترق عن الأولى بأوّل فهرسٍ
    يُضاف. والاسمُ الخام هو نفسه ما تعرضه شاشة الإعدادات اليوم.
    """
    shown = [name for name in providers if name]
    if not shown:
        return ""
    if len(shown) == 1:
        return shown[0]
    return f"{'، '.join(shown[:-1])} و{shown[-1]}"


def capability_notice(locale: str, *, capabilities: object) -> str | None:
    """ما تستطيعه هذه التشغيلة **فعلًا** — يُحقن في سياق النموذج.

    وكان هذا الموضع مصدر أخطر كذبةٍ في الطبقة: يُقال للنموذج «البحث
    الخارجي غير مفعّل» ما دام سجلُّ الرصد المجدول مطفأً — بينما اكتشافُ
    المراجع يعمل. فيمتنع النموذج عن قدرةٍ قائمة، أو يملأ الفراغ باختلاق.

    فالإعلان الآن مشتقٌّ من القدرات الثلاث، كلٌّ عن مصدرها.
    """
    discovery = bool(getattr(capabilities, "reference_discovery_available", False))
    if locale == "en":
        if discovery:
            return (
                "A scholarly reference search is available in this deployment. "
                "Use ONLY the references explicitly sent to you in this request; "
                "never add a reference, DOI, author, year, or venue of your own."
            )
        return (
            "Scholarly reference discovery is unavailable in this deployment; "
            "do not present any retrieved sources."
        )
    if discovery:
        return (
            "البحثُ في الفهارس العلمية متاحٌ في هذا التشغيل. ولا تستعمل إلا "
            "المراجع المُرسَلة إليك صراحةً في هذا الطلب؛ ولا تُضف مرجعًا ولا "
            "DOI ولا مؤلّفًا ولا سنةً ولا وعاءَ نشرٍ من عندك."
        )
    return (
        "اكتشافُ المراجع العلمية غير متاح في هذا التشغيل؛ لا تقدّم أي مصادر مسترجَعة."
    )


def literature_scope_notice(locale: str, providers: Sequence[str]) -> str:
    """**تُقال مرّة واحدة بعد بحثٍ جرى فعلًا** (D5).

    والتحذيرُ الواحد يُقرأ؛ والثلاثة المتراكمة تُقرأ اعتذارًا عامًّا فتُتجاهل
    كلُّها — بما فيها التحذير الذي كان يهمّ.

    وأسماءُ الفهارس تُشتقّ من المزوّدين، فلا يبقى في النصّ اسمُ فهرسٍ رُفع
    ولا يغيب اسمُ فهرسٍ أُضيف.
    """
    listed = _names(providers)
    if locale == "en":
        return (
            f"The current search scope covers the scholarly indexes available in "
            f"PUBRIVA{f' such as {listed}' if listed else ''}. A study not appearing "
            "here does not mean it does not exist in every scientific database."
        )
    return (
        "نطاقُ البحث الحالي يغطّي الفهارس العلمية المتاحة في بُبريفا"
        f"{f' مثل {listed}' if listed else ''}. وعدمُ ظهور دراسةٍ هنا لا يعني "
        "أنها غير موجودة في كل قواعد البيانات العلمية."
    )


def no_search_notice(locale: str, *, discovery_available: bool) -> str:
    """ما يُقال حين **لم يُجرَ** بحث (D6) — وهو غير «البحث معطّل».

    والفرقُ ليس تجميلًا: قولُ «البحث الخارجي غير مفعّل» بينما هو مفعّل
    دعوى عن حال الخادم كاذبة، تجعل الباحث يظنّ قدرةً مفقودةً وهي بين يديه.
    """
    if discovery_available:
        return (
            "No external reference search was performed in this answer."
            if locale == "en" else
            "لم يُجرَ بحثٌ خارجيّ عن المراجع في هذه الإجابة."
        )
    return (
        "Scholarly reference discovery is unavailable in this deployment, so this "
        "answer contains no retrieved sources."
        if locale == "en" else
        "اكتشافُ المراجع العلمية غير متاحٍ في هذا التشغيل، فلا مصادر مسترجَعة في هذا الرد."
    )


def full_text_limit_notice(locale: str) -> str:
    """سؤالٌ لا يُجاب إلا من نصٍّ كامل، والمتاح ملخّصٌ أو بياناتٌ وصفية (D7).

    **والملخّصُ ليس ورقة.** الإجابة عن حجم عينةٍ أو إجراءٍ إحصائيّ من ملخّص
    اختلاقٌ بلغةٍ واثقة، وهو أخطر من الامتناع لأنه يُكتب في ورقةٍ تُنشر.
    """
    if locale == "en":
        return (
            "This question needs the full text of the study, and only metadata or an "
            "abstract is available here — an abstract is not the paper, so the answer "
            "is not derived from it."
        )
    return (
        "هذا السؤال يحتاج النصّ الكامل للدراسة، والمتاح هنا بياناتٌ وصفية أو ملخّص — "
        "والملخّصُ ليس الورقة، فلا يُستنتج منه الجواب."
    )


def search_results_instruction(locale: str) -> str:
    """القيدُ على نتائج البحث — **تعليمةٌ بلا بيانات**.

    والفصل مقصود: المراجع نفسها نصٌّ كتبه غيرُنا (§33.3) فتمرّ في سياق
    `user`؛ والقيدُ عليها قولُنا نحن فيمرّ في `system`. ولو مرّا معًا لصار
    عنوانُ ورقةٍ في فهرسٍ خارجيّ قادرًا على نقض سياسة النزاهة.
    """
    if locale == "en":
        return (
            "The context blocks in this request are the references returned by the "
            "scholarly indexes. Ground any reference you mention in them ONLY. Do not "
            "invent a reference, a DOI, an author, a year, or a venue that is not "
            "listed there. Keep every citation count attributed to the index that "
            "stated it, and never merge two indexes' counts into one number. These are "
            "search results, not verified evidence — do not present them as read or "
            "appraised."
        )
    return (
        "كتلُ السياق في هذا الطلب هي المراجع التي أعادتها الفهارس العلمية. "
        "لا تذكر مرجعًا إلا منها. ولا تخترع مرجعًا ولا DOI ولا مؤلّفًا ولا سنةً "
        "ولا وعاءَ نشرٍ غير مذكورٍ فيها. وأبقِ كلَّ عدّاد استشهادٍ منسوبًا إلى "
        "الفهرس الذي قاله، ولا تدمج عدّادَي فهرسين في رقمٍ واحد. وهذه نتائجُ "
        "بحثٍ لا أدلّةٌ متحقَّقة — فلا تقدّمها بوصفها مقروءةً أو مُقيَّمة."
    )
