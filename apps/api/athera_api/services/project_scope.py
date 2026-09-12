"""حدُّ البحث الواحد | What counts as a live project — one definition, one place.

**وحدةٌ صغيرةٌ عمدًا، ولها سببٌ معماريّ.**

«البحثُ القائم» تعريفٌ يحتاجه كلُّ من يقرأ بحثًا: الموجّهات، والتخطيط،
والتوليف، والعقلُ البحثيّ. وكان يسكن في `services/workspace.py` — وتلك
وحدةٌ تعرف مركزَ الرسائل (تستورد `models.thesis` لتعدّ فرصَ النشر وحالَ
معالجة الملفات).

فكان كلُّ من أراد أن يسأل «أهذا بحثٌ قائم؟» **يرث معه مركزَ الرسائل
كلَّه**. وهو ما أمسكه عقدُ الاستيراد في `pyproject.toml` أولَ ما شُغِّل:

    research_assessment.snapshot → services.workspace → models.thesis

والعقلُ لا يجوز أن يقوم على وحدةٍ مؤجَّلة (§79). فأُخرج التعريفُ إلى هنا،
ولا يستورد هذا الملفُّ إلا `models.portfolio`.

**ولم يتغيّر سلوكٌ ولا اسم:** `workspace.live_project` يبقى موجودًا ويُعيد
تصدير ما هنا، فكلُّ نداءٍ قائم يعمل كما كان. والتعريفُ واحدٌ في موضعٍ
واحد — لا نسخةٌ ثانية تفترق عن أختها بأول تعديل.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.portfolio import ResearchProject


async def live_project(session: AsyncSession, *, tenant_id: uuid.UUID,
                       project_id: uuid.UUID) -> ResearchProject | None:
    """بحثٌ قائم — **وما في السلّة ليس قائمًا**.

    و`deleted_at` شرطٌ لا تفصيل: قراءةُ بحثٍ محذوف تُعيده إلى الشاشة من
    بابٍ خلفيّ، فيقرأ الباحثُ عن بحثٍ ظنّه أزاله.
    """
    return (await session.execute(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.tenant_id == tenant_id,
            ResearchProject.deleted_at.is_(None))
    )).scalar_one_or_none()


__all__ = ["live_project"]
