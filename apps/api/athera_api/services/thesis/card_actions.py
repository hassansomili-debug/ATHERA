"""أفعالُ البطاقة | The one authoritative Thesis Center card state machine (Wave 1.1).

**العطب: معماريّتان منفصلتان تُعرضان سيرَ عملٍ واحدًا.**

  • `ThesisSection` لا يُكتب إلّا في موضعٍ واحد: `POST /theses/{id}/parse`
    القديم.
  • خطُّ الرفع الحديث (`document_intelligence`) **لا يكتب** `ThesisSection`
    ولا `ThesisResult` إطلاقًا — يكتب `FactCandidate`.
  • و`mine-opportunities` **لا يقرأ إلّا** `ThesisSection` و`ThesisResult`.

فرسالةٌ عالجها الخطُّ الحديث **لا دليل عندها للمنقّب أصلًا**، والشاشة كانت
تعرض زرّ «استخراج الفرص» مشروطًا بـ`parsed_at` — وهو ختمٌ لا يضعه إلّا
المسار القديم. فالزرّ إمّا مطفأٌ إلى الأبد، أو يُضغط فيكتب «٠ فرص» على
رسالةٍ لم تُفحص أصلًا.

**فتُجمع القرارات كلّها هنا، في دالّةٍ خالصةٍ واحدة.** الشاشة لا تجتهد:
تعرض ما يقوله الخادم. ومن أراد تغيير القاعدة غيّرها في موضعٍ واحد، لا في
سبعة شروطٍ متفرّقة في JSX.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final

from . import processing

# ═════════════════════ ١. مفردةُ الفعل ═════════════════════
#
# **مفردةٌ مغلقة**: فعلٌ لا اسم له هنا لا تعرضه البطاقة.

ACTION_REVIEW: Final = "review"                # افتح شاشة مراجعة ما استُخرج
ACTION_PROCESS: Final = "process"              # اقرأ الرسالة أوّل مرّة
ACTION_REPROCESS: Final = "reprocess"          # أعد القراءة (وقد قُرئت من قبل)
ACTION_ATTACH_FILE: Final = "attach_file"      # رسالةٌ مسجّلة يدويًّا بلا ملفّ
ACTION_ARCHIVE: Final = "archive"              # أخفِ السجلّ من مركز الرسائل
ACTION_RESTORE: Final = "restore"              # أعده من الأرشيف
ACTION_TRASH_FILE: Final = "trash_file"        # انقل ملفّ المصدر إلى السلّة
ACTION_VIEW_OPPORTUNITIES: Final = "view_opportunities"  # افتح فرصَ النشر القائمة

ACTIONS: Final[tuple[str, ...]] = (
    ACTION_REVIEW, ACTION_PROCESS, ACTION_REPROCESS,
    ACTION_ATTACH_FILE, ACTION_ARCHIVE, ACTION_RESTORE, ACTION_TRASH_FILE,
)

#: **نصُّ المنع أثناء العمل الجاري** — والخادم يفرضه أيضًا، لا الشاشةُ وحدها.
LIFECYCLE_BLOCKED_LABELS: Final[tuple[str, str]] = (
    "لا تُؤرشَف رسالةٌ يجري عليها عملٌ الآن، ولا يُنقل ملفُّها إلى السلّة: "
    "مهمّةٌ تقرأ الملفّ وتكتب مرشّحاتها بينما يُسحب من تحتها تترك نصفَ حال، "
    "**ولا سبيل إلى إلغائها في هذه المرحلة** — فيُقال ذلك ولا يُدَّعى إلغاء. "
    "انتظر انتهاءها ثمّ أعد المحاولة.",
    "A thesis cannot be archived, and its file cannot be trashed, while work is "
    "running on it: a task reading the file and writing its candidates while the "
    "record is pulled from under it leaves a half-state, and there is no cancellation "
    "contract at this stage — so this says so rather than pretending to cancel. Wait "
    "for it to finish, then try again.",
)

#: الحالات التي تُفتح عندها المراجعة — **لا كلُّ حالٍ غير فارغة**.
REVIEWABLE: Final[tuple[str, ...]] = (
    processing.AWAITING_CONSENT, processing.READY_FOR_REVIEW, processing.COMPLETED,
)


# ═════════════════════ ٢. حالُ استخراج الفرص ═════════════════════
#
# **ولا يُدَّعى تكاملٌ لم يقع.** المنقّب يقرأ `thesis_sections` و
# `thesis_results` ولا شيء غيرهما. فإن لم يوجد منهما صفٌّ لهذه الرسالة فليس
# عند المنقّب دليلٌ يقرؤه — وضغطةُ الزرّ حينها تختم «نُقِّب فلم يُوجد» على
# رسالةٍ لم تُفحص أصلًا، وهو أسوأ من زرٍّ غائب.

MINING_AVAILABLE: Final = "available"          # عند المنقّب دليلٌ يقرؤه
MINING_IN_FLIGHT: Final = "in_flight"          # المعالجة جاريةٌ الآن
MINING_NO_EVIDENCE: Final = "no_evidence"      # لا دليلَ مؤهَّل بعد
MINING_FOUND: Final = "found"                  # فرصٌ قائمةٌ على هذه الرسالة
MINING_FAILED: Final = "failed"                # تعثّر التنقيب — ولا يمسّ الاستخراج
# **حُجب ≠ اكتمل بلا نتيجة، وكلاهما ≠ فشل.** ثلاثُ وقائعَ مختلفة كانت
# تُطوى في واحدة، فتقول البطاقةُ عن سياسةٍ وقعت كما يجب إنّها «لا دليل».
MINING_WITHHELD: Final = "withheld"            # دليلٌ قائم، حُجب عن الاستعمال التلقائيّ
MINING_COMPLETED_EMPTY: Final = "completed_empty"  # جرى على دليلٍ مؤهَّل فلم يتكوّن شيء

MINING_STATES: Final[tuple[str, ...]] = (
    MINING_AVAILABLE, MINING_IN_FLIGHT, MINING_NO_EVIDENCE,
    MINING_FOUND, MINING_FAILED, MINING_WITHHELD, MINING_COMPLETED_EMPTY,
)

MINING_LABELS: Final[dict[str, tuple[str, str]]] = {
    # **ولا مفرداتِ نظامٍ في وجه الباحث.** «المنقّب» و«استخراج الفرص»
    # اسمان داخليّان؛ والباحثُ يقرأ ما يعنيه هو: رسالتُه ومعالجتُها.
    MINING_AVAILABLE: (
        "يمكن استكمال معالجة الرسالة الآن — فيها عناصر تصلح أساسًا لفرص نشر.",
        "This thesis can be processed further now: it holds elements that can support "
        "publication opportunities.",
    ),
    MINING_IN_FLIGHT: (
        "نعالج الرسالة ونستخرج فرص النشر — يبدأ ذلك تلقائيًّا ولا يلزمك تشغيله.",
        "We are processing your thesis and preparing its publication opportunities; "
        "this starts automatically and you do not need to trigger it.",
    ),
    MINING_FOUND: (
        # **ومبدئيّةٌ تُقال في متن العبارة، لا في حاشية.** الفرصُ مشتقّةٌ من
        # عناصر الرسالة وحدها: لا مقابلةَ بأدبٍ منشور، ولا حكمَ جِدّةٍ، ولا
        # ترتيبَ أفضليّة. وادّعاءُ أيٍّ من ذلك اليوم وعدٌ لا سند له.
        "فرصُ نشرٍ مبدئيّة مشتقّة من عناصر رسالتك وحدها — قبل مقابلتها "
        "بالأدب المنشور، وقبل أيّ حكمٍ على جِدّتها أو ترتيبها.",
        "Preliminary publication opportunities derived from your thesis alone — before "
        "any comparison with published literature, and before any novelty or ranking "
        "judgement.",
    ),
    MINING_FAILED: (
        # **وفشلُ التنقيب لا يُقرأ فشلَ استخراج.** ما استُخرج باقٍ ومؤصَّل.
        "تعثّر استخراجُ الفرص. وقراءةُ رسالتك تمّت وما استُخرج منها محفوظ — "
        "ويمكن إعادةُ محاولة الاستخراج وحدها.",
        "Opportunity scanning failed. Reading your thesis succeeded and everything "
        "extracted from it is kept; only the scan can be retried.",
    ),
    # **ونصُّ «راجِعْ ثمّ صِلْ ما اعتمدته بالمنقّب» نُزع.** كان يصف خطًّا
    # تقاعد في T0 وT0.1: الأتمتة تقرأ المعرفةَ المعتمَدة من نفسها، ولا
    # اعتمادَ لكلّ واقعة. وإبقاؤه يطلب من الباحث عملًا لم يعد موجودًا.
    MINING_NO_EVIDENCE: (
        "لم يجرِ فحصُ الفرص بعد: لا دليلَ مؤهَّل على هذه الرسالة حتى الآن. "
        "والفحصُ يبدأ تلقائيًّا بعد قراءة الرسالة، ولا يلزمك تشغيلُه.",
        "The opportunity scan has not run yet: no eligible evidence exists on this "
        "thesis so far. The scan starts automatically once the thesis has been read; "
        "you do not need to trigger it.",
    ),
    # **حُجب: سياسةٌ وقعت كما يجب، لا عطب.** ولا يُقال فيه «اعتمِدْ وقائعَ
    # قبل التنقيب» — تلك بوّابةٌ تقاعدت، والمراجعةُ هنا ضبطُ جودةٍ اختياريّ.
    MINING_WITHHELD: (
        "اكتمل فحصُ الرسالة، وفيها معرفةٌ مستخرَجة. وحُجب بعضُ الأدلّة عن "
        "الاستعمال التلقائيّ لأسبابٍ تتعلّق بالثقة أو الاتّساق أو سلامة "
        "الدليل. ولا يلزمك اعتمادُ شيءٍ لتعمل الأتمتة؛ ومراجعةُ ما استُخرج "
        "ضبطُ جودةٍ اختياريّ، وقد تُتيح أدلّةً أكثر.",
        "The thesis scan completed and extracted knowledge exists. Some evidence was "
        "withheld from automatic use for confidence, consistency, or evidence-integrity "
        "reasons. Nothing needs your approval for the automation to run; reviewing what "
        "was extracted is optional quality control and may make more evidence usable.",
    ),
    # **ولا يُقال «لا فرصَ نشرٍ لهذه الرسالة».** تلك دعوى عن العالم لا نملك
    # سندَها؛ وما نملكه أنّ النظام لم يُكوّن واحدةً موثوقةً ممّا توفّر.
    MINING_COMPLETED_EMPTY: (
        "اكتمل فحص الرسالة، ولم يتمكن النظام من تكوين فرصة نشر موثوقة بما يكفي "
        "من الأدلة المتاحة. ويمكنك استكمال المعالجة للمحاولة من جديد.",
        "The thesis scan completed, but the available evidence was not sufficient to "
        "form a reliable publication opportunity. You can continue processing to try "
        "again.",
    ),
}


def mining_state(*, processing_state: str, thesis_mining_state: str,
                 opportunities: int, sections: int, results: int) -> str:
    """حالُ التنقيب كما يراها الباحث — **ومصدرُها حالُ التنقيب نفسه**.

    **وعدُّ الجداول القديمة لم يعد الحَكَم.** كان الجوابُ يُشتقّ من
    `ThesisSection`/`ThesisResult`، وهما لا يُكتبان في المسار الحديث أصلًا:
    ‏`ThesisResult` بلا كاتبٍ في التطبيق كلّه. فرسالةٌ حديثةٌ نُقِّبت فعلًا
    وكُتبت فرصُها كانت تُعرض «لا دليل» — والشاشةُ تكذب على واقعةٍ محفوظة.

    فالترتيب: فرصٌ قائمةٌ أوّلًا (وهي واقعةٌ لا تُؤوَّل)، ثمّ حالُ التنقيب
    المحفوظة، ثمّ العملُ الجاري. **والقديمُ يبقى مقروءًا للتوافق** ولا
    يقود الرحلةَ الحديثة.

    ## و`running` محلّيّةُ المعاملة — تُقال كما هي لا كما نتمنّاها

    `mining.run` يكتب `running` ثمّ يُتمّ عملَه ويكتب الحالَ النهائية
    **في المعاملة نفسها**. فلا جلسةٌ أخرى تراها قطّ: هي حارسٌ داخل
    المعاملة، لا حالٌ مرصودةٌ من الخارج. فالسطرُ الذي يقرؤها هنا صحيحٌ
    ولا يُعتمد عليه، و`in_flight` تُبلَغ عمليًّا من `processing_state`.

    **ولا يُصلَح ذلك بمعاملتين هنا:** إيداعُ `running` وحدها يفتح بابَ
    «عالقةٌ في الجريان» إن مات المسار بينهما، وذاك يحتاج استرجاعًا
    للحال البائتة — عملٌ لاحقٌ مستقلّ، لا أثرٌ جانبيّ لبطاقة.
    """
    if opportunities > 0:
        return MINING_FOUND
    if thesis_mining_state == "running" or processing_state in processing.IN_FLIGHT:
        return MINING_IN_FLIGHT
    if thesis_mining_state == "failed":
        return MINING_FAILED
    if thesis_mining_state == "withheld":
        return MINING_WITHHELD
    if thesis_mining_state == "completed":
        return MINING_COMPLETED_EMPTY
    # **توافقٌ مع القديم، لا قيادةٌ منه.**
    if sections > 0 or results > 0:
        return MINING_AVAILABLE
    return MINING_NO_EVIDENCE


# ═════════════════════ ٣. المسار القديم لا يُعرض فعلًا عاديًّا ═════════════════════

_PARSE_WITHDRAWN_AR: Final = (
    "«تفكيك الرسالة» مسارٌ قديم بقي في الواجهة البرمجية ولم يعد فعلًا على "
    "البطاقة: القراءة التلقائية هي القاعدة، وتشغيلُ المسارين على رسالةٍ واحدة "
    "ينتج مجموعتَي مرشّحاتٍ متوازيتين إحداهما خارج شاشة المراجعة."
)
_PARSE_WITHDRAWN_EN: Final = (
    "\"Parse thesis\" is the legacy path. It stays in the API and is no longer a card "
    "action: automatic reading is canonical, and running both paths on one thesis "
    "produces two parallel candidate sets, one of them outside the review screen."
)


def offers_parse(processing_state: str, *, has_file: bool) -> bool:
    """**لا حالَ بطاقةٍ واحدة تعرض «تفكيك الرسالة» اليوم — ويُقال لماذا.**

    والعهدُ صريح: **تبقى النقطة `/parse` في الواجهة البرمجية** ولا تُحذف.
    المسحوبُ عرضُها فعلًا عاديًّا على البطاقة، لا وجودُها.

    ولم تُكتب هذه قيمةً ثابتة في الشاشة بل شرطًا مسمّى هنا: يومَ يصير للمسار
    القديم حالٌ صادقةٌ يُعرض فيها، يُغيَّر السطر في موضعٍ واحد ويحمل الفحصُ
    سببه معه.
    """
    del processing_state, has_file  # لا حالَ اليوم تُبرّر عرضه — والسبب أعلاه.
    return False


def parse_withdrawn_reason(locale: str) -> str:
    return _PARSE_WITHDRAWN_EN if locale == "en" else _PARSE_WITHDRAWN_AR


# ═════════════════════ ٤. البطاقة كاملةً ═════════════════════

@dataclass(frozen=True, slots=True)
class CardActions:
    """ما تعرضه البطاقة — **قرارٌ واحد يُحسب في الخادم، لا سبعةٌ في JSX**."""

    primary: str | None
    is_running: bool
    can_review: bool
    can_process: bool
    can_reprocess: bool
    can_parse: bool
    can_attach_file: bool
    can_mine: bool
    #: **فرصٌ قائمة تُفتح** — وهي وجهةُ الرحلة، لا زرُّ تشغيلٍ يدويّ.
    can_view_opportunities: bool
    can_archive: bool
    can_restore: bool
    can_trash_file: bool
    is_archived: bool
    lifecycle_blocked_reason: str | None
    mining_state: str
    mining_reason: str
    parse_withdrawn_reason: str
    blocked_reason: str | None


def _pick(locale: str, arabic: str, english: str) -> str:
    return english if locale == "en" else arabic


def compute(
    *,
    processing_state: str,
    file_id: uuid.UUID | None,
    sections: int,
    results: int,
    locale: str,
    archived: bool = False,
    opportunities: int = 0,
    thesis_mining_state: str = "not_started",
) -> CardActions:
    """آلةُ حالِ البطاقة — **وكلُّ فعلٍ معروضٍ فعلٌ يقبله الخادم**.

    القواعد، بترتيب الحسم:

      ١ **حالٌ يجري فيها عملٌ الآن لا فعل عليها.** `queued` و`parsing` و
        `extracting` تعرض حالها وتقول إنّ عملًا يجري، ولا تعرض «فكّك» ولا
        «نقّب» ولا «أعد المحاولة» — لأنّ الخادم يردّها بـ409
        (`claim_for_processing`).
      ٢ **رسالةٌ مسجّلة يدويًّا بلا ملفّ لا يُعرض عليها «تفكيك الرسالة»**:
        النقطة تردّ `thesis.no_file` بـ422. فيُعرض «أرفق ملفّ الرسالة».
      ٣ **`ready_for_review` فعلُها الأول المراجعة**، والثاني إعادة القراءة.
      ٤ **مستندٌ ممسوح ضوئيًّا لا يُعرض عليه فعلٌ يُعيد النتيجة نفسها** —
        `RETRYABLE` لا تشمله عمدًا، ويبقى سببُه معروضًا.
      ٥ **ولا فعلَ يغيّر دورةَ الحياة أثناء عملٍ جارٍ.** أرشفةٌ أو نقلُ
        ملفٍّ إلى السلّة بينما مهمّةٌ خلفيّة تقرأ الملفّ وتكتب مرشّحاتها
        يتركان نصفَ حال، **ولا عقدَ إلغاءٍ في هذا المنتج** يُوقفها أو
        يُسلسلها. فيُمنع الفعل بسببٍ مكتوب، ولا يُدَّعى إلغاءٌ لا وجود له.
        **والخادم يفرض الحدّ نفسه** — شاشةٌ تُخفي زرًّا وخادمٌ يقبل الطلب
        حارسٌ واحدٌ لا اثنان.
      ٦ **والمؤرشَفة لا تُعرض عليها أفعالُ العمل**، بل الاسترجاع وحده:
        قراءةٌ أو تنقيبٌ على سجلٍّ مُخفًى يكتب في ما لا يراه صاحبه.
    """
    in_flight = processing_state in processing.IN_FLIGHT
    has_file = file_id is not None
    # **والمؤرشَفة ساكنة**: لا يُعرض عليها فعلُ عملٍ ما دامت خارج القائمة.
    retryable = has_file and processing_state in processing.RETRYABLE and not archived

    can_review = (not in_flight) and (not archived) and processing_state in REVIEWABLE
    # «اقرأ» و«أعد القراءة» نقطةٌ واحدة وفعلان مختلفان في نصّهما: أوّلُ قراءةٍ
    # ليست إعادةً، وتسميتُها إعادةً تجعل الباحث يظنّ أنّه أضاع شيئًا.
    first_read = retryable and processing_state == processing.UPLOADED
    can_process = first_read
    can_reprocess = retryable and not first_read
    can_attach_file = (not has_file) and (not in_flight) and not archived

    mining = mining_state(processing_state=processing_state,
                          thesis_mining_state=thesis_mining_state,
                          opportunities=opportunities,
                          sections=sections, results=results)

    # ── الأتمتة تملك التنقيب، فلا زرَّ تشغيلٍ يدويّ في الحال السويّة ──
    #
    # **وزرٌّ يطلب من الباحث تشغيلَ ما يعمل من نفسه يجعله مسؤولًا عن آلة.**
    # فيبقى الفعلُ اليدويّ **إعادةَ محاولةٍ عند التعثّر وحده**، وللمسار
    # القديم الذي لا أتمتةَ له. وما عدا ذلك: تُفتح الفرصُ ولا تُشغَّل.
    can_mine = (
        # **و`completed_empty` صارت منها — وهذا عكسُ قرارٍ سابق، بسببه.**
        #
        # كان الحجّة أنّ زرًّا يَعِد بنتيجةٍ أخرى من المُدخل نفسه وعدٌ كاذب.
        # وقد كان ذلك صحيحًا يومَ كان التكوينُ ثابتًا. ثمّ صار المُدخل نفسُه
        # يُنتج مقترحًا محافظًا لم يكن يُنتجه (`_fallback_draft`)، فرسالةٌ
        # خُتمت بصفر قبل الإصلاح تُنتج اليوم فرصةً عند إعادة المحاولة.
        # فمنعُ الاستكمال هنا يحبس الباحثَ في نتيجةٍ تجاوزها المنتج.
        (mining in {MINING_FAILED, MINING_AVAILABLE, MINING_WITHHELD,
                    MINING_COMPLETED_EMPTY})
        and not in_flight and not archived
    )
    can_view_opportunities = opportunities > 0 and not archived

    # **دورةُ الحياة تقف أثناء العمل الجاري** — والسببُ يُقال حيث يقع.
    lifecycle_blocked = (_pick(locale, *LIFECYCLE_BLOCKED_LABELS)
                         if in_flight else None)
    can_archive = (not archived) and not in_flight
    can_restore = archived
    can_trash_file = has_file and (not in_flight) and not archived

    primary: str | None
    if archived:
        primary = ACTION_RESTORE
    elif can_attach_file:
        primary = ACTION_ATTACH_FILE
    # ── وجهةُ الرحلة تسبق ضبطَ الجودة ──
    #
    # **ومراجعةُ الوقائع صارت اختيارية.** كانت الفعلَ الأول لأنّ التنقيب
    # كان يتوقّف عليها؛ ولم يعد. فرسالةٌ لها فرصٌ قائمة وجهتُها الفرص،
    # والمراجعةُ تبقى معروضةً لمن أرادها — ضبطَ جودةٍ لا بوّابةَ مرور.
    elif can_view_opportunities:
        primary = ACTION_VIEW_OPPORTUNITIES
    elif can_review:
        primary = ACTION_REVIEW
    elif can_process:
        primary = ACTION_PROCESS
    elif can_reprocess:
        primary = ACTION_REPROCESS
    else:
        primary = None

    blocked: str | None = None
    if in_flight:
        blocked = _pick(locale, *processing.STATE_LABELS[processing_state])
    elif processing_state == processing.TEXT_LAYER_MISSING:
        blocked = _pick(locale, *processing.FAILURE_LABELS["text_layer_missing"])

    return CardActions(
        primary=primary,
        is_running=in_flight,
        can_review=can_review,
        can_process=can_process,
        can_reprocess=can_reprocess,
        can_parse=offers_parse(processing_state, has_file=has_file),
        can_attach_file=can_attach_file,
        can_mine=can_mine,
        can_view_opportunities=can_view_opportunities,
        can_archive=can_archive,
        can_restore=can_restore,
        can_trash_file=can_trash_file,
        is_archived=archived,
        lifecycle_blocked_reason=lifecycle_blocked,
        mining_state=mining,
        mining_reason=_pick(locale, *MINING_LABELS[mining]),
        parse_withdrawn_reason=parse_withdrawn_reason(locale),
        blocked_reason=blocked,
    )
