"""§7.4 — قاعدة ترقية الذاكرة مفروضة في قاعدة البيانات لا في الكود.

ليست ضمن الاختبارات الثلاثة عشر الأصلية، لكنها الشرط الذي يحمي المنتج كله
من أن تتحول مخرجات النموذج إلى «حقيقة موثقة» بالخطأ.
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from athera_api.db import tenant_session
from athera_api.models.audit import ProvenanceEvent

pytestmark = pytest.mark.asyncio


async def test_model_output_cannot_be_marked_verified(two_tenants):
    a = two_tenants["a"]
    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(
                ProvenanceEvent(
                    tenant_id=a["tenant_id"], object_type="researcher_fact",
                    object_id=uuid.uuid4(), source_type="model_output",
                    created_by=a["user_id"], verification_status="verified",
                    verified_by=a["user_id"], verified_at=__import__("datetime").datetime.now(
                        __import__("datetime").UTC
                    ),
                )
            )
            await session.flush()


async def test_verified_requires_verifier_and_timestamp(two_tenants):
    a = two_tenants["a"]
    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(
                ProvenanceEvent(
                    tenant_id=a["tenant_id"], object_type="researcher_fact",
                    object_id=uuid.uuid4(), source_type="upload",
                    created_by=a["user_id"], verification_status="verified",
                )
            )
            await session.flush()
