"""بصمةُ السياق البحثيّ | The deterministic research-context fingerprint (Wave 2-A, §39–§40).

**ما تُجيب عنه هذه الوحدة سؤالٌ واحد:** هل تغيّر البحثُ تغيّرًا ذا معنى منذ
أن قلنا فيه ما قلنا؟

وبدونها لا يمكن لتوصيةٍ أن تَبْلى. فتبقى «شغّل إحصاءً وصفيًّا» معروضةً بعد
أن حُذفت مجموعةُ البيانات، و«المنهج كمّي» بعد أن صار كيفيًّا — والباحثُ
يقرأ قولًا عن بحثٍ لم يعد بحثَه. وهذا ما سجّله
`docs/research-brain-foundation.md` في بنده الأول: التقييم يُحسب عند كل
نداء، **ولا يمكن مقارنةُ تقييمِ اليوم بتقييم الأمس**.

## والاصطلاح مستعار لا مخترَع

الصيغةُ نفسها التي يستعملها المستودع في ثلاثة مواضع قائمة —
`publishing/drafting/context.py`، و`planning/context.py`،
و`analysis/reproducibility.py`:

    json.dumps(…, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ثمّ sha256

ومنظومةٌ فيها أربعُ طرقٍ لبناء بصمة تبني بإحداها وتقارن بالأخرى.

## ما يدخل البصمة وما لا يدخل

يدخلها **ما يُبنى عليه حكم**: الكياناتُ بمعرّفاتها وأنواعها وتسمياتها،
والروابطُ بأطرافها، وحالاتُ الحقول وسندُها، وحالاتُ المرشّحين، وأقسامُ
المخطوطة بمحتواها، والتعارضاتُ المسجَّلة.

**ولا يدخلها الوقت.** ولا معرّفُ طلب، ولا ترتيبُ قراءةٍ عابر. وبصمةٌ
تتغيّر بمرور الثانية تُبطل كلّ توصيةٍ بلا سبب، فلا تُثبت شيئًا وتُتعب
الباحثَ بتقادمٍ كاذب — وهو العطبُ الذي يحرسه التعليقُ في
`planning/context.py` حرفيًّا.

**ولا تدخلها `read_notes`.** فهي وصفُ ما تعذّرت قراءتُه — بيانٌ عن اللقطة
لا محتوًى فيها. وإدخالُها يجعل تحسينَ رسالةِ خطأٍ تغييرًا في البحث.

## والترتيب قانونيّ لا عابر

كلُّ مجموعةٍ تُرتَّب قبل أن تُهضَم. فلقطتان لبحثٍ واحد قُرئت إحداهما
بترتيبٍ مخالف تُعطيان البصمةَ نفسها — وهذا شرطُ أن تعني البصمةُ «تغيّر
البحث» لا «تغيّر ترتيبُ القراءة».
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .rules import Assessment

#: نسخةُ الصيغة. تتغيّر حين يتغيّر **ما يدخل** البصمة، فتُقادِم كلَّ ما
#: بُني على الصيغة السابقة عمدًا — لأنّ تطابق بصمتين حُسبتا بصيغتين
#: مختلفتين تطابقٌ بلا معنى.
SCHEMA: str = "pubriva.brain.context.v1"


def _entities(assessment: Assessment) -> list[str]:
    """كلُّ كيانٍ سطرًا واحدًا: نوعُه، ومعرّفُه، وتسميتاه.

    والتسميةُ تدخل لأنّ إعادةَ صياغة سؤالِ بحثٍ تغييرٌ في البحث: الكيانُ
    هو هو، والمكتوبُ فيه صار غيره.
    """
    return sorted(
        json.dumps([e.kind.value, e.id, e.label_ar, e.label_en],
                   ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for e in assessment.graph.entities
    )


def _relationships(assessment: Assessment) -> list[str]:
    return sorted(
        f"{r.kind.value}|{r.source_id}|{r.target_id}"
        for r in assessment.graph.relationships
    )


def _fields(assessment: Assessment) -> list[str]:
    """حقولُ «ما نعرفه» بحالتها **وسندها**.

    والسندُ يدخل لأنّ حقلًا صار `known` بذاكرةٍ أخرى ليس الحقلَ نفسه: لو
    دخلت الحالُ وحدَها لَما تغيّرت البصمةُ حين يُستبدل سندُ معرفةٍ بسندٍ
    آخر — وذاك تغيّرٌ في الإسناد يُبنى عليه حكمُ `RB-PROVENANCE-01`.
    """
    return sorted(
        json.dumps([f.key, f.state,
                    sorted(f.backing_memory_ids), sorted(f.backing_candidate_ids)],
                   ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for f in assessment.fields
    )


def _candidates(assessment: Assessment) -> list[str]:
    return sorted(f"{c.id}|{c.status}" for c in assessment.candidates)


def _sections(assessment: Assessment) -> dict[str, str]:
    """أقسامُ المخطوطة **بمعمّى محتواها** لا بمتنها.

    فالبصمةُ تُحفظ وتُنقل وتُعرض في مسارات التشخيص، ومتنُ مخطوطةٍ داخلَ
    مُدخلٍ يُهضَم ليس بحاجةٍ إلى أن يُحمَل. والتغيّرُ في المتن يُلتقط
    بمعمّاه كما يُلتقط بمتنه — وهو ما يفعله `prior_text` في
    `drafting/context.py` بالضبط.
    """
    return {
        key: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for key, text in assessment.sections.items()
        if text
    }


def payload(assessment: Assessment, *, project_id: str,
            contradiction_keys: Iterable[str] = ()) -> dict:
    """المُدخلُ القانونيّ للبصمة — **مكشوفًا ليُقرأ عند اختلاف بصمتين**.

    بصمتان مختلفتان بلا سبيلٍ إلى معرفة ما اختلف تجعلان التشخيصَ تخمينًا.
    فيُفصل بناءُ المُدخل عن هضمه، ويُعرض المُدخلُ في مسار التشخيص.
    """
    return {
        "schema": SCHEMA,
        "project": project_id,
        "entities": _entities(assessment),
        "relationships": _relationships(assessment),
        "fields": _fields(assessment),
        "candidates": _candidates(assessment),
        "sections": _sections(assessment),
        "sample_numbers_in_text": sorted(assessment.sample_numbers_in_text),
        # التعارضُ المسجَّل جزءٌ من حال البحث: ظهورُه أو زوالُه تغيّرٌ
        # يُبنى عليه فعلٌ مقترح (§58).
        "contradictions": sorted(contradiction_keys),
    }


def of(assessment: Assessment, *, project_id: str,
       contradiction_keys: Iterable[str] = ()) -> str:
    """بصمةُ لقطةٍ واحدة — ستّ وستون محرفًا من `sha256`."""
    canonical = json.dumps(
        payload(assessment, project_id=project_id,
                contradiction_keys=contradiction_keys),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["SCHEMA", "of", "payload"]
