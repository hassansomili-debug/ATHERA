"""مهمة التحقق الدورية من سلسلة التدقيق | Scheduled audit-chain verification (ADR-0004).

تُشغَّل دوريًا. أي انقطاع يفتح `integrity_alert` ولا يُبتلع صامتًا.
"""
import asyncio
import sys

from sqlalchemy import select

from ..db import system_session, tenant_session
from ..models.audit import IntegrityAlert
from ..models.identity import Tenant
from . import audit


async def run() -> int:
    async with system_session() as session:
        tenant_ids = (await session.execute(select(Tenant.id))).scalars().all()

    failures = 0
    for tenant_id in tenant_ids:
        async with tenant_session(tenant_id) as session:
            intact, broken_at = await audit.verify_chain(session, tenant_id)
            if intact:
                print(f"[ok]   tenant={tenant_id} audit chain intact")
                continue
            failures += 1
            print(f"[FAIL] tenant={tenant_id} audit chain broken at seq={broken_at}")
            session.add(
                IntegrityAlert(
                    tenant_id=tenant_id,
                    alert_type="audit_chain_broken",
                    severity="critical",
                    name_ar="انقطاع في سلسلة سجل التدقيق",
                    name_en="Audit chain integrity failure",
                    detail_ar=f"أول سجل مكسور: {broken_at}",
                    detail_en=f"First broken sequence: {broken_at}",
                )
            )
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(run()) else 0)
