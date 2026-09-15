"""تحديدُ موضعِ كياناتِ التحليل | the canonical analysis data locator (RC-T1C).

**معرّفٌ واحدٌ لا يقول بحثَه.** نسخةُ مجموعةٍ تُعرَّف بمعرّفها، وبحثُها
يُعلم بقراءة مجموعتها؛ ومخرَجٌ يُعلم ببلوغِ تشغيلته ثمّ خطّتها. وطبقةُ
التحليل كلُّها مبنيّةٌ على هذه المعرّفات غيرِ المباشرة.

فهذا الملفُّ يجيب سؤالًا واحدًا: **أيُّ بحثٍ يملك هذا الكيان؟** — ولا
يفوّض، ولا يقرأ الكيانَ نفسَه، ولا يكتب شيئًا.

## ولمَ موضعٌ واحدٌ لا ستّة

كان كلُّ حارسٍ في `analysis.py` يمشي السلسلةَ بنفسه — ستُّ نسخٍ من
«اتبع الأبَ إلى جذره». وستُّ نسخٍ تفترق بأوّل تعديل: يُضاف جدولٌ فيُنسى
في أربعٍ منها، أو يُصحَّح في واحدةٍ ويبقى العطبُ في الخمس. **والسلسلةُ
تُكتب مرّةً وتُقرأ مرارًا.**

## وما يجعل هذا ممكنًا عبرَ المؤسسات

سياساتُ «تحديد الموضع» في الترحيل 0036: يرى الفاعلُ صفَّ تحليلٍ **جذرُه
بحثٌ أثبت فيه عضويّةً نشِطةً تحمل `view_project` و`manage_data` معًا**.
فالقراءةُ هنا تُجيب عن كياناتِ بحوثه هو ولا تُجيب عن غيرها — **ومن سأل
عن معرّفٍ لا يملكه لم يُعلم أوجد أم لا**: تُعاد `None`، ويردّ المسارُ
جوابَ المعدوم.

## وهذا تحديدُ موضعٍ لا تفويض

فالجوابُ معرّفُ بحثٍ يُدخل به `project_session`، **ثمّ** يقرّر
`ensure_project_access` داخلَ مستأجر البحث مَن يدخل وبأيّ صلاحية. ولا
يُكتب صفٌّ ولا يُقرأ كيانٌ اعتمادًا على هذه القراءة وحدها: بعد العبور
يُعاد قراءةُ الهدف في مستأجره — انظر `_scope` في الموجّه.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analysis import (
    AnalysisOutputRow,
    AnalysisPlanRow,
    AnalysisRun,
    Dataset,
    DatasetVersionRow,
)

# أنواعُ المفاتيح غيرِ المباشرة التي تعرفها هذه الطبقة — **وقائمةٌ مغلقة**.
KINDS = ("dataset", "version", "plan", "run", "output")


async def locate(
    session: AsyncSession,
    *,
    dataset: uuid.UUID | None = None,
    version: uuid.UUID | None = None,
    plan: uuid.UUID | None = None,
    run: uuid.UUID | None = None,
    output: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """معرّفُ البحث المالكِ لهذا الكيان — أو `None` إن لم يُرَ.

    ومفتاحٌ واحدٌ في النداء: مفتاحان يعنيان سؤالين، ويُسألان مرّتين
    ويُقارَن جوابُهما (انظر `same_project`). ودمجُهما في نداءٍ واحدٍ
    يُخفي أيَّهما لم يُطابق.
    """
    given = [k for k, v in (("dataset", dataset), ("version", version),
                            ("plan", plan), ("run", run), ("output", output))
             if v is not None]
    if len(given) != 1:
        raise ValueError(f"locate() takes exactly one key, got {given}")

    if dataset is not None:
        statement = select(Dataset.project_id).where(Dataset.id == dataset)
    elif version is not None:
        statement = (
            select(Dataset.project_id)
            .join(DatasetVersionRow, DatasetVersionRow.dataset_id == Dataset.id)
            .where(DatasetVersionRow.id == version))
    elif plan is not None:
        statement = select(AnalysisPlanRow.project_id).where(
            AnalysisPlanRow.id == plan)
    elif run is not None:
        statement = (
            select(AnalysisPlanRow.project_id)
            .join(AnalysisRun, AnalysisRun.plan_id == AnalysisPlanRow.id)
            .where(AnalysisRun.id == run))
    else:
        statement = (
            select(AnalysisPlanRow.project_id)
            .join(AnalysisRun, AnalysisRun.plan_id == AnalysisPlanRow.id)
            .join(AnalysisOutputRow, AnalysisOutputRow.run_id == AnalysisRun.id)
            .where(AnalysisOutputRow.id == output))

    return (await session.execute(statement)).scalar_one_or_none()


async def same_project(
    session: AsyncSession, *, first: dict[str, uuid.UUID],
    second: dict[str, uuid.UUID],
) -> uuid.UUID | None:
    """بحثٌ واحدٌ يملك الكيانَين — أو `None`.

    **وهذا حدٌّ كان مفقودًا قبل هذه الدفعة.** كان `POST /runs` يفوّض
    الخطّةَ والنسخةَ **كلًّا على حدة**، فمن يُدير بحثين يشغّل خطّةَ هذا
    على بياناتِ ذاك — ويُسجَّل المخرَجُ تحت الخطّة كأنّه منها. وكان
    `POST /exports` يقبل `run_id` من العميل **بلا تفويضٍ أصلًا**.

    وبعد جسر المؤسسات يصير العطبُ أثقل: خلطُ بياناتِ مؤسسةٍ في خطّةِ
    مؤسسةٍ أخرى. **فيُشترط أن يكون الجذرُ واحدًا.**
    """
    left = await locate(session, **first)  # type: ignore[arg-type]
    if left is None:
        return None
    right = await locate(session, **second)  # type: ignore[arg-type]
    if right is None or right != left:
        return None
    return left
