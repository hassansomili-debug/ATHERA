"""التحقق من المصادر | Source verification (§14.3، §14.5، TC-02).

DOI لا يُحلّ في أي سجل **لا يُخزَّن متحققًا ولا يُختلق له بديل**. هذا هو
الفرق العملي بين منصة أدلة ومولّد نصوص.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...errors import AtheraError, NotFound
from ...models.literature import Journal, Source, SourceVersion
from .. import audit
from .registry import RegistryRecord, SourceNotFound, SourceRegistry, normalize_doi


class SourceVerificationError(AtheraError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code, status_code=422, **context)


async def resolve_doi(registries: list[SourceRegistry], doi: str) -> tuple[RegistryRecord, str]:
    """يجرب السجلات بالترتيب ويعيد أول تطابق.

    الترتيب يتبع §33.2: بيانات علمية رسمية قبل أي شيء آخر. وإذا لم يُحلّ في
    أي سجل تُرفع `SourceNotFound` — ولا يُبنى سجل من فراغ.
    """
    normalized = normalize_doi(doi)
    if normalized is None:
        raise SourceVerificationError("evidence.invalid_doi", doi=doi)

    errors: list[str] = []
    for registry in registries:
        try:
            return await registry.get_by_doi(normalized), registry.name
        except SourceNotFound:
            errors.append(registry.name)
    raise SourceNotFound(f"{normalized} not found in: {', '.join(errors)}")


async def import_source(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    record: RegistryRecord,
    registry_name: str,
) -> Source:
    """يخزّن مصدرًا متحققًا من سجل خارجي، مع لقطة حالته."""
    now = dt.datetime.now(dt.UTC)

    journal_id = None
    if record.journal_name:
        journal = (
            await session.execute(select(Journal).where(Journal.name == record.journal_name))
        ).scalar_one_or_none()
        if journal is None:
            journal = Journal(
                tenant_id=tenant_id, name=record.journal_name, issn=record.issn,
                is_open_access=record.is_open_access,
            )
            session.add(journal)
            await session.flush()
        journal_id = journal.id

    existing = None
    if record.doi:
        existing = (
            await session.execute(select(Source).where(Source.doi == record.doi))
        ).scalar_one_or_none()

    source = existing or Source(tenant_id=tenant_id, title=record.title)
    source.doi = record.doi
    source.title = record.title
    source.publication_year = record.publication_year
    source.journal_id = journal_id
    source.journal_name_raw = record.journal_name
    source.retraction_status = record.retraction_status
    source.retraction_detail = record.retraction_detail
    source.access_state = record.access_state
    source.registry = registry_name
    source.registry_id = record.registry_id
    source.last_verified_at = now
    source.verification_status = "verified"
    # §33.3 — تُحفظ كما وردت، ولا تُقرأ منها تعليمات.
    source.raw_metadata = record.raw
    if existing is None:
        session.add(source)
    await session.flush()

    session.add(SourceVersion(
        tenant_id=tenant_id, source_id=source.id, checked_at=now, registry=registry_name,
        retraction_status=record.retraction_status, access_state=record.access_state,
        snapshot={"title": record.title, "year": record.publication_year,
                  "journal": record.journal_name, "authors": record.authors},
    ))

    await audit.record(
        session, tenant_id=tenant_id, action="evidence.source_imported",
        object_type="source", object_id=source.id, actor_user_id=actor_user_id,
        state_after={
            "doi": record.doi, "registry": registry_name,
            "retraction_status": record.retraction_status, "access_state": record.access_state,
        },
        reason="source resolved from an external registry and snapshotted",
        source_refs=[{"registry": registry_name, "registry_id": record.registry_id}],
    )
    return source


async def revalidation_doi(
    session: AsyncSession, *, source_id: uuid.UUID,
) -> str:
    """طورُ التحضير: يتحقّق من المصدر ويُخرج **معرّفَه نصًّا** (RC-T1-H3).

    ولا يُعيد صفَّ ORM: الصفُّ يموت بموت معاملته، والنداءُ الخارجيُّ يقع
    بعدها. فيُحمَل DOI وحدَه، ويُعاد تحميلُ الصفِّ في معاملة الإنهاء.

    ورموزُ الإخفاق هي نفسُها ومواضعُها نفسُها: مصدرٌ غائب ٤٠٤، ومصدرٌ بلا
    DOI خطأُ تحقّقٍ — **قبل** أيّ نداءٍ خارجيّ.
    """
    source = (await session.execute(
        select(Source).where(Source.id == source_id))).scalar_one_or_none()
    if source is None:
        raise NotFound("evidence.source_not_found")
    if not source.doi:
        raise SourceVerificationError("evidence.source_has_no_doi",
                                      source_id=str(source_id))
    return source.doi


async def apply_revalidation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    source_id: uuid.UUID,
    record: RegistryRecord,
    registry_name: str,
    resolved_doi: str,
) -> tuple[Source, bool]:
    """طورُ الإنهاء: يُثبِّت نتيجةَ فحصٍ **جُلبت خارج المعاملة**.

    ## و«تغيّر» تُحسب على الحالِ الراهنة لا البائتة

    الفارقُ يُقاس بين ما في القاعدة **الآن** وما قاله الفهرس — لا بين ما
    كان وقت التحضير. فلو كتب كاتبٌ آخر حالةً أثناء الانتظار، فالانتقالُ
    المُعلَن هو الانتقالُ الواقع، ولا يُفتح تنبيهُ نزاهةٍ على فرقٍ وهميّ.

    ## ولا يُكتب فحصُ ورقةٍ على ورقةٍ أخرى

    وإن تغيّر DOI المصدر بين التحضير والإنهاء فالسجلُّ الذي جُلب يصف **عملًا
    آخر**. فيُرفض التثبيتُ صريحًا (٤٠٩) ولا يُكتب فوق حالٍ أحدث — وهذا حدٌّ
    ضيّقٌ لموضعه، لا قُفلٌ تشاؤميٌّ عامّ.
    """
    source = (await session.execute(
        select(Source).where(Source.id == source_id))).scalar_one_or_none()
    if source is None:
        # حُذف أثناء الانتظار — والرمزُ هو رمزُ الغياب نفسُه.
        raise NotFound("evidence.source_not_found")
    if source.doi != resolved_doi:
        raise AtheraError("evidence.source_changed_during_verification",
                          status_code=409, source_id=str(source_id))

    previous = source.retraction_status
    changed = previous != record.retraction_status
    now = dt.datetime.now(dt.UTC)

    source.retraction_status = record.retraction_status
    source.retraction_detail = record.retraction_detail
    source.last_verified_at = now

    session.add(SourceVersion(
        tenant_id=tenant_id, source_id=source.id, checked_at=now, registry=registry_name,
        retraction_status=record.retraction_status, access_state=source.access_state,
        snapshot={"revalidation": True, "previous_retraction_status": previous},
    ))

    if changed:
        from ...models.audit import IntegrityAlert  # noqa: PLC0415

        session.add(IntegrityAlert(
            tenant_id=tenant_id, alert_type="source_retraction_changed", severity="critical",
            name_ar="تغيّرت حالة السحب/التصحيح لمصدر مستشهد به",
            name_en="Retraction status changed for a cited source",
            detail_ar=f"من «{previous}» إلى «{record.retraction_status}» للمصدر {source.doi}.",
            detail_en=f"From '{previous}' to '{record.retraction_status}' for {source.doi}.",
            object_type="source", object_id=source.id,
        ))

    await audit.record(
        session, tenant_id=tenant_id, action="evidence.source_revalidated",
        object_type="source", object_id=source.id, actor_user_id=actor_user_id,
        state_before={"retraction_status": previous},
        state_after={"retraction_status": record.retraction_status, "changed": changed},
    )
    return source, changed


async def revalidate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    source_id: uuid.UUID,
    registries: list[SourceRegistry],
) -> tuple[Source, bool]:
    """الطورانِ مجتمعانِ في معاملة المستدعي — **لمن يملكها** لا لمسارِ طلب.

    ومسارُ الطلب يستدعي الطورَين مفصولَين، وإلّا امتدّت معاملتُه عبر
    الشبكة (RC-T1-H3). وهذه تبقى لنصٍّ أو مهمّةٍ تملك معاملتَها وتقبل
    طولَها.
    """
    doi = await revalidation_doi(session, source_id=source_id)
    record, registry_name = await resolve_doi(registries, doi)
    return await apply_revalidation(
        session, tenant_id=tenant_id, actor_user_id=actor_user_id,
        source_id=source_id, record=record, registry_name=registry_name,
        resolved_doi=doi)
