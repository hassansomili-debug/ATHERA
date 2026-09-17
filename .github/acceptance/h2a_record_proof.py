"""RC-T1-H2-A — برهانُ الصفّ في الإنتاج | the durable record proof.

**يُشغَّل داخل آلة Fly** عبر `fly ssh console`، ويقرأ بتهيئةِ التطبيق
نفسِها — فالدورُ `athera_app`، بلا تجاوزٍ لسياسة الصفّ وبلا اعتمادِ ترحيل.

**والمعاملةُ للقراءة فقط، ويُتحقّق من ذلك لا يُفترض**: `SET TRANSACTION
READ ONLY` أوّلَ عبارةٍ، ثمّ `SHOW transaction_read_only` يجب أن يقول `on`،
وإلّا توقّف البرهانُ قبل أن يقرأ حرفًا.

**ولا يُطبع رابطُ الاتصال ولا كلمةُ مرورٍ ولا مفتاحٌ خامّ ولا جسمُ جواب.**
وما يُطبع: عددُ الصفوف، والحال، ورمزُ الجواب المخزون، ومعرّفُ البحث.

والسياقُ يُضبط **محلّيًّا بالمعاملة** (`set_config(..., true)`) كما يفعل
`db.tenant_session`: فيقرأ الفاعلُ صفَّه هو عبرَ سياسته، لا بتعطيلها.
"""
from __future__ import annotations

import asyncio
import os
import sys

TABLE = "idempotency_records"
#: الدورُ الذي يخدم الطلبات — **ويُشترط، فالدعوى تقوم عليه**.
RUNTIME_ROLE = "athera_app"


async def main() -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    tenant = os.environ["SMOKE_TENANT_ID"]
    actor = os.environ["SMOKE_ACTOR_ID"]
    digest = os.environ["SMOKE_KEY_DIGEST"]
    operation = os.environ["SMOKE_OPERATION"]
    project = os.environ["SMOKE_PROJECT_ID"]

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("FAILURE=db_read_only_verification_failed")
        print("detail=the runtime configuration carries no database url")
        return 1

    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            mode = (await conn.execute(text("SHOW transaction_read_only"))).scalar()
            print(f"TXN_READ_ONLY={mode}")
            if mode != "on":
                print("FAILURE=db_read_only_verification_failed")
                await conn.rollback()
                return 1

            # ══ الدورُ يُشترط، لا يُطبع ══
            #
            # **والطبعُ ملاحظةٌ لا إنفاذ.** دعوى هذا البرهان أنّ الصفَّ
            # يُقرأ «بسياسة الصفّ نافذة»، وهي لا تصحّ إلّا إن كان الاتصالُ
            # نفسُه خاضعًا لها. فرابطٌ يُضبط يومًا بدورٍ فائقٍ أو بـBYPASSRLS
            # أو باعتماد الترحيل يجعل الدعوى كذبًا **والبرهانَ أخضرَ** — فلا
            # يُكتفى بأن يُسجَّل الدورُ، بل يُشترط.
            posture = (await conn.execute(text(
                "SELECT r.rolname, r.rolsuper, r.rolbypassrls"
                "  FROM pg_roles r WHERE r.rolname = current_user"))).first()
            if posture is None:
                print("FAILURE=db_read_only_verification_failed")
                print("detail=the connected role is not readable from pg_roles")
                await conn.rollback()
                return 1
            who, is_super, bypasses = posture
            print(f"CONNECTED_AS={who}")
            print(f"ROLE_ROLSUPER={is_super}")
            print(f"ROLE_ROLBYPASSRLS={bypasses}")
            if who != RUNTIME_ROLE:
                print("FAILURE=db_read_only_verification_failed")
                print("detail=unexpected runtime database role")
                await conn.rollback()
                return 1
            if is_super:
                print("FAILURE=db_read_only_verification_failed")
                print("detail=the runtime role is a superuser")
                await conn.rollback()
                return 1
            if bypasses:
                print("FAILURE=db_read_only_verification_failed")
                print("detail=runtime role bypasses RLS")
                await conn.rollback()
                return 1

            # سياقُ الفاعل، محلّيًّا بالمعاملة — لا تغييرَ دورٍ ولا تعطيلَ سياسة.
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true),"
                     "       set_config('app.actor_id', :a, true)"),
                {"t": tenant, "a": actor})

            # **ويُقرأ السياقُ بعد ضبطه** — فالضبطُ الصامتُ الفاشل يجعل
            # الاستعلامَ يرى صفرَ صفوفٍ فيُقرأ ذلك «لا صفَّ» لا «لا سياق».
            settings = (await conn.execute(text(
                "SELECT current_setting('app.tenant_id', true),"
                "       current_setting('app.actor_id', true)"))).one()
            if str(settings[0]) != tenant or str(settings[1]) != actor:
                print("FAILURE=db_read_only_verification_failed")
                print("detail=the transaction-local RLS identity was not applied")
                await conn.rollback()
                return 1
            print("RLS_CONTEXT_APPLIED=yes")

            rows = (await conn.execute(
                text(f"SELECT state, response_status, completed_at IS NOT NULL,"
                     f"       response_body->>'id'"
                     f"  FROM {TABLE}"
                     f" WHERE tenant_id = CAST(:t AS uuid)"
                     f"   AND actor_user_id = CAST(:a AS uuid)"
                     f"   AND operation = :o"
                     f"   AND key_digest = :d"),
                {"t": tenant, "a": actor, "o": operation, "d": digest})).all()
            print(f"RECORD_ROWS={len(rows)}")
            if len(rows) != 1:
                print("FAILURE=idempotency_record_missing")
                await conn.rollback()
                return 1

            state, status, completed, stored_id = rows[0]
            print(f"RECORD_STATE={state}")
            print(f"RECORD_RESPONSE_STATUS={status}")
            print(f"RECORD_COMPLETED_AT_SET={completed}")
            if state != "completed" or not completed:
                print("FAILURE=idempotency_record_not_completed")
                await conn.rollback()
                return 1
            if status != 201:
                print("FAILURE=idempotency_record_not_completed")
                await conn.rollback()
                return 1
            if str(stored_id) != str(project):
                print("FAILURE=stored_response_mismatch")
                await conn.rollback()
                return 1
            print("RECORD_POINTS_AT_PROJECT=yes")

            domain = (await conn.execute(
                text("SELECT count(*) FROM research_projects"
                     " WHERE id = CAST(:p AS uuid)"
                     "   AND tenant_id = CAST(:t AS uuid)"),
                {"p": project, "t": tenant})).scalar()
            print(f"DOMAIN_ROWS={domain}")
            if domain != 1:
                print("FAILURE=domain_duplicate")
                await conn.rollback()
                return 1

            await conn.rollback()
            print("TXN_ROLLED_BACK=yes")
            print("H2A_RECORD_PROOF=pass")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
