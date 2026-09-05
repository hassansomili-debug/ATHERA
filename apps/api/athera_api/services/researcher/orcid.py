"""معرّفُ ORCID — صيغةٌ تُتحقَّق، وتوثيقٌ لا يُدَّعى | ORCID format, not verification.

**والصيغةُ الصحيحة ليست توثيقًا** (§6). هذا هو الفرقُ كلُّه، ويُخلط كثيرًا:
رقمٌ يمرّ خانةَ التدقيق يثبت أنّه **رقمُ ORCID صالحُ البنية**، ولا يثبت
أنّ صاحبَ الحساب يملكه. فيبقى `user_declared` حتى يقول مصدرٌ خارجيّ
مُتحقَّق غيرَ ذلك — وذلك المصدرُ لم يُبنَ في هذه الموجة (OAuth مؤجَّل، §13).

ولهذا لا تُصدِّر هذه الوحدةُ دالّةً واحدة تُسمّى «تحقَّق»: الاسمُ نفسه
كان سيكذب. بل `normalise` و`has_valid_format` — ولا ثالثة ترفع حالًا.
"""

from __future__ import annotations

import re
from typing import Final

#: الصيغةُ المعروضة: أربعُ مجموعاتٍ رباعية، وآخرُها قد ينتهي بـX.
ORCID_DISPLAY_PATTERN: Final = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

#: ما يُقبل مُدخَلًا قبل التطبيع: رقمٌ خامّ، أو مفصولٌ بشُرَط، أو رابطٌ كامل.
_STRIPPABLE_PREFIXES: Final = (
    "https://orcid.org/",
    "http://orcid.org/",
    "https://www.orcid.org/",
    "http://www.orcid.org/",
    "orcid.org/",
)

#: الحالُ التي يبقى عليها رقمٌ صحيحُ الصيغة كتبه الباحثُ بيده.
DECLARED_STATUS: Final = "user_declared"


def normalise(value: str | None) -> str | None:
    """يُرجع الصيغةَ المعروضة `0000-0000-0000-0000`، أو `None` إن تعذّر.

    ولا يحكم على الصحّة — التطبيعُ شكلٌ لا حكم. رقمٌ مطبَّعٌ قد يفشل في
    خانة التدقيق، وذلك سؤالُ `has_valid_format` وحدها.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    lowered = text.lower()
    for prefix in _STRIPPABLE_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break

    digits = text.replace("-", "").replace(" ", "").upper()
    if len(digits) != 16:
        return None
    if not digits[:15].isdigit():
        return None
    if digits[15] not in "0123456789X":
        return None

    return "-".join(digits[i:i + 4] for i in range(0, 16, 4))


def checksum_digit(first_fifteen: str) -> str:
    """خانةُ التدقيق mod-11-2 كما تعرّفها ISO 7064 وتستعملها ORCID.

    ويُعاد `X` حين تكون القيمةُ عشرة — وهي الحالةُ التي يسقط فيها كلُّ
    تحقّقٍ يكتفي بـ`isdigit()`.
    """
    total = 0
    for character in first_fifteen:
        total = (total + int(character)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    return "X" if result == 10 else str(result)


def has_valid_format(value: str | None) -> bool:
    """أصحيحةٌ بنيةُ هذا المعرّف؟ — **وهذا كلُّ ما يُقال.**

    لا يعني `True` أنّ الباحثَ يملك المعرّف، ولا أنّ سجلًّا خارجيًّا رآه.
    ومَن قرأ هذه الدالّة توثيقًا بنى على ادّعاءٍ لا سند له (§9).
    """
    normalised = normalise(value)
    if normalised is None:
        return False
    if not ORCID_DISPLAY_PATTERN.match(normalised):
        return False
    digits = normalised.replace("-", "")
    return digits[15] == checksum_digit(digits[:15])


def status_for_declared(value: str | None) -> str:
    """حالُ التوثيق لمعرّفٍ كتبه الباحثُ بيده.

    **ولا ترفعُها الصيغةُ الصحيحة إلى `externally_verified` أبدًا.** غيابُ
    المعرّف `unverified`، ووجودُه صحيحَ الصيغة `user_declared` — وبينهما
    فرقُ «لم يقل» و«قال»، لا فرقُ «كذب» و«صدق».
    """
    return DECLARED_STATUS if normalise(value) is not None else "unverified"
