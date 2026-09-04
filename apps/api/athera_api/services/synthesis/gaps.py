"""الفجوات المحتملة | Gap candidates — the dangerous one (PUBRIVA).

**هذه أخطر وحدةٍ في المنتج.** ومقياس نجاحها ليس عدد الفجوات التي تجدها، بل
عدد الفجوات الزائفة التي **ترفض** أن تقولها. فمنصّةٌ تُخرج لكل باحثٍ خمس
فجواتٍ جاهزة تصير مصنع دعاوى، وتُكتب دعاواها في أوراقٍ تُنشر.

## ثلاث قواعد تحكم كل سطرٍ هنا

**١) الدعوى محدودةٌ بما بُحث.** لا «لا توجد دراسات». أكبر ما يجوز قوله:
«لم تظهر دراسةٌ تغطّي هذا السياق **ضمن مجموعة المراجع الحالية**»، ومعه عدد
المراجع المنظور فيها والفهارس التي جاءت منها. وكلُّ نصٍّ يُبنى هنا يمرّ
بدالّة `bounded` التي تُلحق الحدّ بالدعوى — فلا تُكتب دعوى بلا حدّها.

**٢) غيابُ الذكر ليس غيابًا للشيء.** ملخّصٌ لم يذكر نظرية لا يعني أن
الدراسة بلا نظرية؛ يعني أن الملخّص لم يذكرها. فما لم يُقرأ نصًّا كاملًا لا
يُستنتج منه غيابُ نظرية أبدًا.

**٣) العجز يُعلَن باسمه.** حين لا تكفي المعطيات للحكم لا تُرجع هذه الوحدة
صمتًا: تُرجع `NotAssessed` بحكم `insufficient_information` — وهي مفردة
محرّك القواعد نفسها (`research_brain/rules.py`). وقاعدةٌ لا تجد ما تفحصه
فتسكت تُقرأ «لا فجوة هنا»، وهو جوابٌ لم يُفحص.

## والقوّة موصوفة ومسقوفة

سقفُ القوّة يُحسب من حجم المجموعة وعمق القراءة، ولا تتجاوزه فجوةٌ مهما بدت
قويّة. فمجموعةٌ من ثلاث دراساتٍ لم يُقرأ منها إلا الملخّصات لا تُنتج
«مرشَّحًا مسنودًا» — مهما تكرّر النمط فيها.

## والتعارض لا يصير فجوةً من جنسٍ آخر تلقائيًّا

دراستان تختلفان تُنتجان مرشَّح «أدلة متعارضة» **وحده**، مرتبطًا بتعارضه
بعينه. ولا يُشتقّ منه «علاقة قليلة الدرس» ولا «حاجة إلى تكرار» — الاختلاف
حالُ معرفةٍ تُعرض، لا فجوةٌ تُعلَن.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field, replace
from typing import Final

from . import textual
from .contradictions import ContradictionProposal
from .corpus import CorpusSnapshot
from .vocab import strength_at_most

# **حدودٌ عددية مكتوبة مرّة، ومشروحة.** ورقمٌ سحريّ في شرطٍ داخل دالّة
# يصير عرفًا لا يعرف أحدٌ لمَ هو هناك، فيُرفع يومًا لأن أحدًا لم يعترض.

# أقلّ مجموعةٍ يُحكم عليها بحكمٍ عامّ. ودونها لا نوع فجوةٍ عامّ يُقترح
# أصلًا — **الاختبار السلبي الأول**: مقالتان لا تكفيان لفجوةٍ واسعة.
MIN_CORPUS_FOR_BROAD_CLAIM: Final = 5

# أنواعٌ لا تُقال إلا عن مجموعةٍ معتبرة: كلٌّ منها دعوى عن حالِ حقلٍ لا عن
# حالِ قائمة.
BROAD_GAP_TYPES: Final = ("theory_gap", "understudied_relationship",
                          "replication_need")

# أقلّ عددٍ يُقال عنه «تركّز منهجيّ» — واثنتان تشابهتا صدفةٌ لا نمط.
MIN_FOR_CONCENTRATION: Final = 3

# سنواتٌ بعدها تُسمّى المجموعة قديمة. ولا تعني أن الحقل توقّف: تعني أن
# **هذه المجموعة** لم تُحدَّث.
STALE_AFTER_YEARS: Final = 5

# السياقات التي يُسأل عنها. وهي **سؤالٌ يُطرح على المجموعة**، لا اكتشافًا:
# المنصّة لا تعرف أيّ سياقٍ يهمّ هذا الباحث حتى يقوله.
DEFAULT_WATCHED_CONTEXTS: Final = ("السعودية",)


@dataclass(frozen=True, slots=True)
class GapSourceRef:
    """مرجعٌ في مدى الفجوة — بدوره وبخليّته إن وُجدت."""

    source_id: uuid.UUID
    role: str
    evidence_scope: str
    matrix_cell_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class GapProposal:
    """فجوةٌ **محتملة** — بحدودها معلنةً معها."""

    gap_type: str
    description_ar: str
    why_suggested_ar: str
    known_limitations_ar: str
    strength: str
    sources_considered: int
    search_scope: dict
    source_scope_distribution: dict[str, int]
    sources: tuple[GapSourceRef, ...] = ()
    contradiction_key: tuple[uuid.UUID, uuid.UUID] | None = None


@dataclass(frozen=True, slots=True)
class NotAssessed:
    """**عجزٌ يُعلَن باسمه** — بمفردة محرّك القواعد: `insufficient_information`.

    وهي أهمّ ما تُخرجه هذه الوحدة: تقولُ للباحث «لم أستطع الحكم، ولهذا
    السبب» بدل أن تسكت فيقرأ صمتها «لا فجوة».
    """

    gap_type: str
    verdict: str
    reason_ar: str


@dataclass(frozen=True, slots=True)
class GapAssessment:
    """حصيلةُ النظر — ما اقتُرح **وما تعذّر الحكم فيه**، معًا."""

    proposals: tuple[GapProposal, ...] = ()
    not_assessed: tuple[NotAssessed, ...] = ()
    corpus_size: int = 0
    notes_ar: tuple[str, ...] = field(default_factory=tuple)


def bounded(claim: str, corpus: CorpusSnapshot) -> str:
    """**تُلحق الحدَّ بالدعوى، فلا تخرج دعوى بلا حدّها.**

    وهذه الدالّة هي الفرق بين «لم تظهر دراسة عن كذا» و«لا توجد دراسة عن
    كذا»: الأولى وصفٌ لقائمةٍ عددها معلوم، والثانية دعوى عن العالم.
    """
    indexes = "، ".join(corpus.registries) if corpus.registries else "غير مسجَّلة"
    tail = (
        f" — وذلك ضمن مجموعة المراجع الحالية وحدها: {corpus.size} دراسةً مُدرَجة، "
        f"مصادرها {indexes}، قُرئ محتوى {corpus.content_read_count} منها. "
        "ولم يُجرِ النظام بحثًا منهجيًّا في الفهارس، فما لم يظهر هنا قد يكون "
        "موجودًا خارج هذه المجموعة."
    )
    if corpus.saved_only_count:
        tail += (f" وفي البحث {corpus.saved_only_count} مرجعًا محفوظًا لم يُفرَز "
                 "بعد، وقد يغيّر فرزُها هذه الصورة.")
    return claim + tail


def strength_ceiling(corpus: CorpusSnapshot) -> str:
    """سقفُ ما يجوز ادّعاؤه على هذه المجموعة — **يُفرض ولا يُرجى**.

    ثلاثةٌ تُقرأ معًا: كم دراسة، وكم منها قُرئ محتواها، وكم قُرئ نصًّا
    كاملًا. ومجموعةٌ كبيرةٌ لم يُقرأ منها شيء ليست أقوى من صغيرةٍ قُرئت.
    """
    if corpus.size < MIN_FOR_CONCENTRATION or corpus.content_read_count == 0:
        return "weak_signal"
    if corpus.size < MIN_CORPUS_FOR_BROAD_CLAIM or corpus.full_text_count < 2:
        return "emerging_pattern"
    return "supported_candidate"


def _refs(corpus: CorpusSnapshot, *, supporting: tuple[uuid.UUID, ...] = (),
          contradicting: tuple[uuid.UUID, ...] = (),
          field_key: str | None = None) -> tuple[GapSourceRef, ...]:
    """كلُّ المجموعة تُسجَّل: المُسنِد والمعارض **ومن نُظر فيه ولم يكن أيّهما**.

    وإسقاط الثالث يجعل الفجوة تبدو أوسع مما نُظر فيه — وهو أكثر ما يضخّم
    دعوى بلا كذبةٍ صريحة.
    """
    out: list[GapSourceRef] = []
    for study in corpus.studies:
        if study.source_id in supporting:
            role = "supporting"
        elif study.source_id in contradicting:
            role = "contradicting"
        else:
            role = "considered"
        cell = study.stated(field_key) if field_key else None
        out.append(GapSourceRef(
            source_id=study.source_id, role=role,
            evidence_scope=cell.source_scope if cell else study.reading_scope,
            matrix_cell_id=cell.cell_id if cell else None))
    return tuple(out)


# ═══════════════════ القواعد، قاعدةً قاعدة ═══════════════════

def _context_rule(corpus: CorpusSnapshot, watched: tuple[str, ...]
                  ) -> tuple[list[GapProposal], list[NotAssessed]]:
    """سياقٌ لم يظهر في المجموعة — **الاختبار السلبي الثالث**.

    ودعوى الغياب هنا عن المجموعة لا عن العالم؛ وقوّتها لا تتجاوز «إشارة
    ضعيفة» أبدًا مهما كبرت المجموعة: غيابُ شيءٍ من قائمةٍ جمعها باحثٌ بنفسه
    ليس دليلًا على شيءٍ في الحقل.
    """
    proposals: list[GapProposal] = []
    unassessed: list[NotAssessed] = []

    recorded = [
        (study, textual.country_in(study.text_of("context"),
                                   study.text_of("population", "sample")))
        for study in corpus.studies
    ]
    with_context = [row for row in recorded if row[1] is not None]
    if not with_context:
        # **لا يُحكم على تغطيةٍ لم تُسجَّل.** مصفوفةٌ خاليةُ أعمدة السياق لا
        # تقول «لا سياق سعودي»؛ تقول «لم يُسجَّل سياق أيّ دراسة».
        unassessed.append(NotAssessed(
            gap_type="context_gap",
            verdict="insufficient_information",
            reason_ar=(
                "لم يُسجَّل بلدٌ أو سياقٌ لأيّ دراسة في المصفوفة، فلا يمكن الحكم "
                "على تغطية السياق. **وغيابُ التسجيل ليس غيابًا للسياق**: أكمِل "
                "عمودَي «السياق» و«المجتمع» ثم أعِد النظر.")))
        return proposals, unassessed

    present = {country for _study, country in with_context}
    for wanted in watched:
        if wanted in present:
            continue
        proposals.append(GapProposal(
            gap_type="context_gap",
            description_ar=bounded(
                f"لم تظهر دراسةٌ سياقها «{wanted}» بين الدراسات التي سُجِّل "
                f"سياقها ({len(with_context)} من {corpus.size})", corpus),
            why_suggested_ar=(
                f"قُرئ عمودا «السياق» و«المجتمع» لـ{len(with_context)} دراسة، "
                f"وظهرت فيها هذه السياقات: {'، '.join(sorted(present))}. "
                f"ولم يظهر «{wanted}» بينها."),
            known_limitations_ar=(
                f"هذه ملاحظةٌ على قائمةٍ جمعها الباحث، لا مسحٌ للحقل. و"
                f"{corpus.size - len(with_context)} دراسةً لم يُسجَّل سياقها "
                "أصلًا وقد تكون منه. ولا يجوز أن تُكتب هذه الملاحظة في ورقةٍ "
                "بصيغة «لا توجد دراسات» — الصيغة الصحيحة أنها لم تظهر في "
                "مجموعة المراجع هذه."),
            # **سقفٌ ثابت.** غيابُ سياقٍ من قائمةٍ لا يترقّى بكِبَر القائمة.
            strength="weak_signal",
            sources_considered=corpus.size,
            search_scope=corpus.search_scope(),
            source_scope_distribution=corpus.scope_distribution,
            sources=_refs(corpus, field_key="context")))
    return proposals, unassessed


def _theory_rule(corpus: CorpusSnapshot
                 ) -> tuple[list[GapProposal], list[NotAssessed]]:
    """**الاختبار السلبي الثاني**: غيابُ ذكر النظرية ليس غيابًا للنظرية.

    فلا تُقترح فجوةُ نظريةٍ إلا من قراءةِ نصٍّ كامل: من قرأ الورقة كاملةً
    وسجّل أن نظريةً لم تُذكر قال شيئًا؛ ومن قرأ ملخّصًا لم يقل شيئًا عن
    نظرية الورقة.
    """
    proposals: list[GapProposal] = []
    unassessed: list[NotAssessed] = []

    full_text_reads = [
        study for study in corpus.studies
        if (cell := study.cell("theory")) is not None
        and cell.source_scope == "full_text"
    ]
    if corpus.size < MIN_CORPUS_FOR_BROAD_CLAIM:
        unassessed.append(NotAssessed(
            gap_type="theory_gap",
            verdict="insufficient_information",
            reason_ar=(
                f"المجموعة {corpus.size} دراسةً فقط، و{MIN_CORPUS_FOR_BROAD_CLAIM} "
                "هي أقلُّ ما يُحكم عليه بحكمٍ عامّ في هذه الطبقة. وفجوةٌ نظرية "
                "دعوى عن حال حقلٍ كامل، لا عن حال قائمةٍ قصيرة.")))
        return proposals, unassessed
    if not full_text_reads:
        unassessed.append(NotAssessed(
            gap_type="theory_gap",
            verdict="insufficient_information",
            reason_ar=(
                "لم يُقرأ عمود «النظرية» من نصٍّ كامل في أيّ دراسة. **وغيابُ ذكر "
                "النظرية في الملخّص ليس غيابًا للنظرية في الورقة**: أكثر "
                "الملخّصات لا تذكر إطارها النظري أصلًا. فلا يُستنتج من صمتها شيء.")))
        return proposals, unassessed

    silent = [study for study in full_text_reads
              if (cell := study.cell("theory")) is not None
              and cell.cell_state == "missing"]
    if len(silent) * 2 < len(full_text_reads):
        return proposals, unassessed

    proposals.append(GapProposal(
        gap_type="theory_gap",
        description_ar=bounded(
            f"من بين {len(full_text_reads)} دراسةً قُرئ نصّها كاملًا، "
            f"{len(silent)} لم تُصرّح بإطارٍ نظري في المصفوفة", corpus),
        why_suggested_ar=(
            "التسجيل هنا جاء من قراءة نصٍّ كامل لا من ملخّص، فهو قولٌ عن الورقة "
            "نفسها. وضعفُ التأطير النظري في مجموعةٍ من الدراسات ملاحظةٌ تستحق "
            "الفحص، لا نتيجة."),
        known_limitations_ar=(
            "قد تكون الأوراق مؤطَّرة نظريًّا ولم يُسجَّل ذلك في المصفوفة؛ ومن لم "
            "يُقرأ نصّه كاملًا خارج هذا الحساب أصلًا. ولا تُكتب هذه الملاحظة "
            "دعوى بأن الحقل بلا نظرية."),
        strength=strength_at_most("emerging_pattern", strength_ceiling(corpus)),
        sources_considered=corpus.size,
        search_scope=corpus.search_scope(),
        source_scope_distribution=corpus.scope_distribution,
        sources=_refs(corpus,
                      supporting=tuple(s.source_id for s in silent),
                      field_key="theory")))
    return proposals, unassessed


def _method_rule(corpus: CorpusSnapshot
                 ) -> tuple[list[GapProposal], list[NotAssessed]]:
    """**الاختبار السلبي الخامس**: تركّزٌ منهجيّ في هذه المجموعة، لا برهانٌ
    على أن الدراسات الطولية غير موجودة في العالم."""
    proposals: list[GapProposal] = []
    unassessed: list[NotAssessed] = []

    families: dict[str, list[uuid.UUID]] = {}
    for study in corpus.studies:
        family = textual.design_family(study.text_of("design"),
                                       study.text_of("method"))
        if family:
            families.setdefault(family, []).append(study.source_id)

    counted = sum(len(v) for v in families.values())
    if counted < MIN_FOR_CONCENTRATION:
        unassessed.append(NotAssessed(
            gap_type="method_gap",
            verdict="insufficient_information",
            reason_ar=(
                f"لم يُسجَّل تصميمٌ مقروء إلا لـ{counted} دراسة، و"
                f"{MIN_FOR_CONCENTRATION} هي أقلُّ ما يُسمّى تركّزًا. وأقلُّ من "
                "ذلك تشابهُ صدفةٍ لا نمط.")))
        return proposals, unassessed
    if len(families) != 1:
        return proposals, unassessed

    family, members = next(iter(families.items()))
    proposals.append(GapProposal(
        gap_type="method_gap",
        description_ar=bounded(
            f"كلُّ الدراسات التي سُجِّل تصميمها ({len(members)} دراسة) من أسرة "
            f"«{family}»، ولم تظهر أسرةُ تصميمٍ أخرى", corpus),
        why_suggested_ar=(
            f"قُرئ عمودا «التصميم» و«المنهج» فظهرت أسرةٌ واحدة: «{family}». "
            "وتركّزُ منهجٍ واحد في مجموعةٍ يحدّ ما يمكن استنتاجه منها — "
            "فرصةٌ منهجية محتملة، لا نقصٌ في الحقل."),
        known_limitations_ar=(
            f"هذا تركّزٌ **في هذه المجموعة**، وليس دليلًا على أن دراساتٍ من "
            f"أسرٍ أخرى غير موجودة في الحقل: قائمةُ الباحث تعكس ما وجده "
            f"وحفظه. و{corpus.size - len(members)} دراسةً لم يُسجَّل تصميمها."),
        strength=strength_at_most("emerging_pattern", strength_ceiling(corpus)),
        sources_considered=corpus.size,
        search_scope=corpus.search_scope(),
        source_scope_distribution=corpus.scope_distribution,
        sources=_refs(corpus, supporting=tuple(members), field_key="design")))
    return proposals, unassessed


def _temporal_rule(corpus: CorpusSnapshot, *, today: dt.date
                   ) -> tuple[list[GapProposal], list[NotAssessed]]:
    years = [s.publication_year for s in corpus.studies if s.publication_year]
    if len(years) < MIN_FOR_CONCENTRATION:
        return [], [NotAssessed(
            gap_type="temporal_gap",
            verdict="insufficient_information",
            reason_ar=("سنواتُ النشر مسجَّلة لأقلّ من ثلاث دراسات، فلا يُحكم على "
                       "حداثة المجموعة."))]
    newest = max(years)
    if today.year - newest < STALE_AFTER_YEARS:
        return [], []
    return [GapProposal(
        gap_type="temporal_gap",
        description_ar=bounded(
            f"أحدثُ دراسةٍ في المجموعة نُشرت سنة {newest}، أي قبل "
            f"{today.year - newest} سنة", corpus),
        why_suggested_ar=(
            "المجموعة لا تحمل عملًا حديثًا؛ وقد يكون في الحقل ما استجدّ ولم "
            "يدخل هذه القائمة بعد."),
        known_limitations_ar=(
            "هذه ملاحظةٌ على تاريخ ما جُمع، لا على نشاط الحقل. والأرجح أنها "
            "تُصلَح ببحثٍ جديد في الفهارس لا بورقةٍ جديدة."),
        strength="weak_signal",
        sources_considered=corpus.size,
        search_scope=corpus.search_scope(),
        source_scope_distribution=corpus.scope_distribution,
        sources=_refs(corpus))], []


def _measurement_rule(corpus: CorpusSnapshot
                      ) -> tuple[list[GapProposal], list[NotAssessed]]:
    """تباينُ المقاييس — ملاحظةٌ على قابلية المقارنة، لا نقصٌ في الحقل."""
    recorded = [(s.source_id, textual.terms(s.text_of("measures")))
                for s in corpus.studies if s.stated("measures")]
    if len(recorded) < MIN_FOR_CONCENTRATION:
        return [], [NotAssessed(
            gap_type="measurement_gap",
            verdict="insufficient_information",
            reason_ar=("عمود «المقاييس» مسجَّلٌ لأقلّ من ثلاث دراسات، فلا يُحكم "
                       "على تجانس القياس."))]
    shared = set.intersection(*[set(t) for _sid, t in recorded]) if recorded else set()
    if shared:
        return [], []
    return [GapProposal(
        gap_type="measurement_gap",
        description_ar=bounded(
            f"لم يظهر مقياسٌ مشترك بين الدراسات التي سُجِّلت مقاييسها "
            f"({len(recorded)} دراسة)", corpus),
        why_suggested_ar=(
            "اختلافُ أدوات القياس بين الدراسات يجعل مقارنة نتائجها محدودة — "
            "وهذه ملاحظةٌ على قابلية المقارنة داخل هذه المجموعة."),
        known_limitations_ar=(
            "قد تكون الأدوات نفسها مكتوبةً بأسماء مختلفة في المصفوفة، فيبدو "
            "الاختلاف أكبر مما هو. والأصل مراجعةُ الأعمدة قبل البناء على هذا."),
        strength="weak_signal",
        sources_considered=corpus.size,
        search_scope=corpus.search_scope(),
        source_scope_distribution=corpus.scope_distribution,
        sources=_refs(corpus, supporting=tuple(sid for sid, _t in recorded),
                      field_key="measures"))], []


def _contradiction_rule(corpus: CorpusSnapshot,
                        found: tuple[ContradictionProposal, ...]
                        ) -> list[GapProposal]:
    """**الاختبار السلبي الرابع**: الاختلاف يُنتج «أدلة متعارضة» وحدها.

    ولا يُشتقّ منه نوعٌ آخر تلقائيًّا: «حاجة إلى تكرار» و«علاقة قليلة
    الدرس» دعويان مستقلّتان لهما شروطهما، ولا تُستنتجان من أن دراستين
    اختلفتا.
    """
    out: list[GapProposal] = []
    for item in found:
        pair = (item.side_a.source_id, item.side_b.source_id)
        out.append(GapProposal(
            gap_type="contradictory_evidence",
            description_ar=bounded(
                f"دراستان في المجموعة تقولان قولين مختلفين على البناءات نفسها: "
                f"«{item.side_a.result_ar}» مقابل «{item.side_b.result_ar}»", corpus),
            why_suggested_ar=item.context_explanation_ar,
            known_limitations_ar=(
                "**اختلافُ نتيجتين ليس فجوةً بذاته**، وليس حكمًا على أيٍّ من "
                "الدراستين: قد تكون كلتاهما صحيحة في سياقها. وقبل عدّ هذا فجوةً "
                "تُبنى عليها ورقة، راجِع أعمدة السياق والمجتمع والقياس للطرفين."),
            strength=strength_at_most("weak_signal", strength_ceiling(corpus)),
            sources_considered=corpus.size,
            search_scope=corpus.search_scope(),
            source_scope_distribution=corpus.scope_distribution,
            sources=_refs(corpus, contradicting=pair, field_key="findings"),
            contradiction_key=pair))
    return out


def assess_gaps(corpus: CorpusSnapshot, *,
                contradictions: tuple[ContradictionProposal, ...] = (),
                watched_contexts: tuple[str, ...] = DEFAULT_WATCHED_CONTEXTS,
                today: dt.date | None = None) -> GapAssessment:
    """ينظر في المجموعة ويقول ما وجده **وما عجز عنه**.

    و**الاختبار السلبي الأول** هنا: مجموعةٌ دون الحدّ لا تُنتج نوعًا عامًّا
    واحدًا، ويُعلَن السبب لكل نوعٍ امتُنع عنه — لا يُسكت عنه.
    """
    day = today or dt.datetime.now(dt.UTC).date()
    if corpus.size == 0:
        return GapAssessment(
            not_assessed=(NotAssessed(
                gap_type="context_gap", verdict="insufficient_information",
                reason_ar=("لا دراسةَ مُدرَجة في هذا البحث بعد. والفجوة تُقاس على "
                           "ما نُظر فيه، ولا شيء نُظر فيه.")),),
            corpus_size=0,
            notes_ar=("افرِز مراجعك أولًا: المصفوفة والفجوات تُبنيان على "
                      "المُدرَجة وحدها.",))

    proposals: list[GapProposal] = []
    unassessed: list[NotAssessed] = []

    for rule in (_context_rule,):
        made, missed = rule(corpus, watched_contexts)
        proposals.extend(made)
        unassessed.extend(missed)
    for rule in (_theory_rule, _method_rule, _measurement_rule):
        made, missed = rule(corpus)
        proposals.extend(made)
        unassessed.extend(missed)
    made, missed = _temporal_rule(corpus, today=day)
    proposals.extend(made)
    unassessed.extend(missed)

    proposals.extend(_contradiction_rule(corpus, contradictions))

    # **الحدّ العامّ يُطبَّق بعد كل قاعدة، لا داخلها وحدها.** حارسٌ ثانٍ عمدًا:
    # قاعدةٌ تُضاف غدًا وتنسى الحدّ لا تمرّ من هنا.
    if corpus.size < MIN_CORPUS_FOR_BROAD_CLAIM:
        blocked = [p for p in proposals if p.gap_type in BROAD_GAP_TYPES]
        for item in blocked:
            unassessed.append(NotAssessed(
                gap_type=item.gap_type, verdict="insufficient_information",
                reason_ar=(
                    f"المجموعة {corpus.size} دراسةً، ودون "
                    f"{MIN_CORPUS_FOR_BROAD_CLAIM} لا يُقال حكمٌ عامّ عن حقل.")))
        proposals = [p for p in proposals if p.gap_type not in BROAD_GAP_TYPES]

    # وسقفُ القوّة يُفرض على كل مقترحٍ مرّةً أخيرة — حارسٌ ثانٍ للسبب نفسه.
    ceiling = strength_ceiling(corpus)
    proposals = [
        replace(item, strength=strength_at_most(item.strength, ceiling))
        for item in proposals
    ]
    proposals.sort(key=lambda p: (p.gap_type, p.description_ar))
    seen: set[str] = set()
    unique_missed: list[NotAssessed] = []
    for item in unassessed:
        if item.gap_type in seen:
            continue
        seen.add(item.gap_type)
        unique_missed.append(item)
    unique_missed.sort(key=lambda n: n.gap_type)

    return GapAssessment(
        proposals=tuple(proposals),
        not_assessed=tuple(unique_missed),
        corpus_size=corpus.size,
        notes_ar=(),
    )


__all__ = [
    "BROAD_GAP_TYPES",
    "DEFAULT_WATCHED_CONTEXTS",
    "MIN_CORPUS_FOR_BROAD_CLAIM",
    "MIN_FOR_CONCENTRATION",
    "STALE_AFTER_YEARS",
    "GapAssessment",
    "GapProposal",
    "GapSourceRef",
    "NotAssessed",
    "assess_gaps",
    "bounded",
    "strength_ceiling",
]
