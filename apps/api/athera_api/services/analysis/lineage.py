"""سلسلة إصدارات البيانات | Dataset lineage (§17.2، §17.3، TC-07).

قاعدتان لا تُخترقان:
  • RAW لا يُعدَّل. التنظيف **ينشئ نسخة جديدة** تشير إلى أصلها (TC-07).
  • التحليل لا يعمل إلا على نسخة مجمَّدة — بيانات متحركة تعني نتيجة غير
    قابلة لإعادة الإنتاج، فلا يُسمح بها أصلًا (§17.3).
"""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field

from .vocab import ALLOWED_TRANSITIONS, DATASET_STATES


class LineageError(Exception):
    """انتهاك لسلسلة الإصدارات — يُرفع بدل تصحيح صامت."""


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    version_id: str
    dataset_id: str
    state: str
    label: str
    checksum: str
    parent_version_id: str | None = None
    frozen_at: dt.datetime | None = None
    freeze_id: str | None = None
    row_count: int | None = None
    change_note_ar: str | None = None

    def __post_init__(self) -> None:
        if self.state not in DATASET_STATES:
            raise LineageError(f"unknown dataset state: {self.state}")
        if self.state == "raw" and self.parent_version_id is not None:
            raise LineageError("a raw version has no parent by definition (§17.2)")
        if self.state != "raw" and self.parent_version_id is None:
            raise LineageError(f"a '{self.state}' version must record its parent (§17.2)")

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None and self.freeze_id is not None

    @property
    def is_immutable(self) -> bool:
        """RAW دائمًا، وأي نسخة مجمَّدة."""
        return self.state == "raw" or self.is_frozen


def derive(
    parent: DatasetVersion, *, new_state: str, label: str, checksum: str,
    change_note_ar: str, row_count: int | None = None, version_id: str,
) -> DatasetVersion:
    """ينشئ نسخة مشتقة. لا يعدّل الأصل إطلاقًا — هذا هو TC-07."""
    allowed = ALLOWED_TRANSITIONS.get(parent.state, frozenset())
    if new_state not in allowed:
        raise LineageError(
            f"transition '{parent.state}' → '{new_state}' is not allowed (§17.2); "
            f"allowed: {sorted(allowed)}"
        )
    if not change_note_ar.strip():
        raise LineageError("a derived version must record why it differs from its parent")

    return DatasetVersion(
        version_id=version_id, dataset_id=parent.dataset_id, state=new_state,
        label=label, checksum=checksum, parent_version_id=parent.version_id,
        row_count=row_count, change_note_ar=change_note_ar,
    )


def freeze(version: DatasetVersion, *, at: dt.datetime) -> DatasetVersion:
    """§17.3 — بوابة G6: تنتج Data Freeze ID يُستخدم في كل تحليل لاحق."""
    if version.state == "raw":
        raise LineageError("raw data is not analysed directly; clean it first (§17.2)")
    if version.is_frozen:
        raise LineageError("this version is already frozen")

    payload = f"{version.dataset_id}|{version.version_id}|{version.checksum}|{at.isoformat()}"
    freeze_id = "FRZ-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    return DatasetVersion(
        version_id=version.version_id, dataset_id=version.dataset_id,
        state="analysis_locked" if version.state == "cleaned" else version.state,
        label=version.label, checksum=version.checksum,
        parent_version_id=version.parent_version_id, frozen_at=at, freeze_id=freeze_id,
        row_count=version.row_count, change_note_ar=version.change_note_ar,
    )


@dataclass(slots=True)
class LineageChain:
    versions: list[DatasetVersion] = field(default_factory=list)

    def add(self, version: DatasetVersion) -> None:
        self.versions.append(version)

    def path_to_raw(self, version_id: str) -> list[DatasetVersion]:
        """يتتبع النسخة إلى أصلها الخام — الأثر الذي يجعل النتيجة قابلة للتدقيق."""
        by_id = {v.version_id: v for v in self.versions}
        current = by_id.get(version_id)
        if current is None:
            raise LineageError(f"unknown version: {version_id}")
        chain = [current]
        while current.parent_version_id is not None:
            current = by_id.get(current.parent_version_id)
            if current is None:
                raise LineageError("lineage is broken: a parent version is missing")
            chain.append(current)
        if chain[-1].state != "raw":
            raise LineageError("lineage does not terminate at a raw version (§17.2)")
        return chain
