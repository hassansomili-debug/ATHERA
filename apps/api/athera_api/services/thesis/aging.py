"""أعمار البيانات والأدبيات | Data and literature aging (§23.8).

قبل تحويل رسالة قديمة تنص §23.8 على حساب عمر البيانات وعمر الأدبيات
وإعادة تقييم الفجوة. الحساب هنا صريح ومعلن — لا حكم تلقائي بالرفض:
عمر البيانات معلومة يقررها الباحث والمحرر، لا المنصة.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

DAYS_PER_YEAR = 365.25


@dataclass(slots=True)
class AgingReport:
    data_age_years: float | None
    literature_age_years: float | None
    needs_literature_update: bool | None
    needs_reanalysis_review: bool | None
    note_ar: str
    note_en: str


def compute(
    *,
    as_of: dt.date,
    data_collected_on: dt.date | None,
    latest_cited_year: int | None,
    literature_update_threshold_years: float,
    data_age_review_threshold_years: float,
) -> AgingReport:
    """العتبات معاملات لا ثوابت — سياسة المجلة أو المؤسسة تحددها."""
    data_age = (
        round((as_of - data_collected_on).days / DAYS_PER_YEAR, 2)
        if data_collected_on else None
    )
    literature_age = (
        round(as_of.year - latest_cited_year + (as_of.timetuple().tm_yday / DAYS_PER_YEAR), 2)
        if latest_cited_year else None
    )

    needs_update = (
        literature_age >= literature_update_threshold_years
        if literature_age is not None else None
    )
    needs_review = (
        data_age >= data_age_review_threshold_years if data_age is not None else None
    )

    missing = [
        name for name, value in (("عمر البيانات", data_age), ("عمر الأدبيات", literature_age))
        if value is None
    ]
    if missing:
        note_ar = "تعذّر حساب: " + "، ".join(missing) + " — لا يُفترض أنها حديثة."
        note_en = "Could not compute: " + ", ".join(
            n for n, v in (("data age", data_age), ("literature age", literature_age)) if v is None
        ) + " — do not assume they are current."
    else:
        note_ar = "حُسب عمر البيانات والأدبيات؛ القرار في التحديث للباحث."
        note_en = "Data and literature ages computed; the update decision is the researcher's."

    return AgingReport(
        data_age_years=data_age,
        literature_age_years=literature_age,
        needs_literature_update=needs_update,
        needs_reanalysis_review=needs_review,
        note_ar=note_ar, note_en=note_en,
    )
