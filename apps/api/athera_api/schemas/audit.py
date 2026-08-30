"""عقود التدقيق | Audit contracts (read-only by design — §37)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    occurred_at: dt.datetime
    actor_user_id: uuid.UUID | None
    actor_kind: str
    action: str
    object_type: str
    object_id: uuid.UUID | None
    reason: str | None
    chain_seq: int
    hash: str


class ChainVerificationResponse(BaseModel):
    intact: bool
    broken_at_seq: int | None
    events_checked: int
