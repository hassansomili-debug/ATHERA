"""ما يمنع الآن يصل الشاشة | The current blocker must survive the contract.

**العطبُ الذي بلغ الإنتاج، وكيف نجا من الفحوص.**

‏`journey.view` تحسب `current_blocking_reasons` وتضعها في قاموسها. والموجّه
يبني `JourneyResponse(**view)`. و`extra="ignore"` هي الافتراضُ في Pydantic،
والنموذجُ لم يكن يُعلن الحقل — **فيُطرح المفتاحُ بلا خطأٍ ولا تحذير**.

فتقرأ الشاشةُ `undefined` دائمًا، وتبقى قائمةُ «ما يمنع الآن» فارغةً أبدًا:
إذنٌ غائبٌ يمنع الخيطَ الذهبيّ، وزرُّه مطفأٌ بلا سببٍ مكتوب. وهو الطريقُ
المسدود نفسُه في صورةٍ أهدأ.

## ولماذا لم تُمسكه الفحوصُ القائمة

الرقعةُ في المتصفّح تُلفّق جوابَ `/journey` بنفسها وتضع الحقلَ فيه مباشرةً،
فتفحص الشاشةَ أمام عقدٍ **لا يمرّ بالنموذج**. والخادمُ يُسأل في مواضعَ أخرى
عن `blocking_reasons` لا عن هذه. فالفجوةُ كانت بين الطرفين بالضبط: كلٌّ
منهما صحيحٌ وحده.

**فيُفحص هنا الحدُّ نفسُه** — النموذجُ الذي يقف بينهما — لا طرفاه.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db

#: رمزُ المنع الذي يجب أن يعبُر — وهو الحالُ الحقيقية في الإنتاج.
CONSENT = "ai_consent_required"


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    """المزوّدُ الذاكريّ — ولا MinIO في CI، ولا يُدَّعى وجودُه.

    والتجهيزاتُ التلقائية لا تعبُر بين الوحدات، فتُعلن هنا كما تُعلن في
    أخواتها.
    """
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


# ═════════════════ أ · النموذجُ يُعلن الحقل ═════════════════


def test_the_response_model_declares_the_current_blockers():
    """**حقلٌ يُحسب ولا يُعلَن يُطرح بصمت.** فيُعلَن."""
    from athera_api.schemas.thesis import JourneyResponse

    assert "current_blocking_reasons" in JourneyResponse.model_fields
    field = JourneyResponse.model_fields["current_blocking_reasons"]
    # وقيمةٌ افتراضيةٌ مستقلّة لكلِّ جواب — لا قائمةٌ مشتركة تتراكم.
    assert field.default_factory is list
    # **ولا يزال `extra` على الافتراض** — والإعلانُ هو العلاج، لا تليينُ
    # النموذج ليقبل كلَّ مفتاح. فمفتاحٌ مجهولٌ يبقى يُطرح، وهذا صواب.
    assert JourneyResponse.model_config.get("extra", "ignore") == "ignore"


def test_the_two_blocker_lists_are_separate_fields():
    """**قائمتان لا واحدة**: ما سيلزم، وما يمنع الآن — ولا تُخلطان."""
    from athera_api.schemas.thesis import JourneyResponse

    assert "blocking_reasons" in JourneyResponse.model_fields
    assert "current_blocking_reasons" in JourneyResponse.model_fields


# ═════════════════ ب · الجولةُ كاملةً تحفظ الرمز ═════════════════


def test_the_round_trip_preserves_the_blocker_instead_of_dropping_it():
    """**وهذه هي الجولةُ التي كانت تبتلعه.**

    ‏`JourneyResponse(**view)` ثمّ `model_dump()` — كما يفعل الموجّهُ
    وFastAPI بالضبط.
    """
    from athera_api.schemas.thesis import JourneyResponse

    view = {
        "thesis_id": uuid.uuid4(),
        "state": "manuscript_created",
        "blocking_reasons": [CONSENT],
        "current_blocking_reasons": [CONSENT],
        "can_build_paper": True,
        "can_build_thread": False,
        "thread_ready": False,
        "opportunities": 1,
        "states": ["manuscript_created"],
    }
    dumped = JourneyResponse(**view).model_dump()

    assert dumped["current_blocking_reasons"] == [CONSENT], (
        "الرمزُ سقط في الجولة — وهو العطبُ بعينه")
    assert dumped["blocking_reasons"] == [CONSENT]
    # والخالي يبقى خاليًا، ولا يُملأ بقائمةِ أختِه.
    empty = JourneyResponse(thesis_id=uuid.uuid4(), state="opportunities_ready")
    assert empty.model_dump()["current_blocking_reasons"] == []


def test_an_unknown_key_is_still_dropped():
    """**والعلاجُ إعلانُ الحقل، لا فتحُ النموذج لكلِّ مفتاح.**

    فمفتاحٌ لم يُعلَن يبقى يُطرح — وذاك صوابٌ يحرس العقدَ من التسرُّب.
    """
    from athera_api.schemas.thesis import JourneyResponse

    dumped = JourneyResponse(
        thesis_id=uuid.uuid4(), state="opportunities_ready",
        something_invented=["nonsense"]).model_dump()
    assert "something_invented" not in dumped


# ═════════════════ هـ · العقدُ المنشور يُعلنه ═════════════════


def test_the_openapi_document_exposes_the_field():
    """**وما لا يظهر في العقد المنشور لا يعرفه من يبني عليه.**

    وهذا هو الفحصُ الذي كان سيُمسك العطبَ من الخارج: قرأتُ العقدَ الحيّ
    بعد النشر فوجدتُ الحقلَ غائبًا عن `JourneyResponse` — ثمانيةُ حقولٍ
    لا تسعة.
    """
    from athera_api.main import app

    schema = app.openapi()["components"]["schemas"]["JourneyResponse"]
    assert "current_blocking_reasons" in schema["properties"], (
        f"العقدُ المنشور لا يُعلن الحقل: {sorted(schema['properties'])}")
    assert schema["properties"]["current_blocking_reasons"]["type"] == "array"


# ═════════════════ ج + د · عبر حدِّ الجواب الحقيقيّ ═════════════════


async def _thesis_with_shell(tid, uid, *, consent: bool):
    """رسالةٌ لها هيكلٌ مبنيّ — ومعها إذنٌ أو بلا إذن.

    والهيكلُ يُبنى بالمسار الحقيقيّ (`journey.build_paper`)، فما يُقاس
    بعده حالٌ تقع فعلًا لا حالٌ تُزرع باليد.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis
    from athera_api.services.thesis import journey, selection
    from tests.test_at_thesis_canonical_bridge import _machine_thesis

    thesis_id, file_id, _run = await _machine_thesis(tid, uid, title_ar="عنوان")

    async with tenant_session(tid, uid) as session:
        if consent:
            await _grant_consent(session, tid, uid, file_id)

        opportunity = (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalars().first()
        if opportunity is None:
            from athera_api.services.thesis import mining
            thesis = (await session.execute(
                select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
            await mining.run(session, tenant_id=tid, actor_user_id=uid, thesis=thesis)
            opportunity = (await session.execute(
                select(PublicationOpportunity)
                .where(PublicationOpportunity.thesis_id == thesis_id))).scalars().first()
        assert opportunity is not None, "لا فرصةَ — التجهيزةُ لا تقيس ما تدّعيه"

        await selection.decide(session, tenant_id=tid, opportunity=opportunity,
                               actor_user_id=uid, decision=selection.SELECT,
                               reason="اختيارٌ في فحص العقد")
        thesis = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        await journey.build_paper(session, tenant_id=tid, actor_user_id=uid,
                                  thesis=thesis, opportunity=opportunity)
    return thesis_id


async def _grant_consent(session, tenant_id, user_id, file_id):
    """إذنٌ صريحٌ بالمسار الذي يمنحه به الباحث — لا عمودٌ يُكتب بيد."""
    from athera_api.services import consent as consent_service

    await consent_service.record_decision(
        session, tenant_id=tenant_id, file_id=file_id, actor_user_id=user_id,
        granted=True, provider="null", model=None)


async def _journey_payload(tid, uid, thesis_id):
    """**الجوابُ كما يخرج من الموجّه** — عبر النموذج، لا من `view` مباشرةً."""
    from tests.test_at_thesis_canonical_bridge import _client

    async with _client(tid, uid) as client:
        response = await client.get(f"/api/v1/theses/{thesis_id}/journey")
    assert response.status_code == 200, response.text
    return response.json()


@requires_db
@pytest.mark.asyncio
async def test_without_consent_the_journey_names_consent_and_nothing_else(two_tenants):
    """**ج · هيكلٌ قائمٌ وإذنٌ غائب: يُقال ما يمنع، ويُسمّى باسمه.**

    ولا حقوقَ ولا تأليفَ في الجواب — خرجا من هذه الرحلة، ووجودُهما هنا
    يُعيد الطريقَ المسدود.
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id = await _thesis_with_shell(tid, uid, consent=False)

    payload = await _journey_payload(tid, uid, thesis_id)

    # **والحقلُ وصل** — وهذا هو ما كان يسقط.
    assert "current_blocking_reasons" in payload, "الحقلُ سقط قبل أن يصل"
    assert payload["current_blocking_reasons"] == [CONSENT]
    assert payload["can_build_thread"] is False

    # **ولا رمزَ حقوقٍ في شيءٍ من الجواب.**
    everything = " ".join(payload["blocking_reasons"]
                          + payload["current_blocking_reasons"] + [payload["state"]])
    assert "rights" not in everything
    assert "authorship" not in everything


@requires_db
@pytest.mark.asyncio
async def test_with_consent_the_thread_is_open_and_nothing_blocks_now(two_tenants):
    """**د · وبالإذن: يُفتح الخيطُ، وتخلو قائمةُ ما يمنع الآن.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id = await _thesis_with_shell(tid, uid, consent=True)

    payload = await _journey_payload(tid, uid, thesis_id)

    assert payload["current_blocking_reasons"] == []
    assert payload["can_build_thread"] is True
    assert CONSENT not in payload["blocking_reasons"]


@requires_db
@pytest.mark.asyncio
async def test_the_payload_carries_both_lists_distinctly(two_tenants):
    """**والقائمتان تصلان معًا** — فتعرف الشاشةُ ما يمنع الآن ممّا سيلزم."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id = await _thesis_with_shell(tid, uid, consent=False)

    payload = await _journey_payload(tid, uid, thesis_id)

    assert isinstance(payload["blocking_reasons"], list)
    assert isinstance(payload["current_blocking_reasons"], list)
    # وما يمنع الآن جزءٌ ممّا سيلزم، لا قائمةٌ ثانيةٌ مستقلّة عنه.
    assert set(payload["current_blocking_reasons"]) <= set(payload["blocking_reasons"])
