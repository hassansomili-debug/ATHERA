"""AT-S10-* — إغلاق الفجوات (§9، §24، §17.4، §18.5، §51.9، §51.10، §32).

منطق خالص: كل ما يمكن فحصه بلا قاعدة بيانات يُفحص هنا. ما يحتاج HTTP وقاعدة
حقيقية في `test_at_s10_routers.py`.
"""
import datetime as dt

import pytest

from athera_api.providers import gateway
from athera_api.services import inbox, team
from athera_api.services.trends import brief

NOW = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)


# --------------------------------------------------------------------------
# §9 — بوابة الاعتماد
# --------------------------------------------------------------------------


def test_settled_approval_cannot_be_decided_again():
    """AT-S10-03 — البتّ مرتين يجعل «من اعتمد ومتى» قابلًا لإعادة الكتابة."""
    inbox.check_decidable("pending")  # لا يرمي
    for settled in ("approved", "rejected"):
        with pytest.raises(inbox.InboxError):
            inbox.check_decidable(settled)


def test_unknown_approval_status_is_rejected_not_assumed_pending():
    with pytest.raises(inbox.InboxError):
        inbox.check_decidable("maybe")


def test_unknown_alert_severity_is_treated_as_blocking():
    """شدّة مجهولة تُعامل معاملة الحاجب.

    الافتراض المعاكس يجعل تنبيهًا لم نتعرّف على شدّته يمرّ صامتًا، فيمرّ معه
    ما كان يجب أن يوقف بوابة.
    """
    assert inbox.is_blocking("blocking") is True
    assert inbox.is_blocking("warning") is False
    assert inbox.is_blocking("info") is False
    assert inbox.is_blocking("catastrophic") is True


def test_every_gate_in_the_spec_has_a_bilingual_label():
    """§9 — البوابات الأربع عشرة، كل منها بلغتين."""
    assert set(inbox.GATES) >= {f"G{n}" for n in range(13)} | {"GT1"}
    for gate, (arabic, english) in inbox.GATES.items():
        assert arabic.strip() and english.strip(), gate
        assert arabic != english, gate


# --------------------------------------------------------------------------
# §24 — التأليف
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [
    "ChatGPT", "GPT-4", "Claude", "Gemini", "ATHERA Assistant",
    "شات جي بي تي", "الذكاء الاصطناعي", "نموذج لغوي مساعد",
])
def test_authorship_is_refused_for_non_human_agents(name):
    """AT-S10-06 — §24: التأليف مسؤولية، ولا يتحملها نموذج."""
    with pytest.raises(team.TeamError):
        team.validate_author_name(name)


@pytest.mark.parametrize("name", ["حسن الصميلي", "Hassan Somili", "أ.د. نورة العتيبي"])
def test_human_names_pass(name):
    team.validate_author_name(name)  # لا يرمي


def test_empty_author_name_is_refused():
    with pytest.raises(team.TeamError):
        team.validate_author_name("   ")


def test_unknown_credit_role_is_refused():
    """AT-S10-07 — دور خارج CRediT يُرفض ولا يُسجَّل كما هو."""
    team.validate_credit_roles(["methodology", "supervision"])
    with pytest.raises(team.TeamError):
        team.validate_credit_roles(["methodology", "vibes"])


def test_credit_has_the_fourteen_roles():
    assert len(team.CREDIT_ROLES) == 14


def test_settled_decision_is_superseded_never_edited():
    team.check_supersede(None)  # قرار لم يُحسم بعد
    with pytest.raises(team.TeamError):
        team.check_supersede(NOW)


# --------------------------------------------------------------------------
# §51.9 — النشرة
# --------------------------------------------------------------------------


def test_brief_item_without_evidence_is_refused():
    """AT-S10-10 — بند بلا مرجع إشاعة."""
    brief.BriefItem(item_key="t1", title_ar="اتجاه", evidence_ref="openalex:W1")
    with pytest.raises(brief.BriefError):
        brief.BriefItem(item_key="t1", title_ar="اتجاه", evidence_ref="   ")


def test_empty_brief_says_so_instead_of_disappearing():
    """نشرة فارغة تُنتَج وتقول إن الرصد عمل ولم يجد.

    «لا جديد» و«لم يعمل الرصد» وضعان يستدعيان تصرفين مختلفين تمامًا.
    """
    empty = brief.Brief(cadence="weekly", period_start=NOW - dt.timedelta(days=7),
                        period_end=NOW)
    assert empty.is_empty
    assert "لم يجد" in empty.summary_ar
    assert "found nothing" in empty.summary_en


def test_brief_period_must_move_forward():
    with pytest.raises(brief.BriefError):
        brief.Brief(cadence="weekly", period_start=NOW, period_end=NOW)


def test_unknown_cadence_is_refused():
    with pytest.raises(brief.BriefError):
        brief.Brief(cadence="hourly", period_start=NOW - dt.timedelta(days=1),
                    period_end=NOW)


# --------------------------------------------------------------------------
# §51.10 — الجدة التنافسية
# --------------------------------------------------------------------------


def test_high_similarity_with_published_work_blocks():
    """AT-S10-11 — تشابه 0.9 مع عمل **منشور** يُسقط ادعاء الجدة."""
    verdict = brief.assess_novelty(0.90, published_source_id="src-1")
    assert verdict.is_blocking and verdict.needs_review
    assert "الجدة غير قائمة" in verdict.reason_ar


def test_high_similarity_with_unpublished_work_reviews_but_does_not_block():
    """التمييز جوهري: عمل قيد الإعداد في مكان آخر ليس سببًا لإسقاط فكرة."""
    verdict = brief.assess_novelty(0.90, published_source_id=None)
    assert verdict.needs_review
    assert not verdict.is_blocking


def test_moderate_similarity_reviews_only():
    verdict = brief.assess_novelty(0.70, published_source_id="src-1")
    assert verdict.needs_review and not verdict.is_blocking
    assert "لا يحجب وحده" in verdict.reason_ar


def test_low_similarity_passes_quietly():
    verdict = brief.assess_novelty(0.10, published_source_id="src-1")
    assert not verdict.needs_review and not verdict.is_blocking


def test_similarity_outside_the_unit_interval_is_refused():
    for value in (-0.1, 1.5):
        with pytest.raises(brief.BriefError):
            brief.assess_novelty(value, published_source_id=None)


# --------------------------------------------------------------------------
# §32 — المزوّد
# --------------------------------------------------------------------------


def test_unknown_provider_fails_loudly_instead_of_falling_back_to_null(monkeypatch):
    """AT-S10-13 — تشغيل يظن صاحبه أنه يستدعي نموذجًا وهو لا يستدعي شيئًا.

    كان أي اسم غير `openai` يسقط بصمت إلى `NullProvider`؛ فطلبٌ كُتب له
    `MODEL_PROVIDER=anthropic` بخطأ إملائي كان يعمل ويعيد مخرجات حتمية
    يظنها صاحبها من نموذج.
    """
    from athera_api.config import get_settings
    from athera_api.errors import AtheraError

    get_settings.cache_clear()
    monkeypatch.setenv("MODEL_PROVIDER", "anthropik")
    with pytest.raises(AtheraError):
        gateway.build_provider()
    get_settings.cache_clear()


def test_null_provider_is_the_default(monkeypatch):
    from athera_api.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MODEL_PROVIDER", "null")
    assert gateway.build_provider().name == "null"
    get_settings.cache_clear()


def test_anthropic_adapter_refuses_to_fake_embeddings():
    """إعادة أصفار كانت ستمرّ صامتة عبر pgvector فتُنتج جوارًا عشوائيًّا."""
    import asyncio

    from athera_api.providers.anthropic_adapter import (
        AnthropicAdapter,
        AnthropicEmbeddingUnsupported,
    )

    adapter = AnthropicAdapter(api_key="sk-test-not-used", default_model="m")
    with pytest.raises(AnthropicEmbeddingUnsupported):
        asyncio.run(adapter.embed(["نص"]))


def test_anthropic_adapter_requires_a_key():
    from athera_api.providers.anthropic_adapter import AnthropicAdapter

    with pytest.raises(ValueError):
        AnthropicAdapter(api_key="", default_model="m")


# --------------------------------------------------------------------------
# §51.11 — الرصد المجدول
# --------------------------------------------------------------------------


def test_monitoring_result_has_no_field_for_invented_opportunities():
    """AT-S10-14 — الرصد يجمع إشارات ولا يصنع فرصًا (§51.4).

    الفحص على **الحقول** لا على النية: غياب الحقل يمنع كتابة الرقم أصلًا.
    """
    import ast
    import pathlib

    # يُقرأ المصدر ولا يُستورد: الـworker يعتمد `temporalio` وليست تبعية للـAPI،
    # فاستيراده هنا كان سيربط اختبار قاعدة نزاهة بتوفّر حزمة لا علاقة لها بها.
    source = pathlib.Path(__file__).parents[3] / "services/worker/athera_worker/monitoring.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    harvest = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "HarvestResult"
    )
    names = {
        node.target.id for node in harvest.body if isinstance(node, ast.AnnAssign)
    }
    assert names == {"signals_recorded", "signals_rejected", "trends_touched"}
    assert not any("card" in name or "opportunit" in name for name in names)
