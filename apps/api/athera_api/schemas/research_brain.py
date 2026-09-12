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


class ProjectJourneyView(BaseModel):
    """«الذكاء البحثيّ» لمشروعٍ واحد.

    **ولا نسبةَ إنجاز** (§45): الحالاتُ المسمّاة أعلاه هي الحقيقة، و«٧٣٪
    مكتمل» تُخفي الفرقَ بين بحثٍ ينقصه سطرٌ وبحثٍ ينقصه منهج.
    """

    project_id: uuid.UUID
    title: str

    #: بصمةُ الحال — تُعرض في مسار التشخيص، ولا تُعرض للباحث العاديّ (§84).
    context_fingerprint: str
    fingerprint_schema: str
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime

    #: الخطوةُ التالية المقترحة — واحدةٌ لا عشر.
    recommended: JourneyActionView | None = None
    actions: list[JourneyActionView] = Field(default_factory=list)
    capabilities: list[CapabilityView] = Field(default_factory=list)

    #: ما نعرفه وما ينقص — بالعدّ لا بالمتن.
    known_count: int = 0
    missing_count: int = 0
    needs_review_count: int = 0
    conflict_count: int = 0

    #: توصياتٌ قيلت تحت بصمةٍ سابقة فلم تعد جارية — **يُقال عددُها** (§41).
    superseded_now: int = 0

    #: ما لا تعرفه هذه القراءة — يُعلَن ولا يُسكت عنه.
    limitations: str
    note: str


__all__ = ["CapabilityView", "JourneyActionView", "ProjectJourneyView"]
