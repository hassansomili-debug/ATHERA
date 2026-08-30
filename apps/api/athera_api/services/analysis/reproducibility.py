"""بيان إعادة الإنتاج | Reproducibility manifest (§18.1، §31.6، §39).

§18.1 تشترط حفظ الكود والحزم والإصدار ونسخة البيانات. بيان ناقص يعني
تشغيلة **غير قابلة لإعادة الإنتاج** — والوصف هنا ليس تحفظًا لغويًا: تشغيلة
بهذا الوصف لا تُستشهد في مخطوطة، وبوابة G9 في Sprint 7 ترفضها.

ونتيجة بلا تشغيلة لا وجود لها (§39): كل مخرَج يحمل `run_id` غير قابل للإفراغ.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .vocab import MANIFEST_FIELDS, SANDBOX_DEFAULTS


class ReproducibilityError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    """§31.6 — عقد بيئة التنفيذ. `network_egress` لا يُفعَّل من طلب مستخدم."""

    network_egress: bool = False
    max_cpu_seconds: int = int(SANDBOX_DEFAULTS["max_cpu_seconds"])
    max_memory_mb: int = int(SANDBOX_DEFAULTS["max_memory_mb"])
    max_wall_seconds: int = int(SANDBOX_DEFAULTS["max_wall_seconds"])

    def __post_init__(self) -> None:
        if self.network_egress:
            raise ReproducibilityError(
                "outbound network is disabled for analysis sandboxes (§31.6)"
            )
        if min(self.max_cpu_seconds, self.max_memory_mb, self.max_wall_seconds) <= 0:
            raise ReproducibilityError("resource quotas must be positive (§31.6)")


@dataclass(slots=True)
class RunManifest:
    """ما يلزم لإعادة إنتاج تشغيلة. أي حقل ناقص يُعلَن بالاسم."""

    code_hash: str | None = None
    runtime: str | None = None
    packages: dict[str, str] | None = None
    dataset_version_id: str | None = None
    dataset_freeze_id: str | None = None
    random_seed: int | None = None
    sandbox: SandboxSpec = field(default_factory=SandboxSpec)

    @property
    def missing_fields(self) -> list[str]:
        values = {
            "code_hash": self.code_hash,
            "runtime": self.runtime,
            "packages": self.packages or None,
            "dataset_version_id": self.dataset_version_id,
            "random_seed": self.random_seed,
        }
        return [key for key in MANIFEST_FIELDS if values.get(key) in (None, "", {})]

    @property
    def is_reproducible(self) -> bool:
        """§17.3 — ومع البيان الكامل، لا بد أن تكون البيانات مجمَّدة."""
        return not self.missing_fields and self.dataset_freeze_id is not None

    def fingerprint(self) -> str:
        """بصمة حتمية: نفس المدخلات ⇒ نفس البصمة (AT-S8-06)."""
        if self.missing_fields:
            raise ReproducibilityError(
                "cannot fingerprint an incomplete manifest: " + ", ".join(self.missing_fields)
            )
        payload = json.dumps(
            {
                "code_hash": self.code_hash, "runtime": self.runtime,
                "packages": dict(sorted((self.packages or {}).items())),
                "dataset_version_id": self.dataset_version_id,
                "dataset_freeze_id": self.dataset_freeze_id,
                "random_seed": self.random_seed,
            },
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class RunStatus:
    run_id: str
    reproducible: bool
    missing: list[str]
    fingerprint: str | None
    detail_ar: str
    detail_en: str


def assess(run_id: str, manifest: RunManifest) -> RunStatus:
    missing = manifest.missing_fields
    frozen = manifest.dataset_freeze_id is not None

    if missing:
        labels_ar = "، ".join(MANIFEST_FIELDS[key][0] for key in missing)
        labels_en = ", ".join(MANIFEST_FIELDS[key][1] for key in missing)
        return RunStatus(
            run_id=run_id, reproducible=False, missing=missing, fingerprint=None,
            detail_ar=f"التشغيلة غير قابلة لإعادة الإنتاج؛ ينقصها: {labels_ar}.",
            detail_en=f"Run is not reproducible; missing: {labels_en}.",
        )
    if not frozen:
        return RunStatus(
            run_id=run_id, reproducible=False, missing=["dataset_freeze_id"], fingerprint=None,
            detail_ar="التشغيلة على بيانات غير مجمَّدة؛ لا يمكن إعادة إنتاجها (§17.3).",
            detail_en="Run used a non-frozen dataset; it cannot be reproduced (§17.3).",
        )
    return RunStatus(
        run_id=run_id, reproducible=True, missing=[], fingerprint=manifest.fingerprint(),
        detail_ar="بيان إعادة الإنتاج مكتمل والبيانات مجمَّدة.",
        detail_en="The reproducibility manifest is complete and the dataset is frozen.",
    )


@dataclass(frozen=True, slots=True)
class AnalysisOutput:
    """§39 — «النتائج غير المرتبطة بتحليل: صفر». `run_id` إلزامي بالبناء."""

    output_id: str
    run_id: str
    output_kind: str        # table | figure | statistic | model
    label_ar: str
    payload: dict
    test_key: str | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ReproducibilityError("an output cannot exist without a run (§39)")
