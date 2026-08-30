"""ثنائية اللغة في طبقة الـAPI | Bilingual API messages.

القاعدة: الاستجابة تحمل دائمًا `code` قابلًا للقراءة آليًا، ونصًا مترجمًا حسب
Accept-Language، بالإضافة إلى النصين معًا في `messages` حتى يستطيع أي عميل
عرض اللغة التي يريدها دون رحلة إضافية (§26.4، §38.4).

Rule: every response carries a machine-readable `code`, a message negotiated from
Accept-Language, and both translations, so any client can render either language.
"""
from .catalog import CATALOG, negotiate_locale, translate

__all__ = ["CATALOG", "negotiate_locale", "translate"]
