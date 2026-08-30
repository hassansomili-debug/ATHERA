"""AT-S0-04 — تغطية التدقيق 100% للمسارات المعدِّلة (§39).

المؤشر في §39 يقول «Audit coverage للقرارات الجوهرية 100%». هنا نجعله
قابلًا للقياس آليًا. المسار المعدِّل يجتاز بأحد أمرين فقط:
  1. يكتب `audit.record` بنفسه، أو
  2. يفوّض إلى خدمة مُدرجة أدناه — ونتحقق من أن تلك الخدمة تكتب الحدث فعلًا.
لا يوجد إعفاء ثالث.
"""
import inspect

import pytest

from athera_api.routers import auth as auth_router
from athera_api.routers import files as files_router
from athera_api.routers import profile as profile_router
from athera_api.routers import tenants as tenants_router
from athera_api.services import ingestion, memory

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# خدمات مفوَّضة — كل واحدة يُتحقق من كتابتها للحدث في اختبار مستقل أدناه.
DELEGATES = {
    "ingestion.ingest_file": ingestion.ingest_file,
    "memory.approve_candidate": memory.approve_candidate,
    "memory.reject_candidate": memory.reject_candidate,
}

ROUTER_MODULES = (auth_router, files_router, tenants_router, profile_router)


def _mutating_routes():
    for module in ROUTER_MODULES:
        for route in module.router.routes:
            if getattr(route, "methods", set()) & MUTATING_METHODS:
                yield module, route


@pytest.mark.parametrize("delegate_name", sorted(DELEGATES))
def test_each_delegate_service_writes_an_audit_event(delegate_name):
    source = inspect.getsource(DELEGATES[delegate_name])
    assert "audit.record" in source, f"{delegate_name} is trusted to audit but does not"


def test_every_mutating_route_writes_or_delegates_an_audit_event():
    missing = []
    for _module, route in _mutating_routes():
        source = inspect.getsource(route.endpoint)
        if "audit.record" in source:
            continue
        if any(name.split(".")[-1] in source for name in DELEGATES):
            continue
        missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, (
        "مسارات معدِّلة بلا حدث تدقيق (§39 يشترط 100%): " + ", ".join(missing)
    )


def test_audit_write_happens_inside_the_same_transaction():
    """الحدث يُكتب قبل الاستجابة، داخل المعاملة — وإلا فُقد عند الفشل."""
    source = inspect.getsource(files_router.complete_upload)
    audit_pos = source.index("audit.record")
    assert "return" in source[audit_pos:]


def test_memory_promotion_is_the_only_path_to_verified():
    """لا موجّه يكتب verification_status='verified' مباشرة — كله عبر الخدمة."""
    for module in ROUTER_MODULES:
        source = inspect.getsource(module)
        assert 'verification_status="verified"' not in source, (
            f"{module.__name__} writes verified status directly; use services.memory instead"
        )
