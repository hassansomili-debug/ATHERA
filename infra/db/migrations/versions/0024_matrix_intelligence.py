"""ذكاء مصفوفة الأدبيات وسعة الفرز | Matrix intelligence + screening scale (PUBRIVA).

**الملخّص مصدرٌ منسوب، لا نصٌّ يطفو.** كان الملخّص يُقرأ من `raw_metadata`
بلا اسمِ من أرسله ولا وقتِ إرساله؛ فإذا استخرجت منه المصفوفة عيّنةً ظهرت
القيمة ولا يُعرف من أين. وأسوأ من ذلك: فهرسان يرسلان ملخّصين مختلفين
للورقة نفسها — فيغلب أحدهما الآخر بصمت، ويقرأ الباحث نصف الحقيقة وحده.
فجدولُ `source_abstracts` يحفظ **كل** ملخّصٍ منسوبًا إلى فهرسه وبوقته
ومعرّفه عنده، والاختلاف يبقى ظاهرًا اختلافًا لا يُطوى.

**والصفحة والقسم لا يُخترعان.** الترحيل 0023 منع رقم صفحةٍ لملخّص؛ وهذا
يمدّ المنع إلى الاتجاه الآخر: عمودان مستقلّان لرقم الصفحة والقسم، وقيدٌ
يرفضهما إلا من نصٍّ كامل. ورقمُ الصفحة يأتي من تقطيعٍ قرأ صفحةً فعلًا
(`document_chunks.page_number`) — **ولا يُشتقّ من ترتيب المقطع أبدًا**:
المقطع السابع ليس الصفحة السابعة، والقارئ الذي يعود إليها لا يجد شيئًا.

**والفرز يُصفّى قبل أن يُصفَّح.** ألفُ مرجعٍ تُحمَّل دفعةً واحدة تُسقط
الشاشة؛ فالتصفية والعدّ يقعان في القاعدة، والفهارس هنا هي ما يجعل ذلك
ممكنًا — فهرسٌ لترتيب الصفحة، وفهارس للمرشّحات التي تُصفّى بها فعلًا:
السنة والفهرس ونوع الوثيقة ومفتاح التكرار.

Revision ID: 0024
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = ("source_abstracts",)

# **من أرسل هذا الملخّص.** قائمةٌ مغلقة كقائمة `sources.registry` نفسها،
# ومعها `researcher` — لأن الباحث الذي ينسخ ملخّصًا من الورقة التي بين
# يديه مصدرٌ يُسمّى كسائر المصادر، لا مجهولٌ يُخزَّن بلا نسبة.
ABSTRACT_PROVIDERS = ("crossref", "openalex", "offline", "upload", "researcher")

# **مفتاح التكرار المحتمل.** المعرّف الرقمي أولًا لأنه هوية؛ فإن غاب فعنوانٌ
# منزوعُ كل ما ليس حرفًا ولا رقمًا — فـ«الأثر: دراسة» و«الأثر — دراسة»
# ورقةٌ واحدة كُتب عنوانها مرّتين، ولا يُقال للباحث إنهما اثنتان.
DEDUP_KEY = (
    "coalesce(nullif(lower(btrim(doi)), ''), "
    "lower(regexp_replace(coalesce(title, ''), '[^[:alnum:]]+', '', 'g')))"
)


def upgrade() -> None:
    # ── ١. الملخّص مصدرٌ منسوب، ولا يُطوى ملخّصان في واحد ──
    op.create_table(
        "source_abstracts",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        # `CASCADE` هنا لا `RESTRICT`: الملخّص وصفٌ للمرجع لا كيانٌ مستقلّ
        # عنه، فذهابُ المرجع من المكتبة يُذهب وصفه معه ولا يترك يتيمًا.
        sa.Column("source_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        # معرّف الورقة عند ذلك الفهرس — به يُعاد الطلب ويُقابَل ما وصل.
        sa.Column("provider_identifier", sa.String(255), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        # بصمةٌ للنصّ: بها يُعرف أن ما وصل اليوم هو نفسه ما وصل أمس، فلا
        # يتراكم صفٌّ لكل قراءةٍ للفهرس نفسه.
        sa.Column("content_hash", sa.String(64), nullable=False),
        # **متى وصل.** ملخّصٌ بلا وقتٍ لا يُقارن بملخّصٍ آخر ولا يُعرف أيّهما
        # أحدث — والاختلاف بين فهرسين يُقرأ بالوقت قبل أن يُقرأ بالنصّ.
        sa.Column("retrieved_at", TS, nullable=False),
        sa.CheckConstraint(
            "provider IN (" + ", ".join(f"'{p}'" for p in ABSTRACT_PROVIDERS) + ")",
            name="provider"),
        # ملخّصٌ فارغ ليس ملخّصًا — هو صفٌّ يجعل «لا ملخّص» تبدو «ملخّصًا».
        sa.CheckConstraint("length(btrim(text)) > 0", name="abstract_has_words"),
        # **ولا يُطوى ملخّصان في واحد.** الوحدانية على (المرجع، الفهرس،
        # البصمة): فهرسٌ غيّر ملخّصه يكتب صفًّا ثانيًا يُقرأ اختلافًا، ولا
        # يمحو الأول. وفهرسان مختلفان صفّان دائمًا.
        sa.UniqueConstraint("source_id", "provider", "content_hash",
                            name="uq_source_abstract"),
    )
    op.create_index("ix_source_abstracts_source", "source_abstracts",
                    ["tenant_id", "source_id"])

    # ── ٢. الخلية تقول من أي ملخّصٍ قُرئت، وفي أي صفحةٍ وقسم ──
    #
    # **ولا واحدٌ منها يُخترع.** ثلاثة أعمدةٍ تُضاف فارغةً، وثلاثةُ قيودٍ
    # ترفض أن تُملأ من مدًى لا يحملها.
    op.add_column("literature_matrix_cells",
                  sa.Column("source_abstract_id", PgUUID(as_uuid=True),
                            sa.ForeignKey("source_abstracts.id", ondelete="SET NULL"),
                            nullable=True))
    op.add_column("literature_matrix_cells",
                  sa.Column("evidence_page", sa.Integer, nullable=True))
    op.add_column("literature_matrix_cells",
                  sa.Column("evidence_section", sa.Text, nullable=True))

    # خليةٌ تنسب نفسها إلى ملخّصٍ وهي تدّعي نصًّا كاملًا تنسب إلى غير مصدرها.
    op.create_check_constraint(
        "abstract_citation_needs_abstract_scope", "literature_matrix_cells",
        "source_abstract_id IS NULL OR source_scope = 'abstract_only'")
    # **رقمُ الصفحة من نصٍّ كامل وحده — ولا يُشتقّ من ترتيب مقطع.** والمقطع
    # السابع ليس الصفحة السابعة؛ ومن كتب ذلك أرسل القارئ إلى صفحةٍ لا تحمل
    # ما نُسب إليها. فالمجهول يبقى `NULL`، والصدق أولى من الاكتمال.
    op.create_check_constraint(
        "page_number_only_from_full_text", "literature_matrix_cells",
        "evidence_page IS NULL OR (source_scope = 'full_text' AND evidence_page > 0)")
    op.create_check_constraint(
        "section_only_from_full_text", "literature_matrix_cells",
        "evidence_section IS NULL OR source_scope = 'full_text'")

    # ── ٣. فهارس السعة: تُصفّى ألفُ مرجعٍ وتُعدّ بلا تحميلها ──
    #
    # ترتيبُ الصفحة هو (الأحدث أولًا، ثم المعرّف) — والفهرس بترتيب القراءة
    # نفسه، وإلا فرزَ الخادمُ الجدول كلّه ليعيد عشرين صفًّا.
    op.create_index("ix_project_sources_screening_page", "project_sources",
                    ["tenant_id", "project_id", "use_state",
                     sa.text("created_at DESC"), sa.text("id DESC")])
    # المرشّحات التي تُصفّى بها الشاشة فعلًا — لا فهارس على التخمين.
    op.create_index("ix_sources_screening_year", "sources",
                    ["tenant_id", "publication_year"])
    op.create_index("ix_sources_screening_registry", "sources",
                    ["tenant_id", "registry"])
    # نوعُ الوثيقة يعيش في بيانات الفهرس الخام (§33.3): يُقرأ ولا يُصدَّق،
    # ويُفهرس ليُصفّى به.
    op.execute("CREATE INDEX ix_sources_document_type ON sources "
               "(tenant_id, (raw_metadata->>'type'))")
    op.execute(f"CREATE INDEX ix_sources_dedup_key ON sources (tenant_id, ({DEDUP_KEY}))")

    # ── ٤. العزل: مفعَّل **ومفروض**، ومنحُ الدور صريح (ADR-0002) ──
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = app_current_tenant()) "
            "WITH CHECK (tenant_id = app_current_tenant())"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO athera_app")


def downgrade() -> None:
    """التنازل يرفض ولا يقطع خليةً عن الملخّص الذي قُرئت منه.

    قيمةٌ استخرجتها المنصّة من ملخّصٍ بعينه تُراجَع بمقابلتها بذلك الملخّص:
    يفتح الباحث النصّ، ويقرأ الجملة، ثم يعتمد أو يرفض. وإسقاطُ الجدول يترك
    القيمة قائمةً ومصدرَها غير موجود — فتبقى «تحتاج مراجعة» أبدًا، لأن ما
    تُراجَع به ذهب.

    فيُطلب القرار أولًا — كما في 0016 و0020 و0022 و0023.
    """
    bind = op.get_bind()

    cited = bind.execute(sa.text(
        "SELECT count(*) FROM literature_matrix_cells "
        "WHERE source_abstract_id IS NOT NULL"
    )).scalar_one()
    if cited:
        raise RuntimeError(
            f"downgrade refused: {cited} matrix cell(s) cite the abstract they were "
            "read from; dropping the table would leave values no one can check "
            "against their source. Review or clear them deliberately first. | "
            f"التنازل مرفوض: {cited} خليةً تنسب نفسها إلى ملخّصٍ محفوظ."
        )

    op.execute("DROP INDEX IF EXISTS ix_sources_dedup_key")
    op.execute("DROP INDEX IF EXISTS ix_sources_document_type")
    op.drop_index("ix_sources_screening_registry", table_name="sources")
    op.drop_index("ix_sources_screening_year", table_name="sources")
    op.drop_index("ix_project_sources_screening_page", table_name="project_sources")

    for constraint in ("section_only_from_full_text", "page_number_only_from_full_text",
                       "abstract_citation_needs_abstract_scope"):
        op.execute("ALTER TABLE literature_matrix_cells DROP CONSTRAINT "
                   f"ck_literature_matrix_cells_{constraint}")
    op.drop_column("literature_matrix_cells", "evidence_section")
    op.drop_column("literature_matrix_cells", "evidence_page")
    op.drop_column("literature_matrix_cells", "source_abstract_id")

    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_index("ix_source_abstracts_source", table_name="source_abstracts")
    op.drop_table("source_abstracts")
