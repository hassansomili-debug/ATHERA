"""الموضوعات | Themes — and the line a topic cluster must not cross (PUBRIVA).

**تجميعٌ موضوعي ليس موضوعًا علميًّا.** عناوينُ عشر دراساتٍ تشترك في كلمة
«التحوّل الرقمي» تُجمَع في قائمةٍ واحدة، وهذا ترتيبٌ نافع للقائمة — ولا
شيء فيه نتيجة. والموضوع العلمي تركيبٌ من محتوًى قُرئ من الأوراق نفسها:
مشكلةٍ وهدفٍ وبناءٍ ونتيجة.

وطيُّ الأول في الثاني هو الطريق المباشر إلى «فجوات» مبنيّة على عناوين. فلا
يُطوى هنا: `basis` عمودٌ في القاعدة، والدالّة تُنتج النوعين **مفصولين
بأسمائهما**، والشاشة تعرض الفرق لا تُخفيه.

**ولا موضوع بلا أثرٍ يُتتبَّع.** كل سندٍ لموضوعٍ علميّ يحمل معرّف خليةٍ في
مصفوفة الأدبيات (ترحيل 0023)؛ والخلية تحمل مقتطفها ومَداها ومَن كتبها. فمن
ضغط على الموضوع بلغ الشاهد في ثلاث نقرات — ولم يُقال له «ثِق».

**والحتميّة شرط.** لا نموذج هنا ولا مزوّد: مخرَجٌ يختلف بين تشغيلتين على
المُدخل نفسه لا يُراجَع ولا يُقارَن، وباحثٌ يرى موضوعًا يظهر ويختفي لا يبني
عليه شيئًا.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Final

from ...models.synthesis import CONTENT_SYNTHESIS, TOPIC_CLUSTER
from . import textual
from .corpus import CONTENT_FIELDS, CorpusSnapshot, StudySnapshot

# **دراستان أقلّ ما يُسمّى موضوعًا.** ودراسةٌ واحدة ليست موضوعًا، هي دراسة.
MIN_STUDIES_PER_THEME: Final = 2

# الأعمدة التي يُشتقّ منها موضوعٌ علميّ. و«الحدود» و«الفجوات» ليست منها:
# ما ذكرته ورقةٌ عن حدودها ليس موضوعًا تشترك فيه الأوراق.
THEME_SOURCE_FIELDS: Final = ("constructs", "problem", "objective", "theory", "findings")

# عمودُ السند حين يكون التجميع من العنوان وحده.
METADATA_BASIS_FIELD: Final = "reference"

# أكثر ما يُقترح في مرّةٍ واحدة. وقائمةٌ من ستّين «موضوعًا» لا تُقرأ، فتُقرأ
# بالثقة — وهو أسوأ من ألّا تُعرض.
MAX_PROPOSALS: Final = 12


@dataclass(frozen=True, slots=True)
class ThemeSupport:
    """سندٌ واحد — **ومعه الخلية**، وهي أول حلقةٍ في سلسلة الأثر."""

    source_id: uuid.UUID
    role: str
    basis_field_key: str
    evidence_scope: str
    matrix_cell_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ThemeProposal:
    """موضوعٌ مقترَح — ولم يُكتب في القاعدة بعد، ولم يقل فيه إنسانٌ شيئًا."""

    label_ar: str
    description_ar: str
    basis: str
    supports: tuple[ThemeSupport, ...] = ()
    source_scope_summary: dict[str, int] = field(default_factory=dict)

    @property
    def source_ids(self) -> tuple[uuid.UUID, ...]:
        seen: list[uuid.UUID] = []
        for support in self.supports:
            if support.source_id not in seen:
                seen.append(support.source_id)
        return tuple(seen)

    @property
    def is_traceable(self) -> bool:
        """هل يبلغ كل سندٍ محتوًى خليةً بعينها؟ — شرطُ «موضوع علمي»."""
        return all(
            support.matrix_cell_id is not None
            for support in self.supports
            if support.evidence_scope != "metadata_only"
        )


def _scope_summary(corpus: CorpusSnapshot,
                   source_ids: tuple[uuid.UUID, ...]) -> dict[str, int]:
    """توزيعُ مدى القراءة عبر دراسات الموضوع — **رقمٌ يفضح موضوعًا بلا قراءة**."""
    out: dict[str, int] = {}
    for source_id in source_ids:
        study = corpus.study(source_id)
        if study is not None:
            out[study.reading_scope] = out.get(study.reading_scope, 0) + 1
    return out


def _content_hits(study: StudySnapshot
                  ) -> dict[str, tuple[str, uuid.UUID | None, str, str]]:
    """مفاتيحُ المحتوى: مفتاح ← (العمود، الخلية، المدى، **الكلمة كما كُتبت**).

    وأوّلُ عمودٍ يذكر المفتاح هو سنده — فلا يُسجَّل السند مرّتين لكلمةٍ
    تكرّرت في عمودين، ولا يُعدّ موضوعٌ واحد دراستين.
    """
    hits: dict[str, tuple[str, uuid.UUID | None, str, str]] = {}
    for field_key in THEME_SOURCE_FIELDS:
        cell = study.stated(field_key)
        if cell is None or cell.source_scope == "metadata_only":
            continue
        for term, surface in textual.term_forms(cell.value_ar).items():
            hits.setdefault(term, (field_key, cell.cell_id, cell.source_scope, surface))
    return hits


def _display(term: str, forms: dict[str, set[str]]) -> str:
    """اسمُ الموضوع كما يقرؤه الباحث — **لا المفتاح المسوّى**.

    والاختيار حتميّ (أول الصور أبجديًّا) لا «أوّل ما صادفناه»: مخرَجٌ يتبدّل
    اسمه بترتيب القراءة يجعل مقارنة قائمتين مستحيلة.
    """
    seen = forms.get(term)
    return sorted(seen)[0] if seen else term


def propose_themes(corpus: CorpusSnapshot) -> tuple[ThemeProposal, ...]:
    """يقترح الموضوعات والتجميعات — **مفصولةً بأسمائها، لا مختلطة**.

    الترتيب حتميّ: الموضوعات العلمية أولًا، ثم الأكثر سندًا، ثم أبجديًّا.
    ومخرَجٌ يتغيّر ترتيبه بين تشغيلتين يجعل مقارنة قائمتين مستحيلة.
    """
    if corpus.size < MIN_STUDIES_PER_THEME:
        return ()

    content_by_term: dict[str, list[ThemeSupport]] = {}
    title_by_term: dict[str, list[ThemeSupport]] = {}
    forms: dict[str, set[str]] = {}

    for study in corpus.studies:
        for term, (field_key, cell_id, scope, surface) in _content_hits(study).items():
            forms.setdefault(term, set()).add(surface)
            content_by_term.setdefault(term, []).append(ThemeSupport(
                source_id=study.source_id, role="supporting",
                basis_field_key=field_key, evidence_scope=scope,
                matrix_cell_id=cell_id))
        for term, surface in textual.term_forms(study.title).items():
            forms.setdefault(term, set()).add(surface)
            title_by_term.setdefault(term, []).append(ThemeSupport(
                source_id=study.source_id, role="supporting",
                basis_field_key=METADATA_BASIS_FIELD, evidence_scope="metadata_only"))

    proposals: list[ThemeProposal] = []

    for term, supports in content_by_term.items():
        # **السند المحتوى بلا خلية لا يُقبل.** خليةٌ لم تُخزَّن (عنوانٌ أو
        # سنة) لا تصلح سندًا لموضوعٍ علميّ، والقيد في القاعدة يرفضها أيضًا.
        usable = tuple(s for s in supports if s.matrix_cell_id is not None)
        if len({s.source_id for s in usable}) < MIN_STUDIES_PER_THEME:
            continue
        source_ids = tuple(dict.fromkeys(s.source_id for s in usable))
        summary = _scope_summary(corpus, source_ids)
        shown = _display(term, forms)
        proposals.append(ThemeProposal(
            label_ar=shown,
            description_ar=(
                f"تركيبٌ من محتوى {len(source_ids)} دراسةً مُدرَجة: ذكرت كلٌّ منها "
                f"«{shown}» في أعمدة المحتوى بالمصفوفة. والسند خليةٌ لكل دراسة "
                "يمكن فتحها ورؤية شاهدها ومدى ما قُرئ منه."),
            basis=CONTENT_SYNTHESIS,
            supports=usable,
            source_scope_summary=summary))

    for term, supports in title_by_term.items():
        if term in content_by_term:
            # سبقه موضوعٌ علميّ بالاسم نفسه — ولا يُعرض تجميعٌ يكرّره،
            # فيقرأ الباحث اثنين ويحسبهما إشارتين.
            continue
        source_ids = tuple(dict.fromkeys(s.source_id for s in supports))
        if len(source_ids) < MIN_STUDIES_PER_THEME:
            continue
        summary = _scope_summary(corpus, source_ids)
        shown = _display(term, forms)
        proposals.append(ThemeProposal(
            label_ar=shown,
            description_ar=(
                f"تجميعٌ موضوعي من العناوين وحدها: {len(source_ids)} دراسةً "
                f"يشترك عنوانها في «{shown}». **وهذا ترتيبٌ للقائمة لا نتيجة** — "
                "لم يُقرأ من هذه الدراسات محتوًى يسند موضوعًا، ولا يصلح سندًا "
                "لفجوةٍ ولا لتعارض."),
            basis=TOPIC_CLUSTER,
            supports=supports,
            source_scope_summary=summary))

    proposals.sort(key=lambda p: (
        0 if p.basis == CONTENT_SYNTHESIS else 1,
        -len(p.source_ids),
        p.label_ar,
    ))
    return tuple(proposals[:MAX_PROPOSALS])


def traceability_is_complete(proposal: ThemeProposal) -> bool:
    """**لا موضوع علميّ بلا أثر.** والتجميع الموضوعي لا يدّعي أثرًا أصلًا."""
    if proposal.basis == TOPIC_CLUSTER:
        return all(s.evidence_scope == "metadata_only" for s in proposal.supports)
    return proposal.is_traceable and bool(proposal.supports)


__all__ = [
    "CONTENT_FIELDS",
    "MAX_PROPOSALS",
    "METADATA_BASIS_FIELD",
    "MIN_STUDIES_PER_THEME",
    "THEME_SOURCE_FIELDS",
    "ThemeProposal",
    "ThemeSupport",
    "propose_themes",
    "traceability_is_complete",
]
