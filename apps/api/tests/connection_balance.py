"""ميزانُ اتصالاتٍ على محرّك الاختبار | pool checkout/checkin balance.

**والمحرّكُ يُمرَّر ولا يُستورَد** — كما في `BackendWatch`: حارسُ الحزمة
(`test_no_test_disposes_the_global_application_engine`) يمنع ملفَّ اختبارٍ
من `from …db import engine`، والتطبيقُ مربوطٌ بمحرّك الاختبارات أصلًا؛
فاستيرادُ العامّ يراقب محرّكًا لا يعمل.

ولمَ يكفي هذا مع `NullPool`: الحادثان `checkout`/`checkin` يقعان في
الحالين — والمجمَّعُ المُعطَّل يُنشئ اتصالًا عند السحب ويُغلقه عند الإعادة.
فرصيدٌ غيرُ صفريٍّ بعد انتهاء العمل يعني **اتصالًا لا مالكَ له**: وهو
بعينه ما يُنهيه جامعُ المهملات بتحذير «اتصالٌ غير مُعاد».
"""
from __future__ import annotations

import gc


class ConnectionBalance:
    """يَعُدّ ما سُحب وما أُعيد — ويُبقي الفرقَ مقروءًا.

    ولا يُنظَر إلى العدد المطلق: العددُ يتأثّر بكلّ ما يجري في الحلقة.
    المقصودُ **الفرق**: `outstanding == 0` يعني أنّ كلَّ ما سُحب أُعيد.
    """

    def __init__(self, engine) -> None:
        self._engine = engine
        self.checked_out = 0
        self.checked_in = 0
        self._listeners: list[tuple[str, object]] = []

    @property
    def outstanding(self) -> int:
        return self.checked_out - self.checked_in

    def __enter__(self) -> ConnectionBalance:
        from sqlalchemy import event

        def _out(_dbapi_connection, _record, _proxy) -> None:
            self.checked_out += 1

        def _in(_dbapi_connection, _record) -> None:
            self.checked_in += 1

        for name, fn in (("checkout", _out), ("checkin", _in)):
            event.listen(self._engine.sync_engine, name, fn)
            self._listeners.append((name, fn))
        return self

    def __exit__(self, *_exc) -> bool:
        from sqlalchemy import event

        for name, fn in self._listeners:
            event.remove(self._engine.sync_engine, name, fn)
        self._listeners.clear()
        return False

    def settle(self) -> int:
        """يُجبر الجمعَ ثمّ يعيد الرصيد.

        **والجمعُ يُجبَر عمدًا**: بلا ذلك يُؤجَّل الإنهاءُ إلى فحصٍ لاحق،
        فيصير «نجاحُ» هذا الفحصِ تأجيلًا لا إصلاحًا — وهو بعينه ما جعل
        العطبَ يظهر في ملفٍّ بريء.
        """
        gc.collect()
        return self.outstanding
