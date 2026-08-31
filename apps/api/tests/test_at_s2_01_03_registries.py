"""AT-S2-01/02/03 — سجل الأجنتات والأدوات (§8، §7.1).

القيمة هنا ليست في وجود السجل، بل في أن ما لا توجد له أداة لا يمكن أن يحدث.
"""
import pytest

from athera_api.brain import agents as registry
from athera_api.brain import tools as tool_registry

# الأجنتات الستة عشر — القائمة مكتوبة يدويًا عمدًا حتى يفشل الاختبار إذا
# حُذف أجنت من السجل بصمت.
#
# كانت سبعة عشر. سقط `promotion_auditor` مع إزالة الترقية الأكاديمية
# (ADR-0005): كان يحلّل لائحة جامعية ويحسب فجوة ترقية، ولا موضع له في منصة
# بحث ونشر. ولم يسقط معه أجنت واحد من أجنتات النزاهة.
SPEC_AGENTS = {
    "research_manager", "opportunity_scout", "literature_agent",
    "evidence_curator", "golden_thread_agent", "theory_agent", "methodology_agent",
    "ethics_agent", "data_agent", "analysis_agent", "scientific_writer",
    "journal_matcher", "peer_review_council", "revision_agent", "thesis_miner",
    "authorship_agent",
}


def test_all_sixteen_agents_from_spec_are_registered():
    assert set(registry.AGENTS) == SPEC_AGENTS
    assert len(registry.AGENTS) == 16


def test_every_agent_declares_a_constraint_in_both_languages():
    """§8 يعطي كل أجنت قيدًا. أجنت بلا قيد أجنت بلا حوكمة."""
    for key, spec in registry.AGENTS.items():
        assert spec.constraint_ar.strip(), f"{key} has no Arabic constraint"
        assert spec.constraint_en.strip(), f"{key} has no English constraint"
        assert spec.guards, f"{key} declares no guardrails"


def test_every_agent_declares_at_least_one_tool_and_nothing_unknown():
    known = set(tool_registry.all_tools())
    for key, spec in registry.AGENTS.items():
        assert spec.allowed_tools, f"{key} has no tools and cannot do anything useful"
        unknown = spec.allowed_tools - known
        assert not unknown, f"{key} references unregistered tools: {unknown}"


def test_base_guards_apply_to_every_agent():
    for key, spec in registry.AGENTS.items():
        missing = registry.BASE_GUARDS - spec.guards
        assert not missing, f"{key} is missing base guards: {missing}"


def test_agents_that_touch_numbers_require_an_analysis_run():
    """قيود §8 المتعلقة بالأرقام تُترجم إلى حاجز، لا إلى نص في تعليمات."""
    for key in ("analysis_agent", "scientific_writer", "data_agent"):
        assert "numbers_require_analysis_run" in registry.AGENTS[key].guards


def test_journal_matcher_cannot_promise_acceptance():
    assert "no_acceptance_guarantee" in registry.AGENTS["journal_matcher"].guards


def test_authorship_agent_cannot_assign_authorship():
    assert "authorship_needs_human" in registry.AGENTS["authorship_agent"].guards


# ── AT-S2-03: ما لا توجد له أداة لا يمكن أن يحدث ──

def test_no_registered_tool_has_a_side_effect():
    for key, spec in tool_registry.all_tools().items():
        assert spec.side_effect == "read", f"{key} is not read-only in Sprint 2"


def test_registry_refuses_to_register_a_writing_tool():
    async def _handler(session, **kwargs):  # pragma: no cover
        return None

    with pytest.raises(tool_registry.ToolRegistryError):
        tool_registry.register(tool_registry.ToolSpec(
            key="dataset.mutate_raw", name_ar="تعديل بيانات خام",
            name_en="Mutate raw dataset", side_effect="write", handler=_handler,
        ))


def test_registry_refuses_a_decision_tool():
    async def _handler(session, **kwargs):  # pragma: no cover
        return None

    with pytest.raises(tool_registry.ToolRegistryError):
        tool_registry.register(tool_registry.ToolSpec(
            key="approval.decide", name_ar="البت في اعتماد", name_en="Decide approval",
            side_effect="decide", handler=_handler,
        ))


def test_forbidden_capabilities_are_absent_from_the_registry():
    """الأفعال الخمسة المحظورة لا تملك أداة، فلا يستطيع أي أجنت طلبها."""
    keys = set(tool_registry.all_tools())
    for capability in tool_registry.FORBIDDEN_CAPABILITIES:
        assert not any(capability in key for key in keys), f"a tool exposes {capability}"


def test_no_agent_can_reach_approval_or_raw_data():
    all_allowed = set().union(*(spec.allowed_tools for spec in registry.AGENTS.values()))
    for forbidden in ("approval", "raw", "submit", "authorship.assign"):
        assert not any(forbidden in tool for tool in all_allowed), (
            f"an agent can reach a '{forbidden}' tool"
        )
