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

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# **الاقتباس لا يُكرَّر.** بناءُ الملخّص من ترميز JATS ومن الفهرس المقلوب
# محلولٌ في حزمة الاكتشاف وقد فُحص هناك؛ ونسخةٌ ثانية منه تفترق عن الأولى
# بأول إصلاح، فيقرأ مساران ملخّصين مختلفين للورقة نفسها.
from ..discovery.crossref import _abstract as _abstract_from_jats
from ..discovery.openalex import _abstract as _abstract_from_inverted
from ..models.files import File
from ..models.literature import ACCESS_STATES, Author, Source, SourceAuthor
from ..models.portfolio import ProjectFile, ProjectSource
from ..models.screening import (
    ABSTRACT_LOCATOR,
    EXCLUSION_REASON_CODES,
    FREE_TEXT_REASON_CODE,
    MATRIX_FIELDS,
    LiteratureMatrixCell,
    scope_rank,
)

METADATA_ONLY = "metadata_only"
ABSTRACT_ONLY = "abstract_only"
FULL_TEXT = "full_text"

# الأعمدة التي تُقرأ من البيانات الوصفية وحدها — وهي اثنان لا أكثر.
# **وما عداهما لا يُملأ آليًّا أبدًا**: منهجٌ أو عيّنةٌ أو مقياسٌ لا يُستخرج
# من عنوانٍ وسنة، ومن ملأها من البيانات الوصفية فقد اخترع.
METADATA_FIELDS = ("reference", "year")


@dataclass(frozen=True, slots=True)
class ReadingScope:
    """ما يمكن قراءته من هذا المرجع في هذا البحث — **لا ما يُدّعى**."""

    scope: str
    abstract: str | None = None
    # الملف الذي يجعل `full_text` ممكنة. غيابه يعني أن النصّ ليس في اليد،
    # مهما قال الفهرس عن انفتاح الوصول.
    file_id: uuid.UUID | None = None

    def permits(self, requested: str) -> bool:
        return scope_rank(requested) <= scope_rank(self.scope)


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
    decided_at: object | None = None
    added_at: object | None = None
    reading_scope: str = METADATA_ONLY
    has_abstract: bool = False


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


def reading_scope(source: Source, *, project_file_ids: set[uuid.UUID]) -> ReadingScope:
    """أقصى مدًى صادق لهذا المرجع في هذا البحث.

    **`full_text` تعني أن النصّ في اليد**، لا أن الفهرس قال إنه مفتوح: حقّ
    المعالجة شرطٌ أول (§14.2)، ووجودُ ملفٍّ مرتبطٍ بهذا البحث شرطٌ ثانٍ. فمن
    لم يرفع الورقة لم يقرأها — وشاشةٌ تسمح له بادّعاء قراءتها تكذب نيابةً
    عنه في مصفوفةٍ ستُكتب منها ورقة.
    """
    abstract = abstract_of(source)
    text_bearing = ACCESS_STATES.get(source.access_state, False)
    file_id = source.file_id if source.file_id in project_file_ids else None
    if text_bearing and file_id is not None:
        return ReadingScope(FULL_TEXT, abstract, file_id)
    if abstract:
        return ReadingScope(ABSTRACT_ONLY, abstract, file_id)
    return ReadingScope(METADATA_ONLY, abstract, file_id)


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


def card_of(link: ProjectSource, source: Source, *, authors: list[str],
            scope: ReadingScope) -> ScreeningCard:
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

    files = await project_file_ids(session, tenant_id=tenant_id, project_id=project_id)
    names = await authors_by_source(
        session, tenant_id=tenant_id, source_ids=[source.id for _link, source in rows])
    return [
        card_of(link, source, authors=names.get(source.id, []),
                scope=reading_scope(source, project_file_ids=files))
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


async def matrix_rows(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID) -> list[MatrixRow]:
    """مصفوفة الأدبيات — **للمُدرَجة وحدها**.

    ومرجعٌ «محفوظ فقط» ليس دليلًا بعد؛ ووضعُه في المصفوفة يجعل الباحث يبني
    تحليله على ما لم يقرّر بعدُ أنه دليل. أما المستبعَد فقراره أن يُترك.
    """
    rows = (await session.execute(
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id,
               ProjectSource.use_state == "included")
        .order_by(Source.publication_year.desc().nullslast(), Source.title)
    )).all()
    if not rows:
        return []

    source_ids = [source.id for _link, source in rows]
    files = await project_file_ids(session, tenant_id=tenant_id, project_id=project_id)
    names = await authors_by_source(session, tenant_id=tenant_id, source_ids=source_ids)

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
        scope = reading_scope(source, project_file_ids=files)
        cells: list[MatrixCellView] = []
        for field_key in MATRIX_FIELDS:
            cell = by_key.get((source.id, field_key))
            if cell is not None:
                cells.append(MatrixCellView(
                    field_key=cell.field_key, value_ar=cell.value_ar,
                    cell_state=cell.cell_state, source_scope=cell.source_scope,
                    extraction_method=cell.extraction_method,
                    verification_status=cell.verification_status,
                    source_file_id=cell.source_file_id,
                    evidence_quote=cell.evidence_quote,
                    evidence_locator=cell.evidence_locator))
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
    "FULL_TEXT",
    "METADATA_FIELDS",
    "METADATA_ONLY",
    "MatrixCellView",
    "MatrixRow",
    "ReadingScope",
    "ScreeningCard",
    "abstract_of",
    "authors_by_source",
    "card_of",
    "empty_cell",
    "file_is_in_project",
    "locator_is_honest",
    "matrix_rows",
    "metadata_cell",
    "project_file_ids",
    "reading_scope",
    "reason_is_acceptable",
    "screening_cards",
]
