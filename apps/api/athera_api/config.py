"""الإعدادات | Application settings — كل قيمة من البيئة، ولا أسرار في المستودع (§36.1)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_default_locale: str = "ar"
    app_supported_locales: str = "ar,en"

    database_url: str = "postgresql+asyncpg://athera_app:athera_app_pw@localhost:5432/athera"

    jwt_secret: str = "change-me"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1_209_600
    mfa_required_for_admin_roles: bool = True

    # مزوّد التخزين: `s3` لأي تخزين متوافق · `memory` للاختبار · `none` لمعطّل.
    # الاسم الوحيد الذي يُبدَّل عند الانتقال بين المزودين؛ الباقي عناوين ومفاتيح.
    storage_provider: str = "s3"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "athera-dev"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_presign_ttl_seconds: int = 300

    # §32 / ADR-0003 — Sprint 0 يعمل على "null" افتراضيًا: لا استدعاء إنتاجي لنموذج.
    model_provider: str = "null"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    # مفتاح Anthropic المرتبط بهوية يتطلب ترويسة `anthropic-workspace-id`.
    # اختياري: مفتاح مرتبط بمساحة عمل لا يحتاجه، ومفتاح الهوية يفشل بدونه
    # برسالة صريحة من المزوّد — فالإعداد يُصرَّح ولا يُخمَّن.
    anthropic_workspace_id: str = ""
    # اسم النموذج **إعدادٌ لا ثابت في الكود**. الافتراض الفارغ مقصود: مزوّد
    # بلا نموذج مُعلَن غير مُهيّأ، ولا يسقط إلى اسم مخبوء في مُحوّل — فترقية
    # نموذج تصير تغيير سرّ لا إعادة نشر، وخطأ إعداد يُعلَن ولا يُخمَّن.
    anthropic_model: str = ""
    # §36.3 — القيمة الافتراضية هي الأشد تقييدًا.
    model_external_send_max_classification: str = "C1"

    # §38.6.8 — النطاقات المسموح لها بمناداة الـAPI، مفصولة بفواصل.
    # الافتراض هو التطوير المحلي وحده: نشرٌ نُسي فيه ضبطها يفشل بوضوح في
    # المتصفح، ولا يفتح الـAPI لأي نطاق.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    @property
    def locales(self) -> list[str]:
        return [code.strip() for code in self.app_supported_locales.split(",") if code.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
