"""عقود محرك التحليل | Analysis contracts (§17، §18)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class DatasetCreateRequest(BaseModel):
    project_id: uuid.UUID
    name_ar: str = Field(min_length=2)
    name_en: str | None = None
    classification: str = Field(default="C3", pattern="^C[0-4]$")
    raw_label: str = Field(default="النسخة الخام", min_length=2)
    raw_checksum: str = Field(min_length=8, max_length=64)
    row_count: int | None = None


class VersionCreateRequest(BaseModel):
    parent_version_id: uuid.UUID
    state: str = Field(pattern="^(cleaned|derived)$")
    label: str = Field(min_length=2)
    checksum: str = Field(min_length=8, max_length=64)
    change_note_ar: str = Field(min_length=3)
    row_count: int | None = None


class DatasetVersionResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    state: str
    state_label: str
    label: str
    checksum: str
    parent_version_id: uuid.UUID | None
    row_count: int | None
    change_note_ar: str | None
    freeze_id: str | None
    frozen_at: dt.datetime | None
    is_immutable: bool


class DatasetResponse(BaseModel):
    """المجموعة مع سلسلة نسخها — الحالة تُقرأ من النسخ لا من حقل مستقل.

    حقل «مجمَّدة» على مستوى المجموعة كان سيكذب: مجموعة واحدة قد تحمل نسخة
    خامًا ونسخة منقّاة ونسخة مجمَّدة في آن واحد.
    """

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    classification: str
    versions: list[DatasetVersionResponse]


class FreezeResponse(BaseModel):
    """§17.3 — بوابة G6 تنتج معرّف تجميد يُستخدم في كل تحليل لاحق."""

    version_id: uuid.UUID
    freeze_id: str
    frozen_at: dt.datetime
    note_ar: str = "لا يعمل التحليل إلا على نسخة مجمَّدة؛ هذا معرّفها."
    note_en: str = "Analysis runs only on a frozen version; this is its identifier."


class PlannedTestInput(BaseModel):
    test_key: str = Field(min_length=1, max_length=64)
    test_kind: str
    variables: list[str] = []
    note_ar: str | None = None


class PlanCreateRequest(BaseModel):
    project_id: uuid.UUID
    version_label: str = "v1"
    summary_ar: str | None = None
    tests: list[PlannedTestInput] = Field(min_length=1)


class PlanResponse(BaseModel):
    id: uuid.UUID
    version_label: str
    is_locked: bool
    approved_at: dt.datetime | None
    tests: list[PlannedTestInput]


class RunCreateRequest(BaseModel):
    plan_id: uuid.UUID
    dataset_version_id: uuid.UUID
    tool: str = Field(pattern="^(spss|smartpls|nvivo|python|r)$")
    executed_test_keys: list[str] = []
    code_hash: str | None = None
    runtime: str | None = None
    packages: dict[str, str] | None = None
    random_seed: int | None = None


class TestClassificationResponse(BaseModel):
    test_key: str
    origin: str
    reason: str


class RunResponse(BaseModel):
    """§18.1 — «قابل لإعادة الإنتاج» وصف مكتسب، والناقص يُسمّى."""

    id: uuid.UUID
    tool: str
    status: str
    is_reproducible: bool
    missing_manifest_fields: list[str]
    fingerprint: str | None
    classifications: list[TestClassificationResponse]
    exploratory_test_keys: list[str]
    planned_not_run: list[str]
    requires_disclosure: bool
    detail: str
    detail_ar: str
    detail_en: str


class OutputCreateRequest(BaseModel):
    output_kind: str = Field(pattern="^(table|figure|statistic|model)$")
    label_ar: str = Field(min_length=2)
    label_en: str | None = None
    test_key: str | None = None
    payload: dict = {}


class InterpretationRequest(BaseModel):
    """§18.3 — أربع طبقات منفصلة، وسلسلة سند مفروضة."""

    result_ar: str = Field(min_length=2)
    result_en: str | None = None
    statistical_ar: str | None = None
    theoretical_ar: str | None = None
    managerial_ar: str | None = None


class LayerResponse(BaseModel):
    layer: str
    label: str
    text_ar: str | None
    text_en: str | None


class InterpretationResponse(BaseModel):
    output_id: uuid.UUID
    layers: list[LayerResponse]
    layers_present: list[str]
    approved_at: dt.datetime | None
    note_ar: str = "الطبقات الأربع تبقى منفصلة؛ دمجها يحوّل رقمًا إلى ادعاء."
    note_en: str = "The four layers stay separate; merging turns a number into a claim."


class ToolCapabilityResponse(BaseModel):
    tool: str
    label: str
    import_formats: list[str]
    export_formats: list[str]
    supported: str
    not_supported: str
    not_supported_ar: str
    not_supported_en: str


class DictionaryEntryInput(BaseModel):
    """§17.4 — كل عمود يُوصَف، ووسم PII صريح لا مستنتج من الاسم."""

    column_name: str = Field(min_length=1, max_length=128)
    label_ar: str | None = None
    scale_type: str | None = Field(default=None, pattern="^(nominal|ordinal|interval|ratio)$")
    value_labels: dict[str, str] | None = None
    is_pii: bool = False


class DictionaryEntryResponse(BaseModel):
    id: uuid.UUID
    dataset_version_id: uuid.UUID
    column_name: str
    label_ar: str | None
    scale_type: str | None
    value_labels: dict[str, str] | None
    is_pii: bool


class DictionaryCoverageResponse(BaseModel):
    """التغطية تُعرض بوصفها نقصًا مسمّى لا نسبة مجردة."""

    dataset_version_id: uuid.UUID
    described_columns: int
    pii_columns: int
    entries: list[DictionaryEntryResponse]
    note: str


class ToolExportRequest(BaseModel):
    dataset_version_id: uuid.UUID
    run_id: uuid.UUID | None = None
    tool: str = Field(pattern="^(spss|smartpls|nvivo|python|r)$")
    export_format: str = Field(min_length=1, max_length=16)


class ToolExportResponse(BaseModel):
    """§18.5 — التصدير يحمل حدوده معه.

    `limitations` ليس حقلًا اختياريًّا: تصدير بصيغة مفتوحة إلى أداة مغلقة
    يفقد أشياء، وإخفاء ذلك يجعل المستخدم يظن أنه نقل نموذجه كاملًا.
    """

    id: uuid.UUID
    dataset_version_id: uuid.UUID
    run_id: uuid.UUID | None
    tool: str
    tool_label: str
    export_format: str
    limitations: str
    created_at: dt.datetime
