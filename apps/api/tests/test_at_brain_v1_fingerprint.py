"""البصمةُ تعني تغيّرَ البحث لا تغيّرَ القراءة | The context fingerprint (Wave 2-A §39–§40).

**ما تحرسه هذه الرقعة خاصّيتان متعاديتان**، وسقوطُ أيّهما يُفقد البصمةَ
معناها:

    تثبت حين لا يتغيّر شيءٌ ذو معنى   — وإلا تقادمَ كلُّ قولٍ بلا سبب
    تتغيّر حين يتغيّر البحث            — وإلا بقي القولُ القديم يبدو جاريًا

والأولى هي التي تسقط سهوًا: يكفي أن يدخلها الوقتُ أو ترتيبُ صفوفٍ من
قاعدة بيانات، فتصير كلُّ قراءةٍ بصمةً جديدة — ولا يُكتشف ذلك إلا حين
يشتكي باحثٌ أنّ توصياته تختفي كلّما فتح الصفحة.
"""
from __future__ import annotations

import pytest

from athera_api.research_brain import fingerprint as fp
from athera_api.research_brain import ontology as o
from athera_api.research_brain.rules import Assessment, BrainFieldView, CandidateView

PROJECT = "project:1"


def _graph(*, question: str = "ما أثر التدريب على الأداء؟") -> o.ResearchGraph:
    project = o.Project(id="project:1", label_ar="بحثٌ تجريبيّ")
    rq = o.ResearchQuestion(id="rq:1", label_ar=question)
    return o.ResearchGraph(
        entities=[project, rq],
        relationships=[o.Relationship(kind=o.RelationKind.PROJECT_HAS_QUESTION,
                                      source_id="project:1", target_id="rq:1")])


def _assessment(**kw) -> Assessment:
    return Assessment(graph=kw.pop("graph", _graph()), **kw)


# ═════════════════ أ · تثبت على ما لا معنى لتغيّره ═════════════════


def test_the_same_research_gives_the_same_fingerprint():
    """**الخاصّية الأولى**: لقطتان لبحثٍ واحد بصمةٌ واحدة."""
    assert fp.of(_assessment(), project_id=PROJECT) == \
        fp.of(_assessment(), project_id=PROJECT)


def test_reading_order_does_not_change_the_fingerprint():
    """**وترتيبُ الصفوف من القاعدة عابر** — و`ORDER BY` غائبٌ عن استعلامات كثيرة.

    فلو دخل الترتيبُ البصمةَ لَتغيّرت بين قراءتين لبحثٍ لم يمسّه أحد،
    ولَبدا ذلك عطبًا في المنتج لا في الحارس.
    """
    project = o.Project(id="project:1", label_ar="بحثٌ تجريبيّ")
    rq = o.ResearchQuestion(id="rq:1", label_ar="ما أثر التدريب على الأداء؟")
    link = o.Relationship(kind=o.RelationKind.PROJECT_HAS_QUESTION,
                          source_id="project:1", target_id="rq:1")

    forward = Assessment(graph=o.ResearchGraph(entities=[project, rq],
                                               relationships=[link]))
    reversed_ = Assessment(graph=o.ResearchGraph(entities=[rq, project],
                                                 relationships=[link]))
    assert fp.of(forward, project_id=PROJECT) == fp.of(reversed_, project_id=PROJECT)


def test_field_and_candidate_order_does_not_change_the_fingerprint():
    a = _assessment(fields=(BrainFieldView(key="method", state="missing"),
                            BrainFieldView(key="sample", state="known")),
                    candidates=(CandidateView(id="c1", status="approved"),
                                CandidateView(id="c2", status="unverified")))
    b = _assessment(fields=(BrainFieldView(key="sample", state="known"),
                            BrainFieldView(key="method", state="missing")),
                    candidates=(CandidateView(id="c2", status="unverified"),
                                CandidateView(id="c1", status="approved")))
    assert fp.of(a, project_id=PROJECT) == fp.of(b, project_id=PROJECT)


def test_no_clock_enters_the_fingerprint():
    """**ولا وقتَ فيها** — يُفحص المُدخلُ نفسُه لا الناتج.

    والفحصُ على المُدخل قصدًا: بصمتان متساويتان في اختبارٍ سريع لا تنفيان
    وجودَ حقلِ وقتٍ يتغيّر كلَّ ساعة. فتُقرأ المفاتيحُ بأسمائها.
    """
    payload = fp.payload(_assessment(), project_id=PROJECT)
    forbidden = {"assembled_at", "created_at", "now", "timestamp", "request_id"}
    assert not (forbidden & set(payload)), f"حقلٌ متقلّب دخل البصمة: {payload.keys()}"


def test_read_notes_are_not_part_of_the_fingerprint():
    """**وما تعذّرت قراءتُه بيانٌ عن اللقطة لا محتوًى فيها.**

    فتحسينُ رسالةِ خطأٍ ليس تغييرًا في البحث، ولو دخلت البصمةَ لَأبطل
    كلَّ توصيةٍ قائمة.
    """
    assert "read_notes" not in fp.payload(_assessment(), project_id=PROJECT)


# ═════════════════ ب · وتتغيّر على ما له معنى ═════════════════


@pytest.mark.parametrize("label, mutate", [
    ("سؤالٌ أُعيدت صياغتُه",
     lambda: _assessment(graph=_graph(question="ما علاقةُ التدريب بالرضا؟"))),
    ("حقلٌ صار معروفًا",
     lambda: _assessment(fields=(BrainFieldView(key="method", state="known"),))),
    ("مرشّحٌ اعتُمد",
     lambda: _assessment(candidates=(CandidateView(id="c1", status="approved"),))),
    ("قسمٌ كُتب",
     lambda: _assessment(sections={"introduction": "نصٌّ جديد"})),
])
def test_a_material_change_changes_the_fingerprint(label, mutate):
    """كلُّ تغيّرٍ يُبنى عليه حكمٌ يُنتج بصمةً أخرى."""
    assert fp.of(mutate(), project_id=PROJECT) != fp.of(_assessment(), project_id=PROJECT), \
        f"لم تتغيّر البصمةُ مع: {label}"


def test_a_recorded_contradiction_changes_the_fingerprint():
    """**والتعارضُ حالٌ من أحوال البحث** — ظهورُه تغيّرٌ وزوالُه تغيّر."""
    plain = fp.of(_assessment(), project_id=PROJECT)
    conflicted = fp.of(_assessment(), project_id=PROJECT, contradiction_keys=["claim:9"])
    assert plain != conflicted


def test_two_projects_never_share_a_fingerprint():
    """**والبحثُ جزءٌ من هويّة اللقطة** — ولو تطابق كلُّ ما فيهما اليوم."""
    assert fp.of(_assessment(), project_id="project:1") != \
        fp.of(_assessment(), project_id="project:2")


def test_changing_the_backing_evidence_changes_the_fingerprint():
    """**سندُ المعرفة جزءٌ منها.**

    حقلٌ صار `known` بذاكرةٍ أخرى ليس الحقلَ نفسه: تبديلُ السند تغيّرٌ
    يُبنى عليه حكمُ `RB-PROVENANCE-01`.
    """
    first = _assessment(fields=(BrainFieldView(
        key="method", state="known", backing_memory_ids=("mem:1",)),))
    second = _assessment(fields=(BrainFieldView(
        key="method", state="known", backing_memory_ids=("mem:2",)),))
    assert fp.of(first, project_id=PROJECT) != fp.of(second, project_id=PROJECT)


# ═════════════════ ج · شكلُ البصمة وصيغتُها ═════════════════


def test_the_fingerprint_is_a_sha256_hex_digest():
    """ستٌّ وستون محرفًا ستّ عشريًّا — والقيدُ في القاعدة يفحص الطولَ نفسَه."""
    value = fp.of(_assessment(), project_id=PROJECT)
    assert len(value) == 64
    assert all(ch in "0123456789abcdef" for ch in value)


def test_the_schema_version_is_carried_in_the_payload():
    """**وبصمتان بصيغتين مختلفتين لا تُقارَنان.**

    فلو تغيّر ما يدخل البصمةَ يومًا بلا أن تتغيّر النسخة، لَقُورنت بصمةٌ
    قديمةٌ بجديدةٍ فبدا بحثٌ تغيّر ولم يتغيّر — أو العكس.
    """
    assert fp.payload(_assessment(), project_id=PROJECT)["schema"] == fp.SCHEMA
    assert fp.SCHEMA.startswith("pubriva.")


def test_an_empty_assessment_still_has_a_fingerprint():
    """**وبحثٌ خاوٍ لا يُسقط الحساب** (§57) — يُبصَم فارغًا ولا يُرمى."""
    assert len(fp.of(Assessment(), project_id=PROJECT)) == 64
