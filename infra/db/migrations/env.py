"""بيئة الترحيل | Alembic environment.

الترحيلات تعمل بدور المالك (athera_owner)، بينما التطبيق يعمل بدور
athera_app الذي لا يملك BYPASSRLS — هذا الفصل هو جوهر ADR-0002.
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# البيانات الوصفية لازمة لـ autogenerate وحده، لا لـ upgrade/downgrade.
# جعلها اختيارية يسمح بترحيل قاعدة في بيئة لا تُستورد فيها طبقة الـORM
# كاملة — وهي حالة تشغيلية واقعية لا التفاف على مشكلة.
try:
    from athera_api.models import Base  # noqa: E402

    _model_metadata = Base.metadata
except Exception as _exc:  # pragma: no cover
    print(f"[alembic] model metadata unavailable ({_exc.__class__.__name__}); autogenerate disabled")
    _model_metadata = None

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = _model_metadata

DATABASE_URL = os.getenv(
    "DATABASE_MIGRATION_URL",
    "postgresql+psycopg://athera_owner:athera_owner_pw@localhost:5432/athera",
)
# `%` يُفلَّت قبل التمرير: alembic يمرّر القيمة عبر ConfigParser الذي يقرأ
# `%` كبداية استيفاء. وكلمة مرور مُرمَّزة للرابط تحمل `%40` لأي `@` — وهو
# رمز شائع في كلمات المرور. تمريرها كما هي يُفشل الترحيل برسالة عن «صياغة
# استيفاء» لا تذكر قاعدة البيانات ولا الكلمة، فيضيع الوقت في المكان الخطأ.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
