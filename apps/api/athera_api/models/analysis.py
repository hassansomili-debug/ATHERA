"""محرك التحليل | Analysis engine models (§17، §18، §31.6)."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..services.analysis.vocab import (  # noqa: F401 — إعادة تصدير مقصودة
    DATASET_STATES,
    INTERPRETATION_LAYERS,
    TEST_KINDS,
    TOOL_SUPPORT,
)
from .base import Base, TenantScoped, Timestamped, uuid_pk

__all__ = [
    "Dataset", "DatasetVersionRow", "DataDictionary", "AnalysisPlanRow", "PlannedTestRow",
    "AnalysisRun", "AnalysisOutputRow", "InterpretationRow", "ToolExport",
    "DATASET_STATES", "TEST_KINDS", "TOOL_SUPPORT", "INTERPRETATION_LAYERS",
]


class Dataset(Base, TenantScoped, Timestamped):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str] = mapped_column(String(4), nullable=False, default="C3")


class DatasetVersionRow(Base, TenantScoped, Timestamped):
    """§17.2 — RAW غير قابل للتعديل بمشغّل، والتجميد يمنحه معرّفًا (§17.3)."""

    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=True
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    frozen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freeze_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    frozen_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class DataDictionary(Base, TenantScoped, Timestamped):
    __tablename__ = "data_dictionaries"
    __table_args__ = (UniqueConstraint("dataset_version_id", "column_name",
                                       name="uq_data_dictionary_column"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(String(128), nullable=False)
    label_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variable_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("variables.id", ondelete="SET NULL"), nullable=True
    )
    scale_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    value_labels: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AnalysisPlanRow(Base, TenantScoped, Timestamped):
    """§9 G7 — الاعتماد يقفل القائمة بتجزئة ويسجّل فاعله."""

    __tablename__ = "analysis_plans"
    __table_args__ = (UniqueConstraint("project_id", "version_label",
                                       name="uq_analysis_plan_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    summary_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    lock_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlannedTestRow(Base, TenantScoped, Timestamped):
    __tablename__ = "planned_tests"
    __table_args__ = (UniqueConstraint("plan_id", "test_key", name="uq_planned_test_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("analysis_plans.id", ondelete="CASCADE"), nullable=False
    )
    test_key: Mapped[str] = mapped_column(String(64), nullable=False)
    test_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    variables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("thread_elements.id", ondelete="SET NULL"), nullable=True
    )
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnalysisRun(Base, TenantScoped, Timestamped):
    """§18.1 — «قابل لإعادة الإنتاج» وصف مكتسب ببيان كامل وبصمة."""

    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("analysis_plans.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_freeze_id: Mapped[str] = mapped_column(String(32), nullable=False)
    tool: Mapped[str] = mapped_column(String(16), nullable=False)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    runtime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    packages: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_reproducible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    missing_manifest_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    executed_test_keys: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    exploratory_test_keys: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    requires_disclosure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    network_egress: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnalysisOutputRow(Base, TenantScoped, Timestamped):
    """§39 — «النتائج غير المرتبطة بتحليل: صفر». `run_id` غير قابل للإفراغ."""

    __tablename__ = "analysis_outputs"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    output_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    test_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )


class InterpretationRow(Base, TenantScoped, Timestamped):
    """§18.3 — أربع طبقات لا تُدمج، وسلسلة سند مفروضة بقيود."""

    __tablename__ = "interpretations"
    __table_args__ = (UniqueConstraint("output_id", name="uq_interpretation_output"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    output_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("analysis_outputs.id", ondelete="CASCADE"), nullable=False
    )
    result_ar: Mapped[str] = mapped_column(Text, nullable=False)
    result_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    statistical_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    statistical_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    theoretical_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    theoretical_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    managerial_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    managerial_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolExport(Base, TenantScoped, Timestamped):
    """§18.2 / §47.9 — كل تصدير يحمل حدوده مكتوبة، لا مخفية."""

    __tablename__ = "tool_exports"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False
    )
    tool: Mapped[str] = mapped_column(String(16), nullable=False)
    export_format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    limitations_ar: Mapped[str] = mapped_column(Text, nullable=False)
    limitations_en: Mapped[str] = mapped_column(Text, nullable=False)
