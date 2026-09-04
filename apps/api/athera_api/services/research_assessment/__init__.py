"""تقييم بحثٍ حقيقي بالعقل البحثي | Assessing a real project with the Research Brain.

حزمتان لا واحدة، والحدّ بينهما مقصود:

    snapshot.py   يقرأ صفوف بحثٍ قائم ويبني `Assessment` — ولا يحكم
    view.py       يشغّل القواعد ويترجم الحكم إلى خانات الباحث — ولا يقرأ قاعدة

فيبقى المحرّك في `athera_api/research_brain/` حتميًّا قابلًا للاختبار بلا
قاعدة بيانات، ويبقى القارئ قابلًا للفحص وحده. والخلطُ بينهما يجعل كل اختبار
قاعدةٍ علمية يحتاج PostgreSQL — وهو ما يُميت منصّة التقييم بعد شهرين.
"""
from .snapshot import (
    Contradiction,
    ProjectSnapshot,
    ReadNote,
    build_project_assessment,
)
from .view import (
    ADVISORY_NOTE_AR,
    ADVISORY_NOTE_EN,
    CATEGORY_LABELS,
    NO_SCORE_NOTE_AR,
    NO_SCORE_NOTE_EN,
    Item,
    ResearcherReport,
    assess,
    researcher_report,
)

__all__ = [
    "ADVISORY_NOTE_AR", "ADVISORY_NOTE_EN", "CATEGORY_LABELS", "Contradiction",
    "Item", "NO_SCORE_NOTE_AR", "NO_SCORE_NOTE_EN", "ProjectSnapshot", "ReadNote",
    "ResearcherReport", "assess", "build_project_assessment", "researcher_report",
]
