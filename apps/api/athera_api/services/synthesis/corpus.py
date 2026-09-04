"""لقطةُ مجموعة المراجع | The reference-set snapshot (PUBRIVA).

**لقطةٌ خالصة لا جلسة.** الدرس مسجَّل في `drafting/context.py` و
`planning/context.py` و`research_brain/rules.py`: بنيةٌ تعبر حدّ المعاملة
وهي تحمل كائن ORM حيًّا تقرأ لاحقًا من قاعدةٍ أُغلقت. وهنا سببٌ ثانٍ أهمّ:
كلّ استدلالِ هذه الطبقة يصير قابلًا للاختبار بلا قاعدة بيانات — فتُثبت
الاختبارات السلبية الخمس بدل أن تُوعَد.

**والمجموعة هي المُدرَجة وحدها.** مرجعٌ «محفوظ فقط» لم يُقرَّر بعدُ أنه
دليل، والمستبعَد قراره أن يُترك. لكن **عددَي المحفوظ والمستبعَد يُحملان مع
اللقطة**: فجوةٌ تُقاس على اثني عشر مُدرَجًا بينما أربعون مرجعًا محفوظًا لم
يُفرَز بعد هي فجوةٌ عن فرزٍ لم يكتمل، والباحث يجب أن يرى ذلك.

**ومدى البحث يُقال كما هو.** `indexes_searched` هي الفهارس التي **جاءت
منها** مراجع هذه المجموعة، لا فهارس بُحثت بحثًا منهجيًّا. و
`search_was_systematic` تبقى `False` لأن المنصّة لا تُجري بحثًا منهجيًّا
هنا — والادّعاء بغير ذلك يجعل «لم تظهر دراسة» تُقرأ نتيجةَ مسحٍ شامل.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.literature import Source
from ...models.portfolio import ProjectSource
from ...models.screening import LiteratureMatrixCell
from ..screening import METADATA_FIELDS, project_file_ids, reading_scope

# أعمدةُ المصفوفة التي تحمل **محتوًى مقروءًا** لا بياناتٍ وصفية. وموضوعٌ
# علميّ لا يُسنَد إلا من هذه؛ و`reference`/`year` تصنع تجميعًا موضوعيًّا.
CONTENT_FIELDS: Final = (
    "problem", "objective", "theory", "design", "method", "population", "sample",
    "context", "constructs", "measures", "analysis", "findings", "limitations", "gaps",
)

# الحالات التي تعني «فيها قولٌ يُقرأ». و`missing` ليست منها: الغياب غيابٌ،
# والبناءُ عليه اختراع.
STATED_CELL_STATES: Final = ("known", "needs_review", "conflicting")


@dataclass(frozen=True, slots=True)
class CellSnapshot:
    """خليةُ مصفوفةٍ كما سُجِّلت — **بمعرّفها**، وهو أول حلقةٍ في سلسلة الأثر."""

    cell_id: uuid.UUID | None
    source_id: uuid.UUID
    field_key: str
    value_ar: str | None
    cell_state: str
    source_scope: str
    extraction_method: str
    verification_status: str
    evidence_quote: str | None = None
    evidence_locator: str | None = None

    @property
    def is_stated(self) -> bool:
        """هل تحمل قولًا؟ — و«غير مذكور» لا تحمل، مهما بدت مملوءة."""
        return self.cell_state in STATED_CELL_STATES and bool(
            (self.value_ar or "").strip())


@dataclass(frozen=True, slots=True)
class StudySnapshot:
    """دراسةٌ مُدرَجة بخلاياها — ومَداها المتاح كما حسبته خدمة الفرز."""

    source_id: uuid.UUID
    title: str
    publication_year: int | None
    reading_scope: str
    cells: tuple[CellSnapshot, ...] = ()

    def cell(self, field_key: str) -> CellSnapshot | None:
        for row in self.cells:
            if row.field_key == field_key:
                return row
        return None

    def stated(self, field_key: str) -> CellSnapshot | None:
        """الخلية إن كانت تحمل قولًا — و`None` عند الصمت أو الغياب."""
        found = self.cell(field_key)
        return found if found is not None and found.is_stated else None

    def text_of(self, *field_keys: str) -> str | None:
        """نصُّ أول عمودٍ مذكور من هذه الأعمدة — ولا يُلفَّق من عمودٍ آخر."""
        for key in field_keys:
            found = self.stated(key)
            if found is not None:
                return found.value_ar
        return None

    @property
    def has_content(self) -> bool:
        """هل قُرئ من هذه الدراسة محتوًى أصلًا؟ — عنوانٌ وسنةٌ ليسا محتوًى."""
        return any(row.field_key in CONTENT_FIELDS and row.is_stated
                   for row in self.cells)


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    """ما نظرنا فيه — **وحدودُه جزءٌ منه لا حاشيةٌ عليه**."""

    project_id: uuid.UUID
    studies: tuple[StudySnapshot, ...] = ()
    # الفهارس التي جاءت منها هذه المراجع. و«رفع الباحث» واحدٌ منها.
    registries: tuple[str, ...] = ()
    saved_only_count: int = 0
    excluded_count: int = 0
    taken_at: dt.datetime | None = None

    @property
    def size(self) -> int:
        return len(self.studies)

    @property
    def scope_distribution(self) -> dict[str, int]:
        """كم دراسةً قُرئت من بياناتٍ وصفية، وكم من ملخّص، وكم نصًّا كاملًا.

        وهذا الرقم هو ما يمنع «فجوة» مبنيّة على اثنتي عشرة دراسةً لم يُقرأ
        من إحداها سطرٌ واحد.
        """
        out: dict[str, int] = {}
        for study in self.studies:
            out[study.reading_scope] = out.get(study.reading_scope, 0) + 1
        return out

    @property
    def content_read_count(self) -> int:
        return sum(1 for study in self.studies if study.has_content)

    @property
    def full_text_count(self) -> int:
        return sum(1 for study in self.studies if study.reading_scope == "full_text")

    def search_scope(self) -> dict:
        """**مدى البحث كما هو، لا كما نتمنّاه.**

        `search_was_systematic` تبقى `False`: هذه المجموعة ما جمعه الباحث،
        وليست حصيلةَ استعلامٍ منهجيّ على الفهارس. والفرق هو الفرق بين «لم
        تظهر في مجموعتي» و«لا توجد» — وهو كل شيء في هذه الطبقة.
        """
        return {
            "indexes_searched": list(self.registries),
            "search_was_systematic": False,
            "corpus_size": self.size,
            "content_read": self.content_read_count,
            "full_text_read": self.full_text_count,
            "saved_not_screened": self.saved_only_count,
            "excluded": self.excluded_count,
            "taken_at": self.taken_at.isoformat() if self.taken_at else None,
        }

    def study(self, source_id: uuid.UUID) -> StudySnapshot | None:
        for row in self.studies:
            if row.source_id == source_id:
                return row
        return None


async def load_corpus(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID,
                      taken_at: dt.datetime | None = None) -> CorpusSnapshot:
    """يقرأ المجموعة مرّةً واحدة ويُغلق على لقطةٍ خالصة.

    وثلاث عبارات مهما بلغ عدد المراجع — كما في `screening.screening_cards`:
    عبارةٌ لكل دراسة تُعيد عطب `1 + N` الذي بلغ ثلاثين ثانية في `GET /files`.
    """
    rows = (await session.execute(
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id,
               ProjectSource.use_state == "included")
        .order_by(Source.publication_year.desc().nullslast(), Source.title, Source.id)
    )).all()

    tallies = dict((await session.execute(
        select(ProjectSource.use_state, func.count(ProjectSource.id))
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id)
        .group_by(ProjectSource.use_state)
    )).all())

    if not rows:
        return CorpusSnapshot(
            project_id=project_id,
            saved_only_count=tallies.get("saved_only", 0),
            excluded_count=tallies.get("excluded", 0),
            taken_at=taken_at,
        )

    source_ids = [source.id for _link, source in rows]
    files = await project_file_ids(session, tenant_id=tenant_id, project_id=project_id)
    stored = (await session.execute(
        select(LiteratureMatrixCell).where(
            LiteratureMatrixCell.tenant_id == tenant_id,
            LiteratureMatrixCell.project_id == project_id,
            LiteratureMatrixCell.source_id.in_(source_ids))
    )).scalars().all()

    by_source: dict[uuid.UUID, list[CellSnapshot]] = {}
    for cell in stored:
        by_source.setdefault(cell.source_id, []).append(CellSnapshot(
            cell_id=cell.id, source_id=cell.source_id, field_key=cell.field_key,
            value_ar=cell.value_ar, cell_state=cell.cell_state,
            source_scope=cell.source_scope, extraction_method=cell.extraction_method,
            verification_status=cell.verification_status,
            evidence_quote=cell.evidence_quote, evidence_locator=cell.evidence_locator))

    studies: list[StudySnapshot] = []
    registries: set[str] = set()
    for _link, source in rows:
        # **العنوان والسنة لا يُخزَّنان خلايا** (خدمة الفرز)، فتُبنى لهما
        # لقطتان هنا بمعرّفٍ فارغ: هما بياناتٌ وصفية، وسندٌ منهما لا يبلغ
        # موضوعًا علميًّا أبدًا.
        cells = list(by_source.get(source.id, []))
        present = {row.field_key for row in cells}
        for field_key in METADATA_FIELDS:
            if field_key in present:
                continue
            value = (str(source.publication_year) if field_key == "year"
                     and source.publication_year else
                     source.title if field_key == "reference" else None)
            cells.append(CellSnapshot(
                cell_id=None, source_id=source.id, field_key=field_key,
                value_ar=value, cell_state="known" if value else "missing",
                source_scope="metadata_only", extraction_method="metadata",
                verification_status="unverified"))
        scope = reading_scope(source, project_file_ids=files)
        studies.append(StudySnapshot(
            source_id=source.id, title=source.title,
            publication_year=source.publication_year, reading_scope=scope.scope,
            cells=tuple(sorted(cells, key=lambda c: c.field_key))))
        registries.add(source.registry or "upload")

    return CorpusSnapshot(
        project_id=project_id,
        studies=tuple(studies),
        registries=tuple(sorted(registries)),
        saved_only_count=tallies.get("saved_only", 0),
        excluded_count=tallies.get("excluded", 0),
        taken_at=taken_at,
    )


__all__ = [
    "CONTENT_FIELDS",
    "STATED_CELL_STATES",
    "CellSnapshot",
    "CorpusSnapshot",
    "StudySnapshot",
    "load_corpus",
]
