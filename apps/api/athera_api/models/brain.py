"""أثر العقل البحثي | Research Brain trace (§38.5، §7.1).

`guardrail_checks` تسجّل **كل** حاجز شُغّل، لا المخالفات فقط. معرفة أن
حاجزًا عمل ونجح جزء من الأثر بقدر معرفة أنه حجب.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk


class GuardrailCheck(Base, TenantScoped, Timestamped):
    __tablename__ = "guardrail_checks"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    guard_key: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)  # passed | blocked
    detail_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # المقتطف المخالف — يجعل الحجب قابلًا للمراجعة بدل أن يكون حكمًا غامضًا.
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
