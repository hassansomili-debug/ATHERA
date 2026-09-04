"""استخراج مصفوفة الأدبيات | Literature matrix auto-extraction (PUBRIVA).

**كل ما هنا محكومٌ بسؤالٍ واحد: هل قالت الورقة هذا حرفًا؟**

ومصفوفةٌ تُملأ آليًّا أخطر من مصفوفةٍ فارغة، لأنها تبدو مقروءة. فثلاث
قواعد تحكم كل سطرٍ في هذا الملف:

**الأولى: لا شيء يُستخرج من عنوان.** العنوان دعوى المؤلف لا نتيجته، و«أثر
كذا في كذا» عنوانٌ لدراسةٍ مقطعية لا تقيس أثرًا. فمن قرأ العنوان استخرج
سببيةً لم تُقس — والقارئ يراها في عمود «النتائج» فيصدّقها. فالمقروء هنا
هو الملخّص أو النصّ الكامل، **ولا شيء غيرهما**.

**الثانية: كل قيمة تحمل نصًّا موجودًا حرفيًّا فيما قُرئ.** وهو حاجزُ
`extraction.base` نفسه الذي يحرس مرشّحات الذاكرة الموثقة — لا حاجزٌ ثانٍ
يفترق عنه بأول إصلاح. وما لا يجتاز الحاجز لا يصل الشاشة أصلًا.

**والثالثة: المدى قيدٌ لا ترجيح.** بياناتٌ وصفية لا يُستخرج منها منهجٌ ولا
عيّنة ولا نظرية؛ وملخّصٌ لا يُستخرج منه إلا ما نطق به الملخّص. و«لم تذكر
الورقة نظريةً» تُكتب `missing` — **لا «لم تُستعمل نظرية»**: الأولى وصفٌ لما
قرأناه، والثانية دعوى عن الدراسة لم يقلها أحد.

وما يخرج من هنا كلُّه **مرشَّح**: `needs_review` و`unverified`، وطريقته
`model`. والمفردة `model` هي كلمة المنصّة لِما لم يكتبه إنسان — وهذا
المستخرِج حتميٌّ بلا نموذج لغوي (§4 Provider Independent)، لكن نسبته إلى
`model` مقصودة: بها يشمله قيدُ القاعدة `model_value_is_not_self_approved`
الذي يمنع أن يُكتب معتمَدًا بلا مُعتمِدٍ بشريّ يُسمّى. ومفردةٌ رابعة تعني
«آليّ» كانت ستخرج من تحت ذلك القيد — وهو ثمنٌ لا يُدفع لأجل دقّة تسمية.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.literature import Source
from ..models.research import DocumentChunk
from ..models.screening import LiteratureMatrixCell, SourceAbstract
from . import screening as sc
from .extraction.base import quote_is_grounded
from .publishing.drafting import numbers

# ═══════════════════════ ما يُقرأ ومن أين ═══════════════════════

# **قطعةُ نصٍّ واحدة ومن أين جاءت.** والموضع ليس زينة: به يعود القارئ إلى
# ما قرأناه فيتحقّق منه بنفسه، وبدونه تبقى القيمة دعوى.
@dataclass(frozen=True, slots=True)
class ReadPassage:
    text: str
    # رقمُ الصفحة إن قرأه المُقطِّع من الملف نفسه. **ولا يُشتقّ من ترتيب
    # المقطع**: المقطع السابع ليس الصفحة السابعة، ومن كتب ذلك أرسل القارئ
    # إلى صفحةٍ لا تحمل ما نُسب إليها. و`None` تعني «لا نعرف»، وهي صادقة.
    page: int | None = None
    section: str | None = None
    abstract_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """قيمةٌ مرشَّحة لعمودٍ واحد — **ومعها النصّ الذي قالها**."""

    field_key: str
    value_ar: str
    quote: str
    passage: ReadPassage


# ═══════════════════════ المفردات المقروءة ═══════════════════════
#
# **كلُّ نمطٍ هنا يلتقط لفظًا صريحًا، ولا واحدٌ منها يستنتج.** والحدّ مقصود:
# ما لا يُلتقط بثقة يبقى `missing` ويملؤه الباحث — وهو أرخص بكثير من قيمةٍ
# مخترعة يعتمدها لأنها ظهرت أمامه.

_AR = r"[؀-ۿ]"

# تصاميم البحث. والقيمة المكتوبة هي **اللفظ الذي وُجد**، لا تصنيفٌ نُسقطه.
_DESIGNS: Final[tuple[tuple[str, re.Pattern[str], bool], ...]] = (
    # (المفتاح الداخلي، النمط، هل يقيس سببية؟)
    ("randomized_trial",
     re.compile(r"randomi[sz]ed\s+controlled\s+trial|تجربة\s+عشوائية\s+محكمة",
                re.IGNORECASE), True),
    ("experimental",
     re.compile(r"\bquasi[-\s]?experimental\b|\bexperimental\s+(?:design|study)\b|"
                r"شبه\s+تجريبي\w*|المنهج\s+التجريبي|تصميم\s+تجريبي\w*",
                re.IGNORECASE), True),
    ("longitudinal",
     re.compile(r"\blongitudinal\b|\bpanel\s+data\b|دراسة\s+طولية|المنهج\s+الطولي",
                re.IGNORECASE), False),
    ("cross_sectional",
     re.compile(r"\bcross[-\s]?sectional\b|دراسة\s+مقطعية|المنهج\s+المقطعي",
                re.IGNORECASE), False),
    ("correlational",
     re.compile(r"\bcorrelational\b|دراسة\s+ارتباطية|المنهج\s+الارتباطي",
                re.IGNORECASE), False),
    ("survey",
     re.compile(r"\bsurvey\s+(?:design|study|research)\b|\bquestionnaire\s+survey\b|"
                r"المنهج\s+المسحي|دراسة\s+مسحية", re.IGNORECASE), False),
    ("descriptive",
     re.compile(r"\bdescriptive\s+(?:design|study|research)\b|"
                r"المنهج\s+الوصفي|دراسة\s+وصفية", re.IGNORECASE), False),
    ("case_study",
     re.compile(r"\bcase\s+study\b|دراسة\s+حالة", re.IGNORECASE), False),
    ("systematic_review",
     re.compile(r"\bsystematic\s+review\b|\bmeta[-\s]?analysis\b|"
                r"مراجعة\s+منهجية|تحليل\s+بعدي", re.IGNORECASE), False),
    ("qualitative",
     re.compile(r"\bqualitative\s+(?:study|design|research|approach)\b|"
                r"المنهج\s+النوعي|دراسة\s+نوعية", re.IGNORECASE), False),
    ("mixed_methods",
     re.compile(r"\bmixed[-\s]?methods?\b|المنهج\s+المختلط", re.IGNORECASE), False),
)

# **تصاميمٌ لا تقيس سببية.** ووجودُ واحدٍ منها يمنع كتابة نتيجةٍ سببية
# آليًّا — لا لأن المؤلف لم يقلها، بل لأن دراسته لا تسندها.
_NON_CAUSAL_DESIGNS: Final = frozenset(
    key for key, _pattern, causal in _DESIGNS if not causal)

# ألفاظ السببية. و«الأثر» و«التأثير» منها: هما أشيع ما يُكتب في عناوين
# الدراسات المقطعية العربية، ونقلُهما إلى عمود النتائج يقلب ارتباطًا سببًا.
_CAUSAL_MARKERS: Final = re.compile(
    r"\beffects?\s+of\b|\bimpacts?\s+of\b|\bcauses?\b|\bcaused\b|\bleads?\s+to\b|"
    r"\bled\s+to\b|\bresults?\s+in\b|\bdue\s+to\b|\bbecause\s+of\b|"
    r"\bimproves?\b|\bincreases?\b|\breduces?\b|\bdecreases?\b|"
    r"أثر\w*|تأثير\w*|يؤدي\s+إلى|تؤدي\s+إلى|يسبب|تسبب|بسبب|نتيجةً?\s+لـ?",
    re.IGNORECASE)

_METHODS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("questionnaire", re.compile(r"\bquestionnaires?\b|\bsurvey\b|استبان\w*|استبيان\w*",
                                 re.IGNORECASE)),
    ("interviews", re.compile(r"\b(?:semi[-\s]?structured\s+)?interviews?\b|مقابل\w*",
                              re.IGNORECASE)),
    ("focus_groups", re.compile(r"\bfocus\s+groups?\b|مجموعات\s+مركزة", re.IGNORECASE)),
    ("observation", re.compile(r"\bobservations?\b|الملاحظة\s+المباشرة", re.IGNORECASE)),
    ("content_analysis", re.compile(r"\bcontent\s+analysis\b|تحليل\s+(?:ال)?مضمون",
                                    re.IGNORECASE)),
    ("secondary_data", re.compile(r"\bsecondary\s+data\b|\barchival\s+data\b|"
                                  r"بيانات\s+ثانوية", re.IGNORECASE)),
)

_ANALYSES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("pls_sem", re.compile(r"\bPLS[-\s]?SEM\b", re.IGNORECASE)),
    ("sem", re.compile(r"\bstructural\s+equation\s+model\w*\b|\bSEM\b|"
                       r"نمذجة\s+المعادل\w*\s+البنائية", re.IGNORECASE)),
    ("regression", re.compile(r"\b(?:multiple|hierarchical|logistic|linear)?\s*"
                              r"regression\b|تحليل\s+الانحدار|الانحدار\s+المتعدد",
                              re.IGNORECASE)),
    ("anova", re.compile(r"\bANOVA\b|\banalysis\s+of\s+variance\b|تحليل\s+التباين",
                         re.IGNORECASE)),
    ("t_test", re.compile(r"\bt[-\s]?tests?\b|اختبار\s+ت\b", re.IGNORECASE)),
    ("thematic_analysis", re.compile(r"\bthematic\s+analysis\b|التحليل\s+الموضوعي",
                                     re.IGNORECASE)),
    ("factor_analysis", re.compile(r"\b(?:exploratory|confirmatory)?\s*factor\s+"
                                   r"analysis\b|التحليل\s+العاملي", re.IGNORECASE)),
)

# **النظرية تُذكر باسمها أو لا تُذكر.** ولا تُستنتج من «إطار» ولا من
# «نموذج»: كثيرٌ من الدراسات تبني نموذجًا ولا تستند إلى نظرية، وكتابةُ اسمٍ
# لها هنا اختراعُ سندٍ نظريّ لورقةٍ لا سند لها.
_THEORY: Final = re.compile(
    r"(?:[A-Z][\w'’-]*(?:\s+[A-Z]?[\w'’-]+){0,4}\s+)theory\b"
    r"|theory\s+of\s+(?:[\w'’-]+(?:\s+[\w'’-]+){0,3})"
    r"|نظري[ةه]\s+" + _AR + r"[\w؀-ۿ]*(?:\s+" + _AR + r"[\w؀-ۿ]*){0,3}",
    re.IGNORECASE)

# **المقياس اسمُ أداة، لا وصفُ تصميم.** و«استبانة» وحدها منهجُ جمعٍ لا
# مقياس — موضعها عمود «المنهج»، وتكرارها هنا يملأ عمودين بشيءٍ واحد ثم
# يُقرأ أداةً موصوفة. فيُشترط لفظُ أداةٍ صريح: مقياسٌ أو جردٌ أو أداة أو
# معامل ثبات.
_MEASURES: Final = re.compile(
    r"\b(?:[A-Z][\w'’-]*\s+){0,3}(?:[Ss]cale|[Ii]nventory|[Ii]nstrument)\b"
    r"|\bCronbach'?s?\s+alpha\b"
    r"|مقياس\s+" + _AR + r"[\w؀-ۿ]*(?:\s+" + _AR + r"[\w؀-ۿ]*){0,3}"
    r"|ألفا\s+كرونباخ|معامل\s+الثبات")

_OBJECTIVE: Final = re.compile(
    r"\bthis\s+(?:study|paper|research|article)\s+(?:aims?|aimed|sought|seeks?|"
    r"examines?|examined|investigates?|investigated|explores?|explored)\b"
    r"|\bthe\s+(?:aim|purpose|objective)\s+of\s+th(?:is|e)\s+"
    r"(?:study|paper|research)\b"
    r"|هدفت\s+(?:هذه\s+)?الدراسة|تهدف\s+(?:هذه\s+)?الدراسة|سعت\s+الدراسة",
    re.IGNORECASE)

_PROBLEM: Final = re.compile(
    r"\blittle\s+is\s+known\b|\bremains?\s+(?:largely\s+)?unclear\b"
    r"|\bthere\s+is\s+a\s+(?:lack|dearth|paucity)\s+of\b|\bhas\s+been\s+overlooked\b"
    r"|ندرة\s+الدراسات|قلة\s+الدراسات|لم\s+تحظَ?\s+باهتمام|مشكلة\s+الدراسة",
    re.IGNORECASE)

_FINDINGS: Final = re.compile(
    r"\b(?:the\s+)?(?:results?|findings?|analysis)\s+"
    r"(?:show(?:ed|s)?|reveal(?:ed|s)?|indicate[sd]?|suggest(?:ed|s)?|"
    r"demonstrate[sd]?|found)\b"
    r"|\bwe\s+found\b|\bwas\s+(?:positively|negatively)\s+(?:associated|correlated)\b"
    r"|أظهرت\s+النتائج|كشفت\s+النتائج|توصلت\s+الدراسة|أشارت\s+النتائج",
    re.IGNORECASE)

_LIMITATIONS: Final = re.compile(
    r"\blimitations?\b|\bthis\s+study\s+is\s+limited\b|من\s+حدود\s+الدراسة|"
    r"محددات\s+الدراسة|قيود\s+الدراسة",
    re.IGNORECASE)

_GAPS: Final = re.compile(
    r"\bfuture\s+research\b|\bfurther\s+research\s+is\s+needed\b|"
    r"بحوث\s+مستقبلية|دراسات\s+مستقبلية|يُوصى\s+بإجراء",
    re.IGNORECASE)

# ═══════════════ حرّاسٌ يمنعان أشيع كذبتين في مصفوفة أدبيات ═══════════════

# **الأولى: «آثار للسعودية» ليست عيّنةً سعودية.** جملةٌ تتحدّث عمّن *تنفعه*
# النتيجة تصف قارئًا لا مبحوثًا؛ وأخذُ اسم البلد منها يجعل دراسةً على طلاب
# أمريكيين تُقرأ دراسةً سعودية — ثم تُكتب في قسمٍ عن السياق المحلّي.
_IMPLICATION_CLAUSE: Final = re.compile(
    r"\bimplications?\s+(?:for|to)\b|\brelevance\s+for\b|\brecommendations?\s+for\b"
    r"|\bimplications?\s+are\s+discussed\b|\bapplicable\s+to\b|\bgeneraliz\w+\s+to\b"
    r"|آثار\w*\s+(?:على|لـ)|دلالات\w*\s+(?:على|لـ)|توصيات\w*\s+(?:لـ|إلى)"
    r"|قابلة\s+للتعميم\s+على|يمكن\s+تعميم",
    re.IGNORECASE)

# **والثانية: من هم المبحوثون.** لا يُقرأ مجتمعٌ إلا من جملةٍ تقول صراحةً
# **مَن دُرس** — لا من جملةٍ ذكرت بلدًا عرضًا.
_PARTICIPANT_NOUN: Final = (
    r"(?:students?|undergraduates?|graduates?|participants?|respondents?|employees?|"
    r"workers?|teachers?|nurses?|physicians?|doctors?|patients?|managers?|"
    r"consumers?|customers?|adults?|adolescents?|children|firms?|companies?|"
    r"organi[sz]ations?|households?|families|"
    r"طلاب|طالب\w*|مشارك\w*|مستجيب\w*|موظف\w*|معلم\w*|ممرض\w*|مريض\w*|"
    r"مدير\w*|مستهلك\w*|عميل\w*|أسرة|أسر|شركة|شركات|مؤسسة|مؤسسات|فرد\w*)"
)
_PARTICIPANT_RE: Final = re.compile(_PARTICIPANT_NOUN, re.IGNORECASE)

_SAMPLE_CUE: Final = re.compile(
    r"\bsurveyed\b|\bsampled\b|\brecruited\b|\benrolled\b|\bcomprised\b|"
    r"\bconsisted\s+of\b|\bsample\s+of\b|\bsample\s+(?:size\s+)?(?:was|of)\b|"
    r"\ba\s+total\s+of\b|\bdata\s+were\s+collected\s+from\b|\bparticipants?\s+were\b|"
    r"شملت|بلغت\s+العينة|تكوّنت\s+العينة|تكونت\s+العينة|عينة\s+(?:من|قوامها)|"
    r"استُطلع|استطلعت|طُبّقت\s+على|أُجريت\s+على",
    re.IGNORECASE)

# السياق المكاني/الزماني — يُقرأ من جملة المبحوثين وحدها.
_CONTEXT_CUE: Final = re.compile(
    r"\b(?:in|at|from|across)\s+(?:the\s+)?"
    r"(?:[A-Z][\w'’-]+(?:\s+(?:of|the|and)?\s*[A-Z][\w'’-]+){0,3})"
    r"|\b(?:public|private)\s+(?:universit\w+|schools?|hospitals?|sectors?)\b"
    r"|في\s+" + _AR + r"[\w؀-ۿ]*(?:\s+" + _AR + r"[\w؀-ۿ]*){0,3}")

# **الكسر العشري يُنزع قبل البحث عن أرقام العيّنة.** درسٌ دفعه الإنتاج
# مرّتين: `0.003` كانت تُقرأ «003» عيّنةً مخترَعة، ثم `0,003` بالفاصلة
# اللاتينية بعد أول علاج. فيُنزع كل كسرٍ بأي فاصلة — عربية أو لاتينية أو
# نقطة — وجزؤه الكسري ليس عددَ مشاركين بحال.
_DECIMAL: Final = re.compile(r"\d+\s*[.,٫٬]\s*\d+")
_YEAR: Final = re.compile(r"^(?:1[89]|20)\d{2}$")
_SAMPLE_N: Final = re.compile(r"\b[Nn]\s*=\s*(\d{1,7})\b")
_SAMPLE_BEFORE_NOUN: Final = re.compile(
    r"\b(\d{1,7})\s+(?:\S+\s+){0,3}?" + _PARTICIPANT_NOUN, re.IGNORECASE)

_SENTENCE_SPLIT: Final = re.compile(r"(?<=[.!?؟])\s+|\n+")

# فاصلُ الألفاظ في قيمةٍ مركّبة. **وهو من عندنا لا من الورقة** — فيُفكّ قبل
# أن تُقابَل القيمة بالنصّ، وإلّا رُميت كلُّ قيمةٍ فيها لفظان.
VALUE_JOIN: Final = " · "

# الأعمدة التي يفحصها المستخرِج حين يكون المدى ملخّصًا أو نصًّا كاملًا.
# **وما ليس فيها لا يُملأ آليًّا أبدًا** — لا لأنه صعب، بل لأنه لا يُقرأ من
# ملخّصٍ بثقة: «المتغيّرات» و«الإطار المفاهيمي» يحتاجان الورقة كاملةً وقراءةَ
# إنسان، وملؤهما من ملخّصٍ اختراعٌ مرتّب.
EXAMINED_FIELDS: Final = (
    "objective", "problem", "theory", "design", "method", "population",
    "sample", "context", "measures", "analysis", "findings", "limitations", "gaps",
)


def sentences(text: str) -> list[str]:
    """جملٌ يُقرأ كلٌّ منها وحده — **لأن الحكم يقع داخل الجملة لا عبرها**.

    و«استطلعنا ٤٢٥ طالبًا أمريكيًّا. وللنتائج دلالاتٌ للسعودية» جملتان: من
    قرأهما واحدةً خرج بعيّنةٍ سعودية لم توجد.
    """
    return [part.strip() for part in _SENTENCE_SPLIT.split(text or "") if part.strip()]


def describes_this_study(sentence: str) -> bool:
    """جملةٌ تصف **هذه** الدراسة — لا ما يُوصى به ولا ما تنفعه النتيجة.

    وهو أخطر ما كُشف في تجربة هذا المستخرِج: «يُوصى بدراساتٍ **طولية**
    مستقبلًا» كانت تجعل تصميمَ دراسةٍ مقطعية «طوليًّا». فانقلب الحكم كلّه:
    التصميمُ خطأ، وحارسُ السببية المبنيّ عليه يُرفع عن دراسةٍ تحتاجه.
    """
    return not (_GAPS.search(sentence) or _IMPLICATION_CLAUSE.search(sentence))


def detect_design(text: str) -> tuple[str, str] | None:
    """تصميمُ الدراسة — **باللفظ الذي وُجد لا بتصنيفٍ نُسقطه**.

    والقراءة جملةً جملةً بترتيبها: أول جملةٍ تصف هذه الدراسة وتذكر تصميمًا
    هي التصميم. وداخل الجملة الأقوى ادّعاءً أولًا، فدراسةٌ تقول «تجربة
    عشوائية محكمة» لا تُصنَّف «مسحية» لأنها ذكرت استبانة.
    """
    for sentence in sentences(text) or [text]:
        if not describes_this_study(sentence):
            continue
        for key, pattern, _causal in _DESIGNS:
            match = pattern.search(sentence)
            if match:
                return key, match.group(0).strip()
    return None


# كلماتٌ لا تُضاف إلى وصف المبحوثين حين يُمدّ يسارًا — حروفُ جرٍّ وأفعالٌ
# رابطة لا تصف أحدًا، وإقحامها يجعل القيمة تُقرأ ركيكةً ثم يُشكّ فيها.
_GENERIC_PARTICIPANTS: Final = frozenset(
    "participant participants respondent respondents adult adults individual "
    "individuals مشارك مشاركا مشاركين مستجيب مستجيبا فرد فردا أفراد".split())

_PHRASE_STOP: Final = frozenset(
    "a an the of in at from and or we were was been being with among across "
    "included comprised consisted surveyed recruited enrolled total "
    "من في على و ثم أو التي الذي كانت كان بلغت شملت تكونت".split())


def participant_phrase(sentence: str) -> str | None:
    """وصفُ المبحوثين كما كُتب — **عبارةً لا كلمةً مبتورة**.

    و«طلاب جامعيون» أدقّ من «طلاب»، لكن المدّ محدود ومحكوم: كلمتان يسارًا
    ما لم تكونا رقمًا ولا حرف جرّ. والمدّ بلا حدٍّ يبتلع نصف الجملة فيصير
    عمودُ «المجتمع» جملةً كاملة تُقرأ نتيجة.
    """
    # **«مشاركون» ليست مجتمعًا، هي كلمةٌ تسدّ الخانة.** فتُقدَّم أول عبارةٍ
    # تسمّي المبحوثين تسميةً تُميّزهم — «معلمون»، «ممرضات»، «طلاب جامعيون» —
    # وتُترك الكلمة العامّة لآخر الأمر إن لم يُوجد غيرها.
    match = next((m for m in _PARTICIPANT_RE.finditer(sentence)
                  if m.group(0).lower() not in _GENERIC_PARTICIPANTS), None)
    if match is None:
        match = _PARTICIPANT_RE.search(sentence)
    if match is None:
        return None
    start, end = match.span()
    tail = re.match(r"\s+" + _PARTICIPANT_NOUN, sentence[end:], re.IGNORECASE)
    if tail:
        end += tail.end()
    head = sentence[:start].rstrip()
    for _ in range(2):
        word = re.search(r"([^\W\d_]+)\s*$", head)
        if word is None or word.group(1).lower() in _PHRASE_STOP:
            break
        start = len(head) - len(word.group(1))
        head = head[:start].rstrip()
    return sentence[start:end].strip() or None


def sample_size(sentence: str) -> str | None:
    """حجمُ العيّنة كما نطقت به الجملة — **رقمٌ مكتوب، لا رقمٌ محسوب**.

    ويشترط قرينةً: `N = 425`، أو رقمٌ يليه اسمُ مبحوثين، أو لفظُ عيّنةٍ ثم
    رقم. ورقمٌ مجرّد في جملةٍ ليس حجم عيّنة — قد يكون سنةً أو نسبةً أو عدد
    أسئلة، وكتابته في عمود «العيّنة» اختراعُ عددِ مشاركين.
    """
    body = numbers.normalise(sentence)
    for hit in numbers.find(body):
        body = body.replace(hit.excerpt, " ")
    body = _DECIMAL.sub(" ", body)

    explicit = _SAMPLE_N.search(body)
    if explicit and not _YEAR.match(explicit.group(1)):
        return explicit.group(1)
    before_noun = _SAMPLE_BEFORE_NOUN.search(body)
    if before_noun and not _YEAR.match(before_noun.group(1)):
        return before_noun.group(1)
    if _SAMPLE_CUE.search(body):
        for candidate in re.findall(r"(?<![\d.,])(\d{1,7})(?![\d.,])", body):
            if not _YEAR.match(candidate):
                return candidate
    return None


def describes_participants(sentence: str) -> bool:
    """هل تقول هذه الجملة **من دُرس**؟ — وليس من تنفعه النتيجة.

    فجملةُ الدلالات تُستبعد كلّها: هي عن قارئٍ لا عن مبحوث، ومن قرأ منها
    مجتمعًا أو سياقًا نسب إلى الدراسة عيّنةً لم تُجمع.
    """
    if _IMPLICATION_CLAUSE.search(sentence):
        return False
    return bool(_PARTICIPANT_RE.search(sentence)
                or _SAMPLE_CUE.search(sentence))


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def findings_in(passage: ReadPassage) -> list[Finding]:
    """كل ما تسنده هذه القطعة حرفًا — **ولا شيء تسنده قراءتنا لها**.

    والقيمة المكتوبة إمّا لفظٌ وُجد في النصّ وإمّا الجملة التي قالته؛ ولا
    إعادةَ صياغة: صياغتنا للجملة قد تقلب معناها، والباحث يراجع ما كتبناه
    لا ما قرأناه.

    وجُملُ «الدراسات المستقبلية» و«دلالات النتائج» تُعزل عن كل ما يصف هذه
    الدراسة: منهجُها وتصميمها ومجتمعها وسياقها. وتبقى مقروءةً لعمودَي
    «الفجوات» و«الحدود» — وهما ما قيلت لأجله.
    """
    text = passage.text
    if not text or not text.strip():
        return []
    out: list[Finding] = []
    lines = sentences(text)
    own = [s for s in lines if describes_this_study(s)] or []
    own_text = " ".join(own)

    design = detect_design(text)
    design_key = design[0] if design else None
    if design:
        sentence = next((s for s in own if design[1] in s), own_text)
        out.append(Finding("design", design[1], sentence, passage))

    for field_key, table in (("method", _METHODS), ("analysis", _ANALYSES)):
        hits: list[str] = []
        for _key, pattern in table:
            match = pattern.search(own_text)
            if match:
                hits.append(match.group(0).strip())
        parts = list(dict.fromkeys(hits))
        if parts:
            sentence = next((s for s in own if parts[0] in s), own_text)
            out.append(Finding(field_key, VALUE_JOIN.join(parts), sentence, passage))

    for field_key, pattern in (("theory", _THEORY), ("measures", _MEASURES)):
        match = pattern.search(own_text)
        if match:
            value = match.group(0).strip()
            sentence = next((s for s in own if value in s), own_text)
            out.append(Finding(field_key, value, sentence, passage))

    # الجُمل التي تُكتب كاملةً: القصد والمشكلة والنتائج والحدود والفجوات.
    # **وتُنسخ كما هي.** إعادةُ صياغةٍ في عمود «النتائج» أخطر من غيابها.
    for field_key, pattern, pool in (
        ("objective", _OBJECTIVE, own), ("problem", _PROBLEM, own),
        ("findings", _FINDINGS, own), ("limitations", _LIMITATIONS, lines),
        ("gaps", _GAPS, lines),
    ):
        sentence = next((s for s in pool if pattern.search(s)), None)
        if sentence:
            out.append(Finding(field_key, sentence, sentence, passage))

    # المجتمع والسياق والعيّنة — من جملة المبحوثين وحدها.
    for sentence in (s for s in own if describes_participants(s)):
        size = sample_size(sentence)
        if size and not any(f.field_key == "sample" for f in out):
            out.append(Finding("sample", size, sentence, passage))
        who = participant_phrase(sentence)
        if who and not any(f.field_key == "population" for f in out):
            out.append(Finding("population", who, sentence, passage))
        places = list(dict.fromkeys(
            m.group(0).strip() for m in _CONTEXT_CUE.finditer(sentence)))
        if places and not any(f.field_key == "context" for f in out):
            out.append(Finding("context", VALUE_JOIN.join(places), sentence, passage))

    return _drop_unsupported_causality(out, design_key)


def _drop_unsupported_causality(found: list[Finding],
                                design_key: str | None) -> list[Finding]:
    """**نتيجةٌ سببية من دراسةٍ لا تقيس السببية لا تُكتب آليًّا.**

    الدراسة المقطعية تقيس اقترانًا في لحظة؛ وعنوانها قد يقول «أثر كذا في
    كذا» لأن هذا ما يُنشر. فإن نُقل ذلك اللفظ إلى عمود «النتائج» صار في
    المصفوفة سببٌ لم يُقس — ثم يُكتب في المناقشة، ثم يُحكَّم.

    فتُحذف القيمة ويبقى العمود `missing` — يملؤه الباحث إن رأى، وهو الذي
    يقرأ الورقة ويعرف ما تسنده. **والصدق أولى من الاكتمال.**
    """
    if design_key not in _NON_CAUSAL_DESIGNS:
        return found
    return [f for f in found
            if not (f.field_key in ("findings", "objective", "problem")
                    and _CAUSAL_MARKERS.search(f.value_ar))]


def grounded(found: Sequence[Finding]) -> list[Finding]:
    """حاجزُ الاختلاق نفسه: **قيمةٌ لا يوجد نصُّها فيما قُرئ تُرمى**.

    ولا وضعَ «متساهل»: خطأٌ في نمطٍ يجعل النمط يلتقط ما ليس في النصّ، وهذا
    الحاجز هو ما يمنع أن يصل ذلك الخطأ الشاشة.

    والقيمة المركّبة تُفحص **جزءًا جزءًا**: «استبانة · مقابلات» لفظان
    وُجد كلٌّ منهما وحده، والفاصل بينهما من عندنا. وفحصُ العبارة كلّها
    نصًّا واحدًا كان يرمي كل قيمةٍ فيها لفظان — فتظهر الأعمدة فارغة ولا
    يُعرف لماذا.
    """
    kept: list[Finding] = []
    for item in found:
        if not quote_is_grounded(item.quote, item.passage.text):
            continue
        if all(quote_is_grounded(part, item.passage.text)
               for part in item.value_ar.split(VALUE_JOIN)):
            kept.append(item)
    return kept


# ═════════════════════ الكتابة في القاعدة ═════════════════════

@dataclass(slots=True)
class ExtractionOutcome:
    """حصيلةُ تشغيلةٍ على مرجعٍ واحد — **بما لم يُكتب كما بما كُتب**."""

    source_id: uuid.UUID
    scope: str
    filled: int = 0
    marked_missing: int = 0
    # خلايا لم تُمسّ لأن إنسانًا كتبها أو راجعها. **ولا تُدهس أبدًا.**
    left_to_the_researcher: int = 0
    fields: list[str] = field(default_factory=list)


async def _passages(session: AsyncSession, *, tenant_id: uuid.UUID,
                    scope: sc.ReadingScope,
                    abstract_rows: Sequence[SourceAbstract]) -> list[ReadPassage]:
    """ما يُقرأ فعلًا بهذا المدى — ولا حرفَ فوقه.

    و`metadata_only` تعيد لا شيء: عنوانٌ وسنةٌ لا يُقرأ منهما منهجٌ ولا
    عيّنة، ومن قرأ منهما فقد اخترع.
    """
    if scope.scope == sc.METADATA_ONLY:
        return []
    if scope.scope == sc.ABSTRACT_ONLY:
        # المفتاح (المرسِل، البصمة) لا البصمة وحدها: فهرسان أرسلا النصّ
        # نفسه صفّان، ونسبةُ الخلية إلى أحدهما بلا تمييزٍ نسبةٌ إلى من لم
        # يُقرأ منه.
        rows = {(row.provider, row.content_hash): row.id for row in abstract_rows}
        return [ReadPassage(text=record.text,
                            abstract_id=record.stored_id
                            or rows.get((record.provider, record.content_hash)))
                for record in scope.abstracts]
    if scope.file_id is None:
        return []
    chunks = (await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.tenant_id == tenant_id,
               DocumentChunk.file_id == scope.file_id)
        .order_by(DocumentChunk.seq)
    )).scalars().all()
    # **رقمُ الصفحة من المُقطِّع أو لا يكون.** و`chunk.seq` ترتيبٌ لا صفحة.
    return [ReadPassage(text=chunk.text, page=chunk.page_number,
                        section=chunk.section_path) for chunk in chunks]


async def materialize_abstracts(session: AsyncSession, *, tenant_id: uuid.UUID,
                                source: Source,
                                stored: Sequence[SourceAbstract]) -> list[SourceAbstract]:
    """يُثبِّت ملخّصات هذا المرجع صفوفًا منسوبة — **عند استعمالها لا قبله**.

    فالقيمة المستخرَجة تُراجَع بمقابلتها بالنصّ الذي قيلت منه؛ وذلك النصّ
    إن بقي في `raw_metadata` تغيّر بأول تحديثٍ للفهرس، فتُراجَع القيمة
    بنصٍّ غير الذي قالها. فيُنسخ وقت الاستعمال بوقته ومرسِله ومعرّفه.

    **ولا يُطوى ملخّصان في واحد**: الوحدانية على (المرجع، الفهرس، البصمة).
    """
    known = {(row.provider, row.content_hash) for row in stored}
    fresh = list(stored)
    for record in sc.abstracts_of(source, stored):
        key = (record.provider, record.content_hash)
        if key in known or record.retrieved_at is None:
            continue
        known.add(key)
        row = SourceAbstract(
            tenant_id=tenant_id, source_id=source.id, provider=record.provider,
            provider_identifier=record.provider_identifier, text=record.text,
            content_hash=record.content_hash, retrieved_at=record.retrieved_at)
        session.add(row)
        fresh.append(row)
    if len(fresh) != len(stored):
        await session.flush()
    return fresh


def _locator_for(scope: str, passage: ReadPassage) -> str | None:
    """موضعُ الشاهد — **وللملخّص كلمةٌ واحدة لا رقم**."""
    if scope == sc.ABSTRACT_ONLY:
        return sc.ABSTRACT_LOCATOR
    if scope != sc.FULL_TEXT:
        return None
    if passage.page is not None:
        return f"ص. {passage.page}"
    return passage.section or None


async def extract_for_source(session: AsyncSession, *, tenant_id: uuid.UUID,
                             project_id: uuid.UUID, source: Source,
                             scope: sc.ReadingScope, actor_user_id: uuid.UUID,
                             stored_abstracts: Sequence[SourceAbstract] = (),
                             ) -> ExtractionOutcome:
    """يقرأ ما هو متاحٌ لهذا المرجع ويكتب مرشّحاته — **ولا يدهس إنسانًا**.

    وثلاث قواعد تحكم الكتابة:

    **ما كتبه الباحث بيده لا يُمسّ.** تشغيلةٌ آلية تصحّح ما صحّحه إنسان
    تُعلّمه ألّا يصحّح — ويقرأ في الشاشة قيمةً كتبها هو وقد تبدّلت.

    **وما راجعه الباحث لا يُمسّ.** خليةٌ اعتُمدت أو رُفضت حُكم فيها؛ وإعادةُ
    كتابتها تمحو الحكم وتبقي الختم — وهي بالضبط ما يمنعه قيدُ القاعدة.

    **وما فُحص ولم يُوجد يُكتب `missing`** — لا يُترك فراغًا. والفرق ليس
    شكليًّا: الفراغ يُقرأ «لم يُنظر بعد»، و`missing` تُقرأ «نُظر فلم تذكره
    الورقة» — والثانية وحدها فجوةٌ يعرف الباحث أنّ عليه أن يعالجها.
    """
    outcome = ExtractionOutcome(source_id=source.id, scope=scope.scope)
    abstract_rows = list(stored_abstracts)
    if scope.scope == sc.ABSTRACT_ONLY:
        abstract_rows = await materialize_abstracts(
            session, tenant_id=tenant_id, source=source, stored=abstract_rows)
        # المدى نفسه لا يتغيّر بتثبيت الملخّصات — تتغيّر نسبتُها وحدها. وإعادةُ
        # حسابه هنا كانت تقلبه إلى `full_text` لو صادف أن للمرجع ملفًّا.
        scope = dataclasses.replace(
            scope, abstracts=tuple(sc.abstracts_of(source, abstract_rows)))

    passages = await _passages(session, tenant_id=tenant_id, scope=scope,
                               abstract_rows=abstract_rows)
    if not passages:
        return outcome

    best: dict[str, Finding] = {}
    for passage in passages:
        for finding in grounded(findings_in(passage)):
            best.setdefault(finding.field_key, finding)

    existing = {
        cell.field_key: cell
        for cell in (await session.execute(
            select(LiteratureMatrixCell).where(
                LiteratureMatrixCell.tenant_id == tenant_id,
                LiteratureMatrixCell.project_id == project_id,
                LiteratureMatrixCell.source_id == source.id)
        )).scalars().all()
    }

    now = dt.datetime.now(dt.UTC)
    for field_key in EXAMINED_FIELDS:
        cell = existing.get(field_key)
        if cell is not None and not _is_replaceable(cell):
            outcome.left_to_the_researcher += 1
            continue
        finding = best.get(field_key)
        if cell is None:
            cell = LiteratureMatrixCell(
                tenant_id=tenant_id, project_id=project_id, source_id=source.id,
                field_key=field_key, updated_by=actor_user_id)
            session.add(cell)
        cell.source_scope = scope.scope
        # **ما لم يكتبه إنسان يبقى مرشَّحًا.** والقيد في القاعدة يمنع أن
        # يُكتب معتمَدًا بلا مُعتمِدٍ يُسمّى — وهذا هو ما يُشمَل به.
        cell.extraction_method = "model"
        cell.verification_status = "unverified"
        cell.verified_by, cell.verified_at = None, None
        cell.updated_by = actor_user_id
        cell.updated_at = now
        if finding is None:
            # الغياب غيابٌ لا فراغٌ يُملأ — ولا يحمل قيمةً ولا شاهدًا.
            cell.cell_state = "missing"
            cell.value_ar = None
            cell.evidence_quote = None
            cell.evidence_locator = None
            cell.evidence_page = None
            cell.evidence_section = None
            cell.source_abstract_id = None
            cell.source_file_id = None
            outcome.marked_missing += 1
            continue
        cell.cell_state = "needs_review"
        cell.value_ar = finding.value_ar[:4000]
        cell.evidence_quote = finding.quote[:2000]
        cell.evidence_locator = _locator_for(scope.scope, finding.passage)
        cell.evidence_page = (finding.passage.page
                              if scope.scope == sc.FULL_TEXT else None)
        cell.evidence_section = (finding.passage.section
                                 if scope.scope == sc.FULL_TEXT else None)
        cell.source_abstract_id = (finding.passage.abstract_id
                                   if scope.scope == sc.ABSTRACT_ONLY else None)
        cell.source_file_id = scope.file_id if scope.scope == sc.FULL_TEXT else None
        outcome.filled += 1
        outcome.fields.append(field_key)

    await session.flush()
    return outcome


def _is_replaceable(cell: LiteratureMatrixCell) -> bool:
    """خليةٌ تجوز إعادةُ كتابتها آليًّا: كتبها آليٌّ ولم يحكم فيها إنسان."""
    return (cell.extraction_method == "model"
            and cell.verification_status == "unverified")


__all__ = [
    "EXAMINED_FIELDS",
    "ExtractionOutcome",
    "Finding",
    "ReadPassage",
    "VALUE_JOIN",
    "describes_participants",
    "describes_this_study",
    "detect_design",
    "extract_for_source",
    "findings_in",
    "grounded",
    "materialize_abstracts",
    "participant_phrase",
    "sample_size",
    "sentences",
]
