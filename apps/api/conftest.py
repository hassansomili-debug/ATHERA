"""غلاف توافق اختياري لمفسّر أقدم | Opt-in compatibility shim for older interpreters.

المشروع يستهدف Python 3.12 (ADR-0001)، وهذا الملف **لا يغيّر ذلك**. غرضه
الوحيد أن يتمكن مطوّر على مفسّر أقدم من تشغيل الاختبارات الخالصة — تلك التي
لا تحتاج قاعدة بيانات — بدل الاكتفاء بقراءتها.

يُفعَّل بمتغير بيئة صريح فقط:

    ATHERA_COMPAT_PY39=1 pytest

بلا المتغير لا يفعل شيئًا إطلاقًا، فلا يمكن أن يخفي عيبًا في بيئة 3.12 ولا
في التكامل المستمر. وهو غلاف نحوي لا سلوكي: يسقط `slots=True` (3.10+) ويضيف
`datetime.UTC` (3.11+)، ولا يمس أي منطق.
"""
import os

if os.getenv("ATHERA_COMPAT_PY39") == "1":  # pragma: no cover - أداة تطوير محلية
    import dataclasses
    import datetime as _dt
    import sys

    if sys.version_info < (3, 10):
        _original_dataclass = dataclasses.dataclass

        def _dataclass_without_slots(cls=None, **kwargs):
            kwargs.pop("slots", None)
            if cls is not None:
                return _original_dataclass(cls, **kwargs)
            return _original_dataclass(**kwargs)

        dataclasses.dataclass = _dataclass_without_slots

    if not hasattr(_dt, "UTC"):
        _dt.UTC = _dt.timezone.utc
