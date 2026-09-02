"""عقد مخرَج الكاتب العلمي | Structured drafting contract (S5E-B §15).

**نصٌّ حرّ وحده لا يُتحقَّق منه.** جملةٌ منهجية معقولة لا تُميَّز عن جملةٍ
مخترَعة بالقراءة؛ ما يميّزهما أن تقول الأولى من أي دليلٍ جاءت. فالمخرَج
مهيكل: نصُّ القسم، ثم ادعاءاته كلٌّ بمعرّفات أدلته، ثم ما لم يجد له دليلًا.

**والاعتراف بالنقص جزءٌ من العقد لا استثناءٌ منه.** حقل `missing_evidence`
يجعل «لا أعرف» مخرَجًا صالحًا — فلا يُدفع النموذج إلى ملء الفراغ ليُرضي
شكل الجواب.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# أصل المحتوى (§5) — والتمييز يُعلَن في البيانات لا يُترك للقارئ.
#
#   fact      — تسنده ذاكرة موثقة أو مخرَج تحليل
#   inference — استنتاجٌ من أدلة، يُعلَن استنتاجًا ويُبيَّن أساسه
#   proposal  — اقتراح صياغة، لا يُعرض حقيقةَ مصدر
Origin = Literal["fact", "inference", "proposal"]

# أنواع الادعاء — **مفردات `claims.claim_type` القائمة**، لا مفردات ثانية.
ClaimType = Literal["empirical", "theoretical", "contextual", "interpretive"]

SupportLevel = Literal["direct", "partial", "contextual", "contradictory"]


class DraftedClaim(BaseModel):
    """ادعاءٌ واحد في القسم — بأصله وأدلته."""

    text_ar: str = Field(min_length=5, max_length=2000)
    claim_type: ClaimType
    origin: Origin
    # **معرّفات من السياق المُرسَل وحده.** أي معرّف خارجه يُرفض الرابط ولا
    # يُصحَّح: نموذجٌ يخترع معرّفًا يخترع سندًا.
    memory_ids: list[str] = Field(default_factory=list, max_length=20)
    analysis_output_ids: list[str] = Field(default_factory=list, max_length=20)
    support_level: SupportLevel = "direct"


class MissingEvidence(BaseModel):
    """ما لم يجد له النموذج دليلًا — يبقى ظاهرًا ولا يُملأ."""

    topic_ar: str = Field(min_length=3, max_length=300)
    why_ar: str = Field(default="", max_length=500)


class SectionDraft(BaseModel):
    """مخرَج صياغة قسم واحد."""

    # **الفراغ جوابٌ صالح.** كان الحدّ الأدنى حرفًا واحدًا، فلم يكن للنموذج
    # سبيلٌ ليقول «لا يمكن كتابة هذا القسم من الأدلة المتاحة» — فيُدفع إلى
    # نثرٍ يملأ الشكل، أو يسقط الطلب بخرق العقد. وقد وقع الثاني في أول نداء
    # إنتاجي للمناقشة: دليلٌ واحد، ومنعٌ محكم، فأعاد نواقصه بلا نصّ.
    #
    # والقسم الفارغ بقائمة نواقصه أصدق من فقرة معقولة.
    section_text_ar: str = Field(default="", max_length=20000)
    section_text_en: str | None = Field(default=None, max_length=20000)
    claims: list[DraftedClaim] = Field(default_factory=list, max_length=40)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list, max_length=20)
    warnings_ar: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _must_say_something(self) -> "SectionDraft":
        """**إمّا كتبتَ، وإمّا قلتَ لماذا لم تكتب.**

        جعلُ النصّ اختياريًّا فتح للنموذج بابَ الصدق — وأغلق بابًا آخر: صار
        كلُّ حقلٍ اختياريًّا، فمرّ **أي** كائن بوصفه مسودةً صالحة. ومظروف نقلٍ
        مثل `{"parameters": {…}}` كان يُكشف بخرق العقد، فصار يُقرأ قسمًا
        فارغًا بلا نواقص — أي «لا أعرف» لم يقلها أحد.

        فالفراغ جوابٌ صالح **بشرط أن يُعلَّل**: نصٌّ، أو قائمة نواقص. وما ليس
        فيه واحدٌ منهما ليس مسودةً أصلًا.
        """
        if not self.section_text_ar.strip() and not self.missing_evidence:
            raise ValueError(
                "a section draft must carry either text or a missing-evidence list; "
                "an empty answer with no stated gap is not an answer")
        return self


__all__ = ["ClaimType", "DraftedClaim", "MissingEvidence", "Origin", "SectionDraft",
           "SupportLevel"]
