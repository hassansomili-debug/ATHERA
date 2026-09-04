"""الفرز ومصفوفة الأدبيات | Screening and literature matrix (PUBRIVA).

**ما تقوله هذه الخدمة كلّه جوابٌ عن سؤالٍ واحد: ماذا قُرئ فعلًا؟**

مصفوفةُ أدبيات تُملأ بالتخمين أسوأ من مصفوفةٍ فارغة: الفارغة تُظهر الفجوة،
والمخمَّنة تُخفيها ثم تُكتب في الورقة. فالمدى المتاح لكل مرجعٍ يُحسب هنا من
حالٍ مسجَّلة — حقّ الوصول، ووجود ملفٍّ في هذا البحث، وملخّصٍ أرسله الفهرس —
ولا يُطلب من الباحث أن يدّعيه ولا من نموذجٍ أن يفترضه.

وترتيب المدى معنًى لا تصنيف: `metadata_only` أضعف من `abstract_only`،
وهي أضعف من `full_text`. فطلبُ خليةٍ بمدًى أعلى من المتاح يُردّ صراحةً —
ولا يُقبل ثم يُصحَّح بصمت.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# **الاقتباس لا يُكرَّر.** بناءُ الملخّص من ترميز JATS ومن الفهرس المقلوب
# محلولٌ في حزمة الاكتشاف وقد فُحص هناك؛ ونسخةٌ ثانية منه تفترق عن الأولى
# بأول إصلاح، فيقرأ مساران ملخّصين مختلفين للورقة نفسها.
from ..discovery.crossref import _abstract as _abstract_from_jats
from ..discovery.openalex import _abstract as _abstract_from_inverted
from ..models.files import File
from ..models.literature import (
    ACCESS_STATES,
    TEXT_BEARING_STATES,
    Author,
    Source,
    SourceAuthor,
)
from ..models.portfolio import ProjectFile, ProjectSource
from ..models.research import DocumentChunk
from ..models.screening import (
    ABSTRACT_LOCATOR,
    ABSTRACT_PROVIDERS,
    EXCLUSION_REASON_CODES,
    FREE_TEXT_REASON_CODE,
    MATRIX_FIELDS,
    LiteratureMatrixCell,
    SourceAbstract,
    scope_rank,
)

METADATA_ONLY = "metadata_only"
ABSTRACT_ONLY = "abstract_only"
FULL_TEXT = "full_text"

# الأعمدة التي تُقرأ من البيانات الوصفية وحدها — وهي اثنان لا أكثر.
# **وما عداهما لا يُملأ آليًّا أبدًا**: منهجٌ أو عيّنةٌ أو مقياسٌ لا يُستخرج
# من عنوانٍ وسنة، ومن ملأها من البيانات الوصفية فقد اخترع.
METADATA_FIELDS = ("reference", "year")


# الوصول المفتوح كما **يعلنه الفهرس** — وهو دعوى حقوقٍ لا قراءة. تُعرض
# للباحث باسمها، ولا تُترجَم يومًا إلى «النصّ متاح».
OPEN_ACCESS_STATE = "open_access_full_text"


@dataclass(frozen=True, slots=True)
class AbstractRecord:
    """ملخّصٌ واحد **ومن أرسله ومتى** — لا نصٌّ يطفو بلا نسبة.

    وحُفظ الوقتُ والمعرّف معه لأن ملخّصين مختلفين لورقةٍ واحدة لا يُحسم
    بينهما بالنصّ وحده: يُقرأ من أرسل كلًّا منهما ومتى، ثم يحكم الباحث.
    """

    provider: str
    text: str
    # **`None` تعني «لم يقل الفهرس متى»** — لا «الآن». ووقتُ قراءتنا للصفّ
    # ليس وقت وصول الملخّص، وكتابته مكانه تخترع تاريخًا لم يُرسله أحد.
    retrieved_at: dt.datetime | None = None
    provider_identifier: str | None = None
    # معرّف الصفّ المخزَّن إن كان محفوظًا؛ و`None` تعني ملخّصًا قُرئ من بيانات
    # الفهرس الخام ولم يُثبَّت بعد.
    stored_id: uuid.UUID | None = None

    @property
    def content_hash(self) -> str:
        return abstract_digest(self.text)


def abstract_digest(text: str) -> str:
    """بصمةُ نصٍّ — بها يُعرف أن ما وصل اليوم هو نفسه ما وصل أمس.

    والفراغُ يُوحَّد قبل البصم: فهرسٌ أعاد النصّ نفسه بسطرٍ إضافي لم يرسل
    ملخّصًا ثانيًا، وصفٌّ جديد له يجعل اتفاقًا يبدو اختلافًا.
    """
    return hashlib.sha256(
        re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReadingScope:
    """ما يمكن قراءته من هذا المرجع في هذا البحث — **لا ما يُدّعى**."""

    scope: str
    abstract: str | None = None
    # الملف الذي يجعل `full_text` ممكنة. غيابه يعني أن النصّ ليس في اليد،
    # مهما قال الفهرس عن انفتاح الوصول.
    file_id: uuid.UUID | None = None
    # **كل الملخّصات المتاحة منسوبةً** — لا واحدٌ غلب البقية بصمت.
    abstracts: tuple[AbstractRecord, ...] = ()

    def permits(self, requested: str) -> bool:
        return scope_rank(requested) <= scope_rank(self.scope)

    @property
    def abstracts_disagree(self) -> bool:
        """هل أرسل فهرسان نصّين مختلفين؟ — حالٌ تُعرض ولا تُحسم آليًّا."""
        return len({record.content_hash for record in self.abstracts}) > 1


@dataclass(slots=True)
class ScreeningCard:
    """بطاقةُ دراسةٍ في شاشة الفرز — بما يُعرَف به المرجع لا بمعرّفٍ داخلي."""

    source_id: uuid.UUID
    title: str
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    venue: str | None = None
    # **الـDOI يُعرض متحقَّقًا أو لا يُعرض.** معرّفٌ لم يُحلّ في فهرسٍ معروضًا
    # بجانب دراسةٍ يُقرأ إثباتًا، فيُنسخ في قائمة المراجع وهو لم يُفحص.
    doi: str | None = None
    registry: str | None = None
    verification_status: str = "unverified"
    retraction_status: str = "unknown"
    use_state: str = "saved_only"
    exclusion_reason_code: str | None = None
    reason_ar: str | None = None
    decided_at: dt.datetime | None = None
    added_at: dt.datetime | None = None
    reading_scope: str = METADATA_ONLY
    has_abstract: bool = False
    # **دعوى الفهرس لا قراءةٌ وقعت.** «مفتوح الوصول» حالُ حقوقٍ يعلنها فهرس،
    # وتُعرض باسمها؛ ولا تُترجَم يومًا إلى «النصّ الكامل في يدك».
    index_says_open_access: bool = False
    # نوعُ الوثيقة كما أعلنه الفهرس — يُقرأ ولا يُصدَّق (§33.3).
    document_type: str | None = None
    # مرجعٌ يشترك مع غيره في هذا البحث بمعرّفٍ أو عنوانٍ مُطابَق. **تنبيهٌ لا
    # حكم**: الحذف قرارُ الباحث، والاستبعاد يلزمه سببه المسجَّل كسائر أسبابه.
    possible_duplicate: bool = False
    # عددُ الملخّصات المنسوبة، وهل اختلفت. واختلافُ فهرسين يُعرض اختلافًا
    # ولا يُحسم بغلبة أحدهما بصمت.
    abstract_sources: int = 0
    abstracts_disagree: bool = False


@dataclass(slots=True)
class MatrixCellView:
    field_key: str
    value_ar: str | None
    cell_state: str
    source_scope: str
    extraction_method: str
    verification_status: str
    source_file_id: uuid.UUID | None = None
    evidence_quote: str | None = None
    evidence_locator: str | None = None
    # من أي ملخّصٍ قُرئت الخلية — ومن أرسله. لا «من ملخّص» مجهولٍ صاحبه.
    source_abstract_id: uuid.UUID | None = None
    abstract_provider: str | None = None
    # **الصفحة تُقال حين تُعرف، وتُترك `None` حين لا تُعرف.**
    evidence_page: int | None = None
    evidence_section: str | None = None


@dataclass(slots=True)
class MatrixRow:
    source_id: uuid.UUID
    title: str
    authors: list[str]
    publication_year: int | None
    doi: str | None
    reading_scope: str
    cells: list[MatrixCellView]


def abstract_of(source: Source) -> str | None:
    """ملخّصُ المرجع كما أرسله الفهرس — **ولا يُولَّد ولا يُستنتج**.

    `raw_metadata` محتوًى غير موثوق (§33.3): يُقرأ منه حقلُ الملخّص وحده،
    وبصورته التي يرسلها كل فهرس. وغيابه يبقى غيابًا: مرجعٌ بلا ملخّصٍ
    مُرسَل لا يُملأ منه عمودٌ واحد في المصفوفة.
    """
    raw = source.raw_metadata
    if not isinstance(raw, dict):
        return None
    jats = raw.get("abstract")
    if isinstance(jats, str):
        text = _abstract_from_jats(jats)
        if text:
            return text
    inverted = raw.get("abstract_inverted_index")
    if isinstance(inverted, dict):
        return _abstract_from_inverted(inverted)
    return None


def _provider_of(source: Source, fallback: str) -> str:
    """من أرسل هذا الملخّص — بالفهرس المسجَّل، وإلّا بصورة النصّ نفسه.

    ولا يُنسب ملخّصٌ إلى فهرسٍ لا تعرفه المفردة المغلقة: نسبةٌ خاطئة أسوأ من
    نسبةٍ عامّة، لأنها تُقرأ إثباتًا ويُعاد إليها الطلب فلا يُوجد شيء.
    """
    registry = (source.registry or "").strip().lower()
    return registry if registry in ABSTRACT_PROVIDERS else fallback


def derived_abstracts(source: Source) -> list[AbstractRecord]:
    """ملخّصات هذا المرجع كما وردت في بيانات الفهرس الخام — **منسوبةً**.

    وكانت تُقرأ نصًّا واحدًا بلا اسم مرسِله؛ فإذا حمل الصفّ ترميز JATS
    وفهرسًا مقلوبًا معًا غلب الأول الثاني بصمت. وهما مصدران لا واحد،
    فيُقرآن اثنين ويُنسب كلٌّ إلى شكله.

    و`retrieved_at` وقتُ آخر تحقّقٍ من المرجع إن وُجد، وإلّا وقتُ إنشاء صفّه
    — ولا يُكتب «الآن»: وقتُ القراءة ليس وقت الوصول.
    """
    raw = source.raw_metadata
    if not isinstance(raw, dict):
        return []
    # وقتُ آخر تحقّقٍ من المرجع إن وُجد، وإلّا وقتُ إنشاء صفّه. وغيابهما معًا
    # يبقى غيابًا: `None` تقول «لا نعرف متى وصل»، ولا تُملأ بلحظة القراءة.
    when = source.last_verified_at or source.created_at
    identifier = source.registry_id
    out: list[AbstractRecord] = []
    jats = raw.get("abstract")
    if isinstance(jats, str):
        text = _abstract_from_jats(jats)
        if text:
            out.append(AbstractRecord(
                provider=_provider_of(source, "crossref"), text=text,
                retrieved_at=when, provider_identifier=identifier))
    inverted = raw.get("abstract_inverted_index")
    if isinstance(inverted, dict):
        text = _abstract_from_inverted(inverted)
        if text:
            out.append(AbstractRecord(
                provider=_provider_of(source, "openalex"), text=text,
                retrieved_at=when, provider_identifier=identifier))
    return out


def abstracts_of(source: Source,
                 stored: Sequence[SourceAbstract] = ()) -> list[AbstractRecord]:
    """كل ملخّصات هذا المرجع — **المحفوظ والوارد معًا، ولا يُطوى أحدهما**.

    والصفّ المحفوظ يسبق ما يُشتقّ من البيانات الخام لأنه يحمل وقت وصوله
    ومعرّفه عند مرسِله؛ وما يطابقه بصمةً ومرسِلًا لا يُعاد ذكره — تكرارُ
    النصّ نفسه مرّتين يُقرأ فهرسين اتّفقا، وهو فهرسٌ واحد قُرئ مرّتين.
    """
    out: list[AbstractRecord] = [
        AbstractRecord(provider=row.provider, text=row.text,
                       retrieved_at=row.retrieved_at,
                       provider_identifier=row.provider_identifier,
                       stored_id=row.id)
        for row in stored
    ]
    seen = {(record.provider, record.content_hash) for record in out}
    for record in derived_abstracts(source):
        key = (record.provider, record.content_hash)
        if key not in seen:
            seen.add(key)
            out.append(record)
    return out


def reading_scope(source: Source, *, project_file_ids: set[uuid.UUID],
                  stored_abstracts: Sequence[SourceAbstract] = ()) -> ReadingScope:
    """أقصى مدًى صادق لهذا المرجع في هذا البحث.

    **`full_text` تعني أن النصّ في اليد**، لا أن الفهرس قال إنه مفتوح: حقّ
    المعالجة شرطٌ أول (§14.2)، ووجودُ ملفٍّ مرتبطٍ بهذا البحث شرطٌ ثانٍ. فمن
    لم يرفع الورقة لم يقرأها — وشاشةٌ تسمح له بادّعاء قراءتها تكذب نيابةً
    عنه في مصفوفةٍ ستُكتب منها ورقة.

    و`project_file_ids` هي الملفات التي **يُقرأ منها فعلًا**: يبنيها
    `readable_project_file_ids` من ملفٍّ مرتبطٍ بهذا البحث وله تقطيعٌ مقروء.
    فملفٌّ مرفوع لم يُقرأ منه حرفٌ بعد ليس نصًّا كاملًا في اليد — هو وعدٌ به.

    و`abstract` يبقى النصّ الأول للتوافق مع ما بُني عليه؛ و`abstracts` تحمل
    الجميع منسوبين، لأن فهرسين مختلفين حالٌ تُعرض لا تُطوى.
    """
    records = tuple(abstracts_of(source, stored_abstracts))
    abstract = records[0].text if records else None
    text_bearing = ACCESS_STATES.get(source.access_state, False)
    file_id = source.file_id if source.file_id in project_file_ids else None
    if text_bearing and file_id is not None:
        return ReadingScope(FULL_TEXT, abstract, file_id, records)
    if abstract:
        return ReadingScope(ABSTRACT_ONLY, abstract, file_id, records)
    return ReadingScope(METADATA_ONLY, abstract, file_id, records)


def reason_is_acceptable(code: str | None, note: str | None) -> bool:
    """هل يصلح هذا السبب مُدخَلًا؟ — **و`unrecorded_legacy` لا يصلح أبدًا**.

    هي قيمةٌ تصف صفوفًا سبقت اشتراط الأسباب، وقبولها مُدخَلًا يفتح بابًا
    خلفيًّا لاستبعادٍ بلا سبب — وهو ما أُنشئ الحقل كلّه ليمنعه.
    """
    if code not in EXCLUSION_REASON_CODES:
        return False
    if code == FREE_TEXT_REASON_CODE:
        return bool(note and note.strip())
    return True


def locator_is_honest(scope: str, locator: str | None) -> bool:
    """**لا تُخترع أرقام صفحات.** ملخّصٌ لا صفحات له، وبياناتٌ وصفية لا موضع."""
    if locator is None:
        return True
    if scope == METADATA_ONLY:
        return False
    if scope == ABSTRACT_ONLY:
        return locator == ABSTRACT_LOCATOR
    return True


async def project_file_ids(session: AsyncSession, *, tenant_id: uuid.UUID,
                           project_id: uuid.UUID) -> set[uuid.UUID]:
    """ملفات هذا البحث القائمة — عبارةٌ واحدة تخدم كل بطاقات الشاشة.

    والقراءة تقع مرّة لا مرّةً لكل مرجع: صفحةُ الفرز تعرض عشرات البطاقات،
    وعبارةٌ لكل واحدة تُعيد عطب `1 + N` الذي بلغ ثلاثين ثانية في `GET
    /files`.
    """
    rows = (await session.execute(
        select(ProjectFile.file_id).where(
            ProjectFile.tenant_id == tenant_id,
            ProjectFile.project_id == project_id,
            ProjectFile.state == ProjectFile.ACTIVE)
    )).scalars().all()
    return set(rows)


async def authors_by_source(session: AsyncSession, *, tenant_id: uuid.UUID,
                            source_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    """أسماء المؤلفين لكل مرجع — **عبارةٌ واحدة للقائمة كلّها**."""
    if not source_ids:
        return {}
    rows = (await session.execute(
        select(SourceAuthor.source_id, Author.display_name)
        .join(Author, Author.id == SourceAuthor.author_id)
        .where(SourceAuthor.tenant_id == tenant_id,
               SourceAuthor.source_id.in_(source_ids))
        .order_by(SourceAuthor.source_id, SourceAuthor.position)
    )).all()
    out: dict[uuid.UUID, list[str]] = {}
    for source_id, name in rows:
        out.setdefault(source_id, []).append(name)
    return out


async def readable_project_file_ids(session: AsyncSession, *, tenant_id: uuid.UUID,
                                   project_id: uuid.UUID) -> set[uuid.UUID]:
    """ملفات هذا البحث التي **يُقرأ منها فعلًا** — لا التي رُفعت وحدها.

    ملفٌّ مرفوع لم يُقطَّع منه سطرٌ بعد ليس نصًّا كاملًا في اليد: هو وعدٌ به.
    وقد يكون رفعُه فشل، أو تحليلُه لم يقع، أو كان صورًا لا نصّ فيها. فيُشترط
    وجودُ تقطيعٍ مقروء — وهو الفرق بين «معي الورقة» و«معي ملفٌّ اسمه الورقة».
    """
    rows = (await session.execute(
        select(ProjectFile.file_id).where(
            ProjectFile.tenant_id == tenant_id,
            ProjectFile.project_id == project_id,
            ProjectFile.state == ProjectFile.ACTIVE,
            exists().where(and_(DocumentChunk.tenant_id == tenant_id,
                                DocumentChunk.file_id == ProjectFile.file_id)))
    )).scalars().all()
    return set(rows)


async def stored_abstracts_by_source(
    session: AsyncSession, *, tenant_id: uuid.UUID,
    source_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, list[SourceAbstract]]:
    """الملخّصات المحفوظة لهذه المراجع — **عبارةٌ واحدة للصفحة كلّها**."""
    if not source_ids:
        return {}
    rows = (await session.execute(
        select(SourceAbstract)
        .where(SourceAbstract.tenant_id == tenant_id,
               SourceAbstract.source_id.in_(source_ids))
        .order_by(SourceAbstract.provider, SourceAbstract.retrieved_at.desc())
    )).scalars().all()
    out: dict[uuid.UUID, list[SourceAbstract]] = {}
    for row in rows:
        out.setdefault(row.source_id, []).append(row)
    return out


def dedup_key_expr():
    """مفتاح التكرار المحتمل — **المعرّف هويةٌ، والعنوان قرينة**.

    والفهرس في الترحيل 0024 مكتوبٌ بهذه العبارة نفسها حرفًا بحرف؛ فمن غيّر
    أحدهما وحده ترك القاعدة تمسح جدول المراجع في كل فتحٍ للشاشة.
    """
    doi = func.nullif(func.lower(func.btrim(Source.doi)), "")
    title = func.lower(func.regexp_replace(
        func.coalesce(Source.title, ""), "[^[:alnum:]]+", "", "g"))
    return func.coalesce(doi, title)


def has_abstract_expr(tenant_id: uuid.UUID):
    """هل لهذا المرجع ملخّص؟ — **سؤالٌ يُجاب في القاعدة لا في الذاكرة**.

    والتصفية على ألف مرجعٍ لا تُحتمل في بايثون: تُحمَّل كلّها لتُرمى تسعُ
    مئة. فتُكتب الشروط هنا بما يقابل `abstracts_of` قدر ما تقابله SQL.

    **وفرقٌ واحد يبقى ويُقال:** فاكُّ الفهرس المقلوب يرفض ملخّصًا يزيد على
    أربعة آلاف كلمة، وهذا الشرط لا يعدّ الكلمات. فمرجعٌ كهذا — ولم يُر قطّ —
    يدخل في تصفية «له ملخّص» وتقول بطاقته «لا ملخّص». والبطاقة هي الصادقة،
    والتصفية تزيد ولا تُخفي: أن تُعرض دراسةٌ زائدة أهون من أن تُحجب.
    """
    raw = Source.raw_metadata
    jats = and_(
        func.jsonb_typeof(raw["abstract"]) == "string",
        func.length(func.btrim(func.regexp_replace(
            func.coalesce(raw["abstract"].astext, ""), "<[^>]*>", " ", "g"))) > 0,
    )
    inverted = and_(
        func.jsonb_typeof(raw["abstract_inverted_index"]) == "object",
        raw["abstract_inverted_index"].astext != "{}",
    )
    stored = exists().where(and_(SourceAbstract.tenant_id == tenant_id,
                                 SourceAbstract.source_id == Source.id))
    return or_(stored, jats, inverted)


@dataclass(frozen=True, slots=True)
class ScreeningFilters:
    """ما يُصفّى به قبل التصفيح — **وكلُّه في القاعدة**.

    وتصفيةٌ تقع بعد التصفيح كذبة: الصفحة الأولى تعرض ثلاثة من عشرين لأن
    سبعة عشر رُفضت بعد جلبها، ويقرأ الباحث «ثلاث دراسات» وهي ثلاثمائة.
    """

    use_state: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    registry: str | None = None
    document_type: str | None = None
    open_access: bool | None = None
    has_abstract: bool | None = None
    has_full_text: bool | None = None
    possible_duplicate: bool | None = None

    @property
    def without_state(self) -> ScreeningFilters:
        """المرشّحات بلا حال الفرز — **وعليها تُحسب العدّادات**.

        فالعدّاد يجيب: «كم مُدرَجة **ضمن ما أراه الآن**؟». وإسقاط بقيّة
        المرشّحات يجعله يجيب عن سؤالٍ آخر لم يُسأل.
        """
        return replace(self, use_state=None)


def apply_filters(stmt: Select, filters: ScreeningFilters, *,
                  tenant_id: uuid.UUID,
                  duplicate_ids: frozenset[uuid.UUID],
                  readable_file_ids: frozenset[uuid.UUID]) -> Select:
    """يُلحق المرشّحات بعبارةٍ تصل `project_sources` بـ`sources` — قبل أي حدّ."""
    if filters.use_state:
        stmt = stmt.where(ProjectSource.use_state == filters.use_state)
    if filters.year_from is not None:
        stmt = stmt.where(Source.publication_year >= filters.year_from)
    if filters.year_to is not None:
        stmt = stmt.where(Source.publication_year <= filters.year_to)
    if filters.registry:
        stmt = stmt.where(Source.registry == filters.registry)
    if filters.document_type:
        stmt = stmt.where(
            Source.raw_metadata["type"].astext == filters.document_type)
    if filters.open_access is not None:
        # **دعوى الفهرس تُصفّى بها باسمها.** والحقل يقول «الفهرس أعلن وصولًا
        # مفتوحًا»، لا «النصّ في يدك» — واثنان مختلفان لا يُخلطان في مرشّح.
        test = Source.access_state == OPEN_ACCESS_STATE
        stmt = stmt.where(test if filters.open_access else ~test)
    if filters.has_abstract is not None:
        test = has_abstract_expr(tenant_id)
        stmt = stmt.where(test if filters.has_abstract else ~test)
    if filters.has_full_text is not None:
        # النصّ الكامل شرطان: حقّ معالجة، وملفٌّ في هذا البحث يُقرأ منه فعلًا.
        test = and_(Source.access_state.in_(TEXT_BEARING_STATES),
                    Source.file_id.in_(readable_file_ids))
        stmt = stmt.where(test if filters.has_full_text else ~test)
    if filters.possible_duplicate is not None:
        test = ProjectSource.source_id.in_(duplicate_ids)
        stmt = stmt.where(test if filters.possible_duplicate else ~test)
    return stmt


async def duplicate_source_ids(session: AsyncSession, *, tenant_id: uuid.UUID,
                               project_id: uuid.UUID) -> frozenset[uuid.UUID]:
    """مراجع هذا البحث التي يشترك اثنان منها في معرّفٍ أو عنوانٍ مُطابَق.

    **والعزل هنا عزلُ بحثٍ لا عزلُ مستأجر فقط.** التكرار سؤالٌ داخل بحثٍ
    بعينه: ورقةٌ في بحثين ليست مكرّرة، وحصرُ المجموعة بـ`project_id` هو ما
    يمنع أن يُقال لباحثٍ إن دراسته مكرّرة لأنها موجودة في بحثٍ آخر له.

    والحساب يقع في القاعدة تجميعًا، فلا تُحمَّل المراجع لتُقارن في الذاكرة.
    """
    key = dedup_key_expr()
    repeated = (
        select(key.label("dedup_key"))
        .select_from(ProjectSource)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id)
        .group_by(key)
        .having(func.count(ProjectSource.id) > 1)
        .subquery()
    )
    rows = (await session.execute(
        select(ProjectSource.source_id)
        .select_from(ProjectSource)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id,
               key.in_(select(repeated.c.dedup_key)))
    )).scalars().all()
    return frozenset(rows)


@dataclass(slots=True)
class ScreeningTallies:
    """عدّادات الشاشة — **من القاعدة، لا من طول الصفحة المعروضة**."""

    saved_only: int = 0
    included: int = 0
    excluded: int = 0

    @property
    def all(self) -> int:
        return self.saved_only + self.included + self.excluded

    def of(self, use_state: str | None) -> int:
        return self.all if use_state is None else getattr(self, use_state, 0)


async def screening_tallies(session: AsyncSession, *, tenant_id: uuid.UUID,
                            project_id: uuid.UUID, filters: ScreeningFilters,
                            duplicate_ids: frozenset[uuid.UUID],
                            readable_file_ids: frozenset[uuid.UUID]) -> ScreeningTallies:
    """كم في كل حال — **بكل المرشّحات إلا حال الفرز نفسها**.

    فالتبويب يقول «المستبعَدة (٧)» وأنت في تبويب «المدرَجة»: عددٌ محسوبٌ فوق
    الصفحة المعروضة يقول صفرًا دائمًا، ويقرؤه الباحث حكمًا على بحثه.
    """
    stmt = (
        select(ProjectSource.use_state, func.count(ProjectSource.id))
        .select_from(ProjectSource)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id)
        .group_by(ProjectSource.use_state)
    )
    stmt = apply_filters(stmt, filters.without_state, tenant_id=tenant_id,
                         duplicate_ids=duplicate_ids,
                         readable_file_ids=readable_file_ids)
    counts = dict((await session.execute(stmt)).all())
    return ScreeningTallies(
        saved_only=counts.get("saved_only", 0),
        included=counts.get("included", 0),
        excluded=counts.get("excluded", 0),
    )


# حدُّ الصفحة. والأعلى ليس تحسينًا: ألفُ بطاقةٍ في جوابٍ واحد تُسقط الشاشة
# التي تعرضها قبل أن تُسقط الخادم الذي بناها.
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class ScreeningPage:
    cards: list[ScreeningCard]
    page: int
    page_size: int
    # عدد ما تطابقه **كل** المرشّحات ومنها حال الفرز — لا عدد ما في الصفحة.
    total: int
    tallies: ScreeningTallies
    duplicates: int = 0

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


async def screening_page(session: AsyncSession, *, tenant_id: uuid.UUID,
                         project_id: uuid.UUID,
                         filters: ScreeningFilters | None = None,
                         page: int = 1,
                         page_size: int = DEFAULT_PAGE_SIZE) -> ScreeningPage:
    """صفحةٌ واحدة من الفرز — **تُصفّى في القاعدة ثم تُصفَّح**.

    وعددُ العبارات ثابتٌ لا يتبع عدد المراجع: مجموعةُ المكرّرات، وملفاتُ
    البحث المقروءة، والعدّادات، والصفحة، ومؤلفوها، وملخّصاتها. ستٌّ لمئة
    مرجعٍ وستٌّ لألف — وهو الفرق بين شاشةٍ تفتح وشاشةٍ تُنتظر.
    """
    filters = filters or ScreeningFilters()
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    duplicate_ids = await duplicate_source_ids(
        session, tenant_id=tenant_id, project_id=project_id)
    readable = frozenset(await readable_project_file_ids(
        session, tenant_id=tenant_id, project_id=project_id))

    tallies = await screening_tallies(
        session, tenant_id=tenant_id, project_id=project_id, filters=filters,
        duplicate_ids=duplicate_ids, readable_file_ids=readable)

    stmt = (
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id)
    )
    stmt = apply_filters(stmt, filters, tenant_id=tenant_id,
                         duplicate_ids=duplicate_ids, readable_file_ids=readable)
    # الترتيب بمفتاحين: الوقت وحده يتساوى في الاستيراد الجملة، فتتبدّل
    # الصفوف بين صفحتين ويظهر مرجعٌ مرّتين ويغيب آخر.
    rows = (await session.execute(
        stmt.order_by(ProjectSource.created_at.desc(), ProjectSource.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()

    source_ids = [source.id for _link, source in rows]
    names = await authors_by_source(session, tenant_id=tenant_id, source_ids=source_ids)
    abstracts = await stored_abstracts_by_source(
        session, tenant_id=tenant_id, source_ids=source_ids)

    cards = [
        card_of(link, source, authors=names.get(source.id, []),
                scope=reading_scope(source, project_file_ids=readable,
                                    stored_abstracts=abstracts.get(source.id, ())),
                is_duplicate=source.id in duplicate_ids)
        for link, source in rows
    ]
    return ScreeningPage(cards=cards, page=page, page_size=page_size,
                         total=tallies.of(filters.use_state), tallies=tallies,
                         duplicates=len(duplicate_ids))


def document_type_of(source: Source) -> str | None:
    """نوعُ الوثيقة كما أعلنه الفهرس — **يُقرأ ولا يُصدَّق** (§33.3).

    ولا يُستنتج من شيء: مرجعٌ بلا نوعٍ مُعلَن يبقى بلا نوع، ولا يُسمّى
    «مقال مجلة» لأن له مجلّة — فالكتابُ المراجَع له مجلّةٌ كذلك.
    """
    raw = source.raw_metadata
    if not isinstance(raw, dict):
        return None
    value = raw.get("type")
    return (value.strip() or None) if isinstance(value, str) else None


def card_of(link: ProjectSource, source: Source, *, authors: list[str],
            scope: ReadingScope, is_duplicate: bool = False) -> ScreeningCard:
    """بطاقةٌ واحدة — **والـDOI لا يُعرض إلا متحقَّقًا**."""
    return ScreeningCard(
        source_id=source.id,
        title=source.title,
        authors=authors,
        publication_year=source.publication_year,
        venue=source.journal_name_raw,
        doi=source.doi if source.verification_status == "verified" else None,
        registry=source.registry,
        verification_status=source.verification_status,
        retraction_status=source.retraction_status,
        use_state=link.use_state,
        exclusion_reason_code=link.exclusion_reason_code,
        reason_ar=link.reason_ar,
        decided_at=link.decided_at,
        added_at=link.created_at,
        reading_scope=scope.scope,
        has_abstract=bool(scope.abstract),
        index_says_open_access=source.access_state == OPEN_ACCESS_STATE,
        document_type=document_type_of(source),
        possible_duplicate=is_duplicate,
        abstract_sources=len(scope.abstracts),
        abstracts_disagree=scope.abstracts_disagree,
    )


async def screening_cards(session: AsyncSession, *, tenant_id: uuid.UUID,
                          project_id: uuid.UUID,
                          use_states: Iterable[str] | None = None) -> list[ScreeningCard]:
    """بطاقات الفرز — ثلاث عبارات مهما بلغ عدد المراجع."""
    stmt = (
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id)
        .order_by(ProjectSource.created_at.desc(), ProjectSource.id.desc())
    )
    wanted = tuple(use_states) if use_states else ()
    if wanted:
        stmt = stmt.where(ProjectSource.use_state.in_(wanted))
    rows = (await session.execute(stmt)).all()

    files = await readable_project_file_ids(
        session, tenant_id=tenant_id, project_id=project_id)
    source_ids = [source.id for _link, source in rows]
    names = await authors_by_source(session, tenant_id=tenant_id, source_ids=source_ids)
    abstracts = await stored_abstracts_by_source(
        session, tenant_id=tenant_id, source_ids=source_ids)
    return [
        card_of(link, source, authors=names.get(source.id, []),
                scope=reading_scope(source, project_file_ids=files,
                                    stored_abstracts=abstracts.get(source.id, ())))
        for link, source in rows
    ]


def metadata_cell(field_key: str, source: Source, authors: list[str]) -> MatrixCellView:
    """عمودان يُقرآن من البيانات الوصفية — **وحالهما `missing` عند غيابها**.

    ولا يُخزَّنان صفًّا: قيمتهما هي المرجع نفسه، فلو خُزّنت لافترقت عنه بأول
    تصحيحٍ للسنة أو للعنوان، وصار في الشاشة مرجعان لواحد.
    """
    if field_key == "year":
        value = str(source.publication_year) if source.publication_year else None
    else:
        lead = authors[0] if authors else None
        value = f"{lead} — {source.title}" if lead else source.title
    return MatrixCellView(
        field_key=field_key,
        value_ar=value,
        cell_state="known" if value else "missing",
        source_scope=METADATA_ONLY,
        extraction_method="metadata",
        verification_status="unverified",
    )


def cell_view(cell: LiteratureMatrixCell,
              abstract_providers: dict[uuid.UUID, str] | None = None) -> MatrixCellView:
    """خليةٌ مخزَّنة كما تُعرض — **بمَداها ومَن أرسل ما قُرئ منه**.

    واسمُ الفهرس يُعرض بجانب القيمة لا في تفصيلٍ يُفتح: من يقرأ «العيّنة ٤٢٥»
    يحتاج أن يعرف أنها من ملخّص Crossref قبل أن يعتمدها، لا بعده.
    """
    providers = abstract_providers or {}
    return MatrixCellView(
        field_key=cell.field_key, value_ar=cell.value_ar,
        cell_state=cell.cell_state, source_scope=cell.source_scope,
        extraction_method=cell.extraction_method,
        verification_status=cell.verification_status,
        source_file_id=cell.source_file_id,
        evidence_quote=cell.evidence_quote,
        evidence_locator=cell.evidence_locator,
        source_abstract_id=cell.source_abstract_id,
        abstract_provider=providers.get(cell.source_abstract_id)
        if cell.source_abstract_id else None,
        evidence_page=cell.evidence_page,
        evidence_section=cell.evidence_section,
    )


def empty_cell(field_key: str, scope: str) -> MatrixCellView:
    """خليةٌ لم تُملأ بعد — **`missing` صريحة، لا خانةٌ بيضاء**.

    والفرق ليس شكليًّا: الخانة البيضاء تُقرأ «لا شيء يستحق الذكر»، و
    `missing` تُقرأ «لم يُذكر» — والثانية وحدها فجوةٌ تُعالَج.
    """
    return MatrixCellView(
        field_key=field_key,
        value_ar=None,
        cell_state="missing",
        source_scope=scope,
        extraction_method="researcher",
        verification_status="unverified",
    )


async def included_source_count(session: AsyncSession, *, tenant_id: uuid.UUID,
                                project_id: uuid.UUID) -> int:
    """كم دراسةً مُدرَجة في هذا البحث — **من القاعدة لا من طول الصفحة**."""
    return (await session.execute(
        select(func.count(ProjectSource.id)).where(
            ProjectSource.tenant_id == tenant_id,
            ProjectSource.project_id == project_id,
            ProjectSource.use_state == "included")
    )).scalar_one()


async def matrix_rows(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID, page: int = 1,
                      page_size: int = DEFAULT_PAGE_SIZE) -> list[MatrixRow]:
    """مصفوفة الأدبيات — **للمُدرَجة وحدها**، صفحةً صفحة.

    ومرجعٌ «محفوظ فقط» ليس دليلًا بعد؛ ووضعُه في المصفوفة يجعل الباحث يبني
    تحليله على ما لم يقرّر بعدُ أنه دليل. أما المستبعَد فقراره أن يُترك.

    والتصفيح هنا كتصفيح الفرز: ستّةَ عشرَ عمودًا في ألف صفٍّ ستةَ عشرَ ألف
    خلية في جوابٍ واحد — والمتصفّح يتوقّف قبل أن يُنهي رسمها.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    rows = (await session.execute(
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id,
               ProjectSource.use_state == "included")
        # الترتيب بمفتاحٍ فريد في آخره: العنوان يتكرّر، والسنة أكثر، فتتبدّل
        # الصفوف بين صفحتين ويظهر مرجعٌ مرّتين ويغيب آخر.
        .order_by(Source.publication_year.desc().nullslast(), Source.title, Source.id)
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    if not rows:
        return []

    source_ids = [source.id for _link, source in rows]
    files = await readable_project_file_ids(
        session, tenant_id=tenant_id, project_id=project_id)
    names = await authors_by_source(session, tenant_id=tenant_id, source_ids=source_ids)
    stored_abstracts = await stored_abstracts_by_source(
        session, tenant_id=tenant_id, source_ids=source_ids)
    abstract_providers = {
        row.id: row.provider
        for rows_for_source in stored_abstracts.values() for row in rows_for_source
    }

    stored = (await session.execute(
        select(LiteratureMatrixCell).where(
            LiteratureMatrixCell.tenant_id == tenant_id,
            LiteratureMatrixCell.project_id == project_id,
            LiteratureMatrixCell.source_id.in_(source_ids))
    )).scalars().all()
    by_key: dict[tuple[uuid.UUID, str], LiteratureMatrixCell] = {
        (cell.source_id, cell.field_key): cell for cell in stored
    }

    out: list[MatrixRow] = []
    for _link, source in rows:
        authors = names.get(source.id, [])
        scope = reading_scope(source, project_file_ids=files,
                              stored_abstracts=stored_abstracts.get(source.id, ()))
        cells: list[MatrixCellView] = []
        for field_key in MATRIX_FIELDS:
            cell = by_key.get((source.id, field_key))
            if cell is not None:
                cells.append(cell_view(cell, abstract_providers))
            elif field_key in METADATA_FIELDS:
                cells.append(metadata_cell(field_key, source, authors))
            else:
                cells.append(empty_cell(field_key, scope.scope))
        out.append(MatrixRow(
            source_id=source.id, title=source.title, authors=authors,
            publication_year=source.publication_year,
            doi=source.doi if source.verification_status == "verified" else None,
            reading_scope=scope.scope, cells=cells))
    return out


async def file_is_in_project(session: AsyncSession, *, tenant_id: uuid.UUID,
                             project_id: uuid.UUID, file_id: uuid.UUID) -> bool:
    """هل هذا الملف مرتبطٌ بهذا البحث قائمًا؟ — شرطُ نسبةِ خليةٍ إليه."""
    row = (await session.execute(
        select(ProjectFile.id)
        .join(File, File.id == ProjectFile.file_id)
        .where(ProjectFile.tenant_id == tenant_id,
               ProjectFile.project_id == project_id,
               ProjectFile.file_id == file_id,
               ProjectFile.state == ProjectFile.ACTIVE)
        .limit(1)
    )).first()
    return row is not None


__all__ = [
    "ABSTRACT_ONLY",
    "DEFAULT_PAGE_SIZE",
    "FULL_TEXT",
    "MAX_PAGE_SIZE",
    "METADATA_FIELDS",
    "METADATA_ONLY",
    "OPEN_ACCESS_STATE",
    "AbstractRecord",
    "MatrixCellView",
    "MatrixRow",
    "ReadingScope",
    "ScreeningCard",
    "ScreeningFilters",
    "ScreeningPage",
    "ScreeningTallies",
    "abstract_digest",
    "abstract_of",
    "abstracts_of",
    "apply_filters",
    "authors_by_source",
    "card_of",
    "cell_view",
    "dedup_key_expr",
    "derived_abstracts",
    "document_type_of",
    "duplicate_source_ids",
    "empty_cell",
    "file_is_in_project",
    "has_abstract_expr",
    "included_source_count",
    "locator_is_honest",
    "matrix_rows",
    "metadata_cell",
    "project_file_ids",
    "readable_project_file_ids",
    "reading_scope",
    "reason_is_acceptable",
    "screening_cards",
    "screening_page",
    "screening_tallies",
    "stored_abstracts_by_source",
]
