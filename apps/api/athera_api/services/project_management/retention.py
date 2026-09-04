"""الإتلاف الدائم: معاينةٌ ثمّ وقف | Permanent deletion: preview, then blocked.

**طلب المالك صريح: حذفٌ دائم من سلّة المهملات.** وهذا الملف ينفّذ نصفه
الآمن ويقف عند نصفه الخطر، ويقول لماذا وقف — لا يصمت ولا يخمّن.

## ما يقع فعلًا

  ١ معاينةُ تبعياتٍ بعشرة أعداد باسمها: مراجع، ادعاءات، معرفة معتمَدة،
    ملفات، فريق، مهامّ، قرارات، مخطوطة، عناصر تركيب، تبعيات تدقيق.
  ٢ حالُ **وقفٍ معلَنة** لا زرٌّ ينفّذ بصمت.

## ولماذا الوقف

سياسةُ الاحتفاظ في هذا المستودع **ليست معرَّفةً تعريفًا صالحًا للتنفيذ**.
ومصفوفة تصنيف البيانات (`docs/data-classification.md`) تقول:

  C2 بحثيّ حسّاس   «مدة المشروع + ٥ سنوات»
  C3 بيانات بحثية  «حسب Data Management Plan»
  C4 بيانات مشاركين «حسب الموافقة الأخلاقية فقط»

فالأولى تعني أنّ إتلافَ بحثٍ اليوم قد يخالف احتفاظًا واجبًا لخمس سنوات؛
والثانيتان تُحيلان إلى خطّة إدارة بياناتٍ وموافقةٍ أخلاقية **لا يمثّلهما
جدولٌ في هذه القاعدة أصلًا**. فالمنصّة لا تملك ما تقرأ منه أنّ الإتلاف
مسموح.

**والقرار المطلوب هنا هو الامتناع.** أن أُنفّذ حذفًا لا أعرف مشروعيّته
لأن الطلب صدر يعني أن أُتلف نسبًا علميًّا لا يُعاد كتابته — وسنواتُ عملٍ
لا تُستعاد بضغطةٍ ثانية. وأن أدّعي أنّه نُفّذ وهو لم يُنفّذ أسوأ.

  فالوقف يُعلَن، ومعه شرطُ رفعه بنصّه.

## ما يرفع الوقف

قرارُ معماريةٍ مكتوب (ADR) يحدّد، لكل مستوى تصنيف: مدّة الاحتفاظ، ومن
يملك الإذن، وما الذي يبقى في شاهد التدقيق بعد الإتلاف. وقد كُتب الطلب في
`docs/integration/track-b-requests.md`.

## وشاهدُ التدقيق حين يُسمح يومًا

سجلّ التدقيق في هذا المستودع يُلحَق ولا يُحذف (ترحيل 0003: `UPDATE` و
`DELETE` منزوعتان عن `athera_app`، وزنادٌ يرفضهما). فأثرُ البحث فيه باقٍ
بعد إتلافه لا محالة. والقاعدة حينها: **بياناتٌ وصفية فقط** — معرّفٌ ووقتٌ
وفاعل — ولا سطرَ محتوًى بحثيّ في الشاهد. وهذا مكتوبٌ هنا ليُقرأ قبل أن
يُنفَّذ، لا بعده.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# سببُ الوقف — رمزٌ واحد يُقرأ في الشاشة وفي السجلّ وفي الاختبار.
BLOCKED_REASON: Final = "retention_policy_undefined"

BLOCKED_AR: Final = (
    "الإتلاف الدائم موقوف: لا سياسةَ احتفاظٍ قابلةً للتنفيذ في هذا النظام. "
    "مصفوفة تصنيف البيانات تُلزم بالاحتفاظ بالمواد البحثية الحساسة مدّة "
    "المشروع وخمس سنوات بعده، وتُحيل بياناتِ المشاركين إلى الموافقة الأخلاقية "
    "وحدها — ولا يقرأ النظام أيًّا منهما اليوم. فلا يُتلَف ما لا تُعرف "
    "مشروعيّة إتلافه. والبحث باقٍ في السلّة، ويمكن استعادته كما هو."
)

BLOCKED_EN: Final = (
    "Permanent deletion is blocked: this system has no enforceable retention "
    "policy. The data-classification matrix requires sensitive research material "
    "to be kept for the project's duration plus five years, and defers participant "
    "data to the ethics consent alone — neither of which this system can read "
    "today. Nothing is destroyed whose destruction cannot be shown to be lawful. "
    "The project stays in the trash and can be restored unchanged."
)

# ما يلزم لرفع الوقف — يُعرض للباحث ولمن يقرأ السجلّ، فلا يبقى الوقف لغزًا.
UNBLOCK_REQUIREMENT_AR: Final = (
    "يُرفع الوقف بقرار معمارية مكتوب يحدّد لكل مستوى تصنيف: مدّة الاحتفاظ، "
    "ومَن يملك إذن الإتلاف، وما الذي يبقى في شاهد التدقيق بعده."
)

UNBLOCK_REQUIREMENT_EN: Final = (
    "The block lifts with a written architecture decision that fixes, per "
    "classification level: the retention period, who may authorise destruction, "
    "and what remains in the audit tombstone afterwards."
)

# مصادر السياسة التي قُرئت قبل هذا القرار — تُعرض لأن «موقوف» بلا مرجعٍ
# يُقرأ عطبًا في المنتج لا حكمًا مدروسًا.
POLICY_SOURCES: Final[tuple[str, ...]] = (
    "docs/data-classification.md",
    "infra/db/migrations/versions/0003_rls_and_immutability.py",
)


@dataclass(frozen=True, slots=True)
class DeletionVerdict:
    """حكمُ المعاينة — **ولا حالة `allowed` في هذا الإصدار**.

    والحقل موجودٌ لا لأنه يُستعمل اليوم، بل ليكون الموضع الوحيد الذي يتغيّر
    يوم تُكتب السياسة: من رفع الوقف يغيّر سطرًا هنا ويقابله اختبار، ولا
    يبحث عن `if` مبعثرةٍ في موجّه.
    """

    is_blocked: bool
    reason: str
    message_ar: str
    message_en: str
    requirement_ar: str
    requirement_en: str
    policy_sources: tuple[str, ...]


def verdict() -> DeletionVerdict:
    """هل يُسمح بالإتلاف الدائم الآن؟ — **لا، ويُقال السبب كاملًا**."""
    return DeletionVerdict(
        is_blocked=True,
        reason=BLOCKED_REASON,
        message_ar=BLOCKED_AR,
        message_en=BLOCKED_EN,
        requirement_ar=UNBLOCK_REQUIREMENT_AR,
        requirement_en=UNBLOCK_REQUIREMENT_EN,
        policy_sources=POLICY_SOURCES,
    )


__all__ = [
    "BLOCKED_AR",
    "BLOCKED_EN",
    "BLOCKED_REASON",
    "POLICY_SOURCES",
    "UNBLOCK_REQUIREMENT_AR",
    "UNBLOCK_REQUIREMENT_EN",
    "DeletionVerdict",
    "verdict",
]
