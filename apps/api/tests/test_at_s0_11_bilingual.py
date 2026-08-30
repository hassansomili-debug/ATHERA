"""AT-S0-11 — ثنائية اللغة عربي/إنجليزي في كل طبقة (§26.4، §38.4).

المنتج ليس عربيًا بواجهة إنجليزية مترجمة، ولا العكس. هذا الاختبار يمنع
انحراف أي طبقة عن اللغتين معًا.
"""
import json
import pathlib

import pytest

from athera_api.i18n.catalog import CATALOG, SUPPORTED_LOCALES, negotiate_locale, translate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MESSAGES_DIR = REPO_ROOT / "apps" / "web" / "messages"


def test_every_api_message_exists_in_both_languages():
    incomplete = [
        key for key, entry in CATALOG.items()
        if not all(entry.get(locale, "").strip() for locale in SUPPORTED_LOCALES)
    ]
    assert not incomplete, f"API messages missing a translation: {incomplete}"


def test_arabic_messages_are_actually_arabic():
    """حارس ضد نسخ النص الإنجليزي في الخانة العربية."""
    suspicious = []
    for key, entry in CATALOG.items():
        arabic = entry["ar"]
        if not any("؀" <= ch <= "ۿ" for ch in arabic):
            suspicious.append(key)
    assert not suspicious, f"Arabic entries with no Arabic script: {suspicious}"


def test_locale_negotiation():
    assert negotiate_locale(None) == "ar"
    assert negotiate_locale("en-US,en;q=0.9") == "en"
    assert negotiate_locale("ar-SA,ar;q=0.9,en;q=0.8") == "ar"
    assert negotiate_locale("fr-FR") == "ar"  # يسقط إلى الافتراضي لا يفشل
    assert negotiate_locale("") == "ar"


def test_translate_falls_back_without_crashing():
    assert translate("auth.invalid_credentials", "en") == "Invalid credentials."
    assert "غير صحيحة" in translate("auth.invalid_credentials", "ar")
    assert translate("nonexistent.key", "ar") == "nonexistent.key"


def test_web_message_catalogs_have_identical_key_sets():
    if not MESSAGES_DIR.exists():
        pytest.skip("web messages not present")
    catalogs = {}
    for locale in SUPPORTED_LOCALES:
        path = MESSAGES_DIR / f"{locale}.json"
        assert path.exists(), f"missing web catalog: {path}"
        catalogs[locale] = json.loads(path.read_text(encoding="utf-8"))

    def flatten(node, prefix=""):
        keys = set()
        for key, value in node.items():
            full = f"{prefix}{key}"
            if isinstance(value, dict):
                keys |= flatten(value, f"{full}.")
            else:
                keys.add(full)
        return keys

    ar_keys, en_keys = flatten(catalogs["ar"]), flatten(catalogs["en"])
    assert ar_keys == en_keys, (
        f"web catalogs diverged — only in ar: {sorted(ar_keys - en_keys)}, "
        f"only in en: {sorted(en_keys - ar_keys)}"
    )


def test_bilingual_columns_exist_on_user_facing_models():
    """أي كائن يُعرض للمستخدم يحمل الاسم بلغتين."""
    from athera_api.models.audit import IntegrityAlert
    from athera_api.models.identity import Organization, Role, Tenant
    from athera_api.models.runs import Notification

    for model in (Tenant, Organization, Role, IntegrityAlert):
        columns = set(model.__table__.columns.keys())
        assert {"name_ar", "name_en"} <= columns, f"{model.__name__} is not bilingual"
    assert {"title_ar", "title_en", "body_ar", "body_en"} <= set(
        Notification.__table__.columns.keys()
    )


def test_error_envelope_carries_both_languages():
    from athera_api.i18n.catalog import all_translations

    payload = all_translations("authz.forbidden")
    assert set(payload) == set(SUPPORTED_LOCALES)
