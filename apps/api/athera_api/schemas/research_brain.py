"""عقدُ «الذكاء البحثيّ» المنشور | The published Research Intelligence contract (Wave 2-A §55).

**ولمَ ملفٌّ مستقلّ:** `schemas/workspace.py` فيه `NextAction` من قبل —
`{key, label}` — وهي الخطوةُ الواحدة في `ProjectOverview`. واسمان لشيئين
مختلفين في ملفٍّ واحد يجعل القارئ يظنّهما واحدًا، والكاتبَ يستورد الخطأ.
فهذه `JourneyActionView` باسمها، وتلك تبقى كما هي.

## والحقلُ المُعلَن هو الحقلُ الواصل

الدرسُ من الإنتاج، وثمنُه معروف: `journey.view` كانت تحسب
`current_blocking_reasons` ويطرحها النموذجُ صامتًا لأنّه لم يُعلنها —
و`extra="ignore"` هي الافتراض في Pydantic. فبقيت الشاشةُ تقرأ `undefined`
وزرٌّ مطفأٌ بلا سببٍ مكتوب.

**فكلُّ حقلٍ تحتاجه الواجهةُ مُعلَنٌ هنا**، وفحصٌ يقرأ العقدَ المنشور نفسَه
(`app.openapi()`) لا الرقعةَ في المتصفّح — لأنّ الرقعةَ تُلفّق الجوابَ
فتتجاوز النموذجَ الذي كان هو موضعَ العطب.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class JourneyActionView(BaseModel):
    """فعلٌ واحد بحاله وسببه — **ولا اسمَ خدمةٍ داخليّ فيه**."""

    action_key: str
    category: str
    status: str
    title: str
    reason: str
    route: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class CapabilityView(BaseModel):
    """بوّابةٌ حتمية: ما يمكن الآن وما لا يمكن — **ولا رأيَ فيها** (§24)."""

    key: str
    allowed: bool
    blocking_reasons: list[str] = Field(default_factory=list)


class StageView(BaseModel):
    """مرحلةٌ واحدة كما يقرؤها الباحث — **بحالها وسببها، لا برمزها**."""

    key: str
    #: خمسُ حالاتٍ صادقة — و«الحاليّة» ليست منها بل `is_current` أدناه.
    status: str
    #: **هنا يقف الباحث** — علمٌ مستقلّ لا يمحو الحال.
    is_current: bool = False
    title: str
    #: لماذا هذه الحال — ويصل دائمًا، فلا حالَ بلا تفسير (§43).
    reason: str
    #: ملخّصٌ قصيرٌ صادق، أو فارغٌ إن لم يكن ثمّة ما يُلخَّص (§47).
    summary: str = ""
    route: str | None = None
    #: رموزُ المنع — تُترجَم في الواجهة، ومع `blocked` وحدها (§44).
    blocking_reasons: list[str] = Field(default_factory=list)


class KnownFactView(BaseModel):
    """واقعةٌ يعرفها PUBRIVA عن هذا البحث — **أو لا يعرفها** (§48، §51).

    و`value` الفارغة تعني «غير مسجَّل»، ولا تُملأ باستنباط: وجودُ بياناتٍ
    لا يجعل المنهجَ كمّيًّا.
    """

    key: str
    label: str
    value: str = ""
    known: bool = False


class MissingItemView(BaseModel):
    """ناقصٌ واحد — **مصنَّفًا لا مكدَّسًا في قائمةٍ حمراء** (§49)."""

    key: str
    label: str
    #: `blocking` أو `recommended` أو `optional`.
    severity: str


class ProjectJourneyView(BaseModel):
    """«الذكاء البحثيّ» لمشروعٍ واحد.

    **ولا نسبةَ إنجاز** (§45): الحالاتُ المسمّاة أعلاه هي الحقيقة، و«٧٣٪
    مكتمل» تُخفي الفرقَ بين بحثٍ ينقصه سطرٌ وبحثٍ ينقصه منهج.
    """

    project_id: uuid.UUID
    title: str

    #: بصمةُ الحال — تُعرض في مسار التشخيص، ولا تُعرض للباحث العاديّ (§84).
    #:
    #: **وهي ما يجعل التقادمَ قابلًا للكشف** دون حفظِ توصية: لقطتان
    #: ببصمتين مختلفتين حالان مختلفتان، والمعروضُ دائمًا محسوبٌ من الراهنة.
    context_fingerprint: str
    fingerprint_schema: str
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime

    # ═══ أين أنت؟ وماذا أُنجز؟ ═══
    #
    # **والمراحلُ تسع** (§19): أربعَ عشرةَ مرحلةً دقيقةً في شريطٍ واحد
    # تُخفي الرحلةَ بدل أن تُظهرها.
    stages: list[StageView] = Field(default_factory=list)
    #: مفتاحُ المرحلة الحاليّة — واحدةٌ لا عدّة (§46).
    current_stage: str | None = None

    # ═══ ما نعرفه، وما الناقص ═══
    known: list[KnownFactView] = Field(default_factory=list)
    missing: list[MissingItemView] = Field(default_factory=list)

    #: الخطوةُ التالية المقترحة — واحدةٌ لا عشر.
    recommended: JourneyActionView | None = None
    actions: list[JourneyActionView] = Field(default_factory=list)
    capabilities: list[CapabilityView] = Field(default_factory=list)

    #: ما نعرفه وما ينقص — بالعدّ لا بالمتن.
    known_count: int = 0
    missing_count: int = 0
    needs_review_count: int = 0
    conflict_count: int = 0

    #: ما لا تعرفه هذه القراءة — يُعلَن ولا يُسكت عنه.
    limitations: str
    note: str


__all__ = ["CapabilityView", "JourneyActionView", "KnownFactView",
           "MissingItemView", "ProjectJourneyView", "StageView"]
