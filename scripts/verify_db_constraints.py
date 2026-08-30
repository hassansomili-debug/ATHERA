"""التحقق من قيود قاعدة البيانات | Database constraint verification.

الغرض: تحويل ادعاء إلى برهان. الترحيلات الثلاثة عشر تحمل عشرات القيود
والمشغّلات التي تمنع أشياء بعينها — ومنعُها **مكتوب** حتى الآن، لا مُختبَر.

هذا السكربت يحاول ارتكاب كل ممنوع، ويفشل إن **نجح** أيٌّ منها. يُشغَّل مرة
واحدة على قاعدة مهاجَرة:

    make verify-constraints

⚠️ لم يُشغَّل بعد: البيئة التي كُتب فيها بلا PostgreSQL. أول تشغيل هو
الاختبار الحقيقي له وللقيود معًا.
"""
from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass

DEFAULT_URL = os.getenv(
    "DATABASE_VERIFY_URL",
    "postgresql+psycopg://athera_app:athera_app_pw@localhost:5432/athera",
)


@dataclass(frozen=True)
class ForbiddenAttempt:
    """محاولة يجب أن تفشل. نجاحها يعني أن القيد غائب أو معطَّل."""

    key: str
    reference: str
    description_ar: str
    sql: str
    params: dict


def attempts(tenant_id: str, user_id: str) -> list[ForbiddenAttempt]:
    t = {"t": tenant_id, "u": user_id}
    return [
        ForbiddenAttempt(
            "audit_update", "§37 / ADR-0004",
            "تعديل سجل تدقيق",
            "UPDATE audit_events SET reason = 'tampered'", {},
        ),
        ForbiddenAttempt(
            "audit_delete", "§37 / ADR-0004",
            "حذف سجل تدقيق",
            "DELETE FROM audit_events", {},
        ),
        ForbiddenAttempt(
            "memory_model_output_verified", "§7.4",
            "ترقية مخرَج نموذج إلى ذاكرة موثقة",
            """INSERT INTO researcher_memories
                 (tenant_id, memory_category, statement_ar, source_type, verification_status)
               VALUES (:t, 'researcher_fact', 'ادعاء', 'model_output', 'verified')""", t,
        ),
        ForbiddenAttempt(
            "memory_verified_without_verifier", "§7.4",
            "ذاكرة موثقة بلا مُحقِّق وتاريخ",
            """INSERT INTO researcher_memories
                 (tenant_id, memory_category, statement_ar, source_type, verification_status)
               VALUES (:t, 'researcher_fact', 'ادعاء', 'user_statement', 'verified')""", t,
        ),
        ForbiddenAttempt(
            "excerpt_without_text_access", "§14.5",
            "اقتطاف نص من مصدر بيانات وصفية فقط",
            """INSERT INTO evidence_excerpts
                 (tenant_id, source_id, quote, locator, access_basis, created_by)
               VALUES (:t, gen_random_uuid(), 'نص', 'p.1', 'abstract_metadata_only', :u)""", t | {"u": user_id},
        ),
        ForbiddenAttempt(
            "opportunity_ready_without_rights", "§23.9 / TC-06",
            "فرصة جاهزة للتقديم بلا اعتماد حقوق وتأليف",
            """INSERT INTO publication_opportunities
                 (tenant_id, thesis_id, opportunity_kind, paper_kind, working_title_ar, status)
               VALUES (:t, gen_random_uuid(), 'independent_question', 'extraction',
                       'عنوان', 'ready_to_submit')""", t,
        ),
        ForbiddenAttempt(
            "authorship_party_is_ai", "§24.2",
            "إسناد تأليف لطرف غير إنسان أو جهة",
            """INSERT INTO authorship_parties (tenant_id, party_kind, display_name)
               VALUES (:t, 'ai', 'نموذج')""", t,
        ),
        ForbiddenAttempt(
            "patch_applied_without_actor", "§21",
            "تطبيق رقعة مراجعة بلا فاعل ونسخة جديدة",
            """INSERT INTO review_patches
                 (tenant_id, report_id, section_key, rationale_ar, status)
               VALUES (:t, gen_random_uuid(), 'method', 'سبب', 'applied')""", t,
        ),
        ForbiddenAttempt(
            "analysis_run_with_network", "§31.6",
            "تشغيل تحليل بإنترنت صادر",
            """INSERT INTO analysis_runs
                 (tenant_id, plan_id, dataset_version_id, dataset_freeze_id, tool,
                  network_egress, started_at)
               VALUES (:t, gen_random_uuid(), gen_random_uuid(), 'FRZ-x', 'python',
                       true, now())""", t,
        ),
        ForbiddenAttempt(
            "interpretation_managerial_without_theoretical", "§18.3",
            "دلالة إدارية بلا تفسير نظري",
            """INSERT INTO interpretations (tenant_id, output_id, result_ar, managerial_ar)
               VALUES (:t, gen_random_uuid(), 'نتيجة', 'دلالة إدارية')""", t,
        ),
        ForbiddenAttempt(
            "signal_model_output_as_evidence", "§51.1",
            "احتساب مخرَج نموذج دليلًا على اتجاه",
            """INSERT INTO trend_signals
                 (tenant_id, trend_id, pattern, source_type, source_id, observed_at,
                  counts_as_evidence)
               VALUES (:t, gen_random_uuid(), 'topic_emergence', 'model_output', 'x',
                       now(), true)""", t,
        ),
        ForbiddenAttempt(
            "signal_without_source", "§51.11",
            "إشارة يتيمة بلا معرّف مصدر",
            """INSERT INTO trend_signals
                 (tenant_id, trend_id, pattern, source_type, source_id, observed_at)
               VALUES (:t, gen_random_uuid(), 'topic_emergence', 'openalex', '', now())""", t,
        ),
    ]


def main() -> int:  # pragma: no cover - يحتاج قاعدة بيانات حية
    from sqlalchemy import create_engine, text

    engine = create_engine(os.getenv("DATABASE_VERIFY_URL", DEFAULT_URL))
    tenant_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())

    passed, leaked = 0, []
    # اتصال مستقل لكل محاولة: فشل عبارة في PostgreSQL يُبطل المعاملة كلها،
    # فمشاركتها بين المحاولات تجعل نتيجة كل محاولة تعتمد على سابقتها.
    for attempt in attempts(tenant_id, user_id):
        with engine.connect() as connection:
            connection.execute(text("SELECT set_config('app.tenant_id', :t, true)"),
                               {"t": tenant_id})
            try:
                connection.execute(text(attempt.sql), attempt.params)
            except Exception:
                connection.rollback()
                passed += 1
                print(f"  ✓ {attempt.key} — مُنعت كما يجب ({attempt.reference})")
            else:
                connection.rollback()
                leaked.append(attempt)
                print(f"  ✗ {attempt.key} — نجحت وكان يجب أن تفشل ({attempt.reference})")

    total = passed + len(leaked)
    print(f"\nمُنع {passed} من {total} فعل ممنوع.")
    if leaked:
        print("قيود غائبة أو معطَّلة:")
        for attempt in leaked:
            print(f"  - {attempt.key}: {attempt.description_ar} ({attempt.reference})")
        return 1
    print("كل القيود الحرجة تعمل.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
