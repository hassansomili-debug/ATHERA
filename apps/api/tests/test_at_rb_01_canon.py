"""AT-RB-01 — سجل المراجع المنهجية: المجهول ليس إذنًا.

الاختبار الأهم في هذا الملف هو `test_nothing_in_the_canon_may_be_ingested_today`.
سجلٌّ يظهر فيه مرجعٌ واحد مأذون بلا أن يفحصه أحد يعني أن الاستيعاب صار
ممكنًا بسطرٍ لا يلاحظه مراجع.
"""
import datetime as dt

import pytest
from pydantic import ValidationError

from athera_api.research_brain import canon


def test_nothing_in_the_canon_may_be_ingested_today():
    """لا مرجع مأذون — والقائمة فارغة لأن أحدًا لم يفحص، لا لأنها نُسيت."""
    assert canon.ingestible() == ()
    assert all(not canon.may_ingest(source) for source in canon.CANON)


def test_every_source_starts_unknown_and_unverified():
    for source in canon.CANON:
        assert source.ingestion_permission is canon.IngestionPermission.UNKNOWN, source.id
        assert source.verification_status is canon.VerificationStatus.UNVERIFIED, source.id
        assert source.reviewed_by is None and source.reviewed_at is None, source.id


def test_unknown_is_not_denied_and_neither_is_permission():
    """ثلاث حالات لا حالتان — والرسالة تفرّق بينها لأن العمل المطلوب مختلف."""
    unknown = canon.CANON[0]
    denied = unknown.model_copy(update={"ingestion_permission": canon.IngestionPermission.DENIED})

    assert not canon.may_ingest(unknown)
    assert not canon.may_ingest(denied)
    assert unknown.ingestion_permission is not denied.ingestion_permission

    unknown_ar, unknown_en = canon.ingestion_reason(unknown)
    denied_ar, denied_en = canon.ingestion_reason(denied)
    assert unknown_ar != denied_ar and unknown_en != denied_en
    assert "لم يُفحص" in unknown_ar
    assert "not unchecked" in denied_en or "recorded decision" in denied_en


def test_granted_without_a_basis_is_refused():
    """إذنٌ بلا مستندٍ مسمّى لا يُبنى أصلًا — لا يُبنى ثم يُرفض."""
    with pytest.raises(ValidationError):
        canon.MethodologySource(
            id="x-1", title="Some Handbook", author="Someone", language="en",
            domain="research_design", source_type=canon.SourceType.HANDBOOK,
            ingestion_permission=canon.IngestionPermission.GRANTED,
            verification_status=canon.VerificationStatus.VERIFIED,
            reviewed_by="reviewer", reviewed_at=dt.datetime.now(dt.UTC),
        )


def test_a_basis_without_a_grant_is_refused():
    """مستندُ إذنٍ مسجَّل مع إذنٍ غير ممنوح يوهم بإذنٍ لم يُمنح."""
    with pytest.raises(ValidationError):
        canon.MethodologySource(
            id="x-2", title="Some Handbook", author="Someone", language="en",
            domain="research_design", source_type=canon.SourceType.HANDBOOK,
            permission_basis="a licence we do not have",
        )


def test_granted_requires_a_verified_source():
    """لا يُؤذن باستيعاب مرجعٍ لم يُتحقَّق أنه هو."""
    with pytest.raises(ValidationError):
        canon.MethodologySource(
            id="x-3", title="Some Handbook", author="Someone", language="en",
            domain="research_design", source_type=canon.SourceType.HANDBOOK,
            ingestion_permission=canon.IngestionPermission.GRANTED,
            permission_basis="publisher agreement 2026-01",
        )


def test_verified_requires_a_named_reviewer_and_a_date():
    """الحالة نفسها التي يفرضها `ck_source_verified_requires_registry_or_upload`."""
    with pytest.raises(ValidationError):
        canon.MethodologySource(
            id="x-4", title="Some Handbook", author="Someone", language="en",
            domain="research_design", source_type=canon.SourceType.HANDBOOK,
            verification_status=canon.VerificationStatus.VERIFIED,
        )


def test_a_fully_documented_grant_is_accepted():
    """المسار المشروع موجود — والقيود تمنع الاختصار لا الطريق."""
    source = canon.MethodologySource(
        id="x-5", title="An Open Standard", author="A Working Group", language="en",
        domain="reporting", source_type=canon.SourceType.REPORTING_STANDARD,
        license_status=canon.LicenseStatus.OPEN_LICENCE,
        copyright_status=canon.CopyrightStatus.RIGHTS_CLEARED,
        ingestion_permission=canon.IngestionPermission.GRANTED,
        permission_basis="CC BY 4.0, checked 2026-09-01",
        verification_status=canon.VerificationStatus.VERIFIED,
        reviewed_by="legal-review", reviewed_at=dt.datetime.now(dt.UTC),
    )
    assert canon.may_ingest(source)


def test_the_registry_holds_no_text_of_any_source():
    """العقد بلا حقلٍ للمتن — و`extra="forbid"` يمنع تهريبه في حقلٍ إضافي."""
    field_names = set(canon.MethodologySource.model_fields)
    assert not field_names & {"text", "content", "body", "excerpt", "quote", "full_text"}
    with pytest.raises(ValidationError):
        canon.MethodologySource(
            id="x-6", title="A Book", author="Someone", language="en", domain="d",
            source_type=canon.SourceType.TEXTBOOK, full_text="chapter one …",
        )


def test_ids_are_unique_and_looked_up():
    ids = [source.id for source in canon.CANON]
    assert len(ids) == len(set(ids))
    assert canon.get(ids[0]) is canon.CANON[0]
    assert canon.get("no-such-source") is None


def test_verification_states_match_the_sources_table():
    """المفردة منقولة عن `ck_source_status` في ترحيل 0008، لا مخترعة."""
    assert canon.VERIFICATION_STATES == ("unverified", "verified", "rejected")
    assert {s.value for s in canon.VerificationStatus} == set(canon.VERIFICATION_STATES)
