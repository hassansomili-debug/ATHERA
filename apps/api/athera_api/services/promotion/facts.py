"""وقائع الحالة | Case facts fed to the calculator.

بنى محايدة تمامًا: لا تعرف جامعة ولا لائحة. الحاسبة تأخذ هذه الوقائع
وقواعد السياسة، ولا شيء غيرهما.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PublicationFact:
    publication_id: str
    title: str
    published_on: dt.date | None
    author_count: int
    author_position: int
    is_corresponding: bool
    is_refereed: bool
    is_thesis_derived: bool
    indexes: tuple[str, ...]
    journal_name: str | None
    verification_status: str

    @property
    def is_sole_author(self) -> bool:
        return self.author_count == 1

    @property
    def is_verified(self) -> bool:
        return self.verification_status == "verified"


@dataclass(frozen=True, slots=True)
class CaseFacts:
    """كل ما تعرفه الحاسبة عن الباحث. ما ليس هنا لا يُخمَّن."""

    as_of: dt.date
    rank_started_on: dt.date | None = None
    current_rank: str | None = None
    target_rank: str | None = None
    publications: tuple[PublicationFact, ...] = field(default_factory=tuple)
    # التدريس والخدمة نادرًا ما تكون في المنصة — غيابها يعني «يحتاج تحققًا».
    teaching_records: tuple[dict, ...] = field(default_factory=tuple)
    service_records: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def verified_publications(self) -> tuple[PublicationFact, ...]:
        return tuple(p for p in self.publications if p.is_verified)
