"""مستخرِج حتمي | Deterministic rule-based extractor.

يعمل **بلا نموذج لغوي إطلاقًا**. وجوده ليس احتياطًا: هو ما يجعل خط أنابيب
الذاكرة الموثقة قابلًا للاختبار والتشغيل مع `MODEL_PROVIDER=null`، ويمنع
ارتهان أساس المنتج بمزود (§4 Provider Independent).

يغطي ما يمكن التقاطه بثقة من سيرة ذاتية عربية/إنجليزية: ORCID، الرتبة
الأكاديمية، المؤسسة، البرمجيات التحليلية، المناهج. وما لا يُلتقط بثقة
يُترك للمستخرِج النموذجي — لا يُخمَّن.
"""
from __future__ import annotations

import re

from ..parsing import ParsedChunk
from .base import Candidate, ExtractionResult, Extractor, enforce_grounding

_ORCID = re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b")

_RANKS = [
    ("أستاذ مشارك", "Associate Professor", "associate_professor"),
    ("أستاذ مساعد", "Assistant Professor", "assistant_professor"),
    ("أستاذ دكتور", "Professor", "professor"),
    ("محاضر", "Lecturer", "lecturer"),
    ("Associate Professor", "Associate Professor", "associate_professor"),
    ("Assistant Professor", "Assistant Professor", "assistant_professor"),
    ("Full Professor", "Professor", "professor"),
]

_SOFTWARE = [
    ("SPSS", "SPSS"), ("SmartPLS", "SmartPLS"), ("Smart PLS", "SmartPLS"),
    ("NVivo", "NVivo"), ("AMOS", "AMOS"), ("Stata", "Stata"), ("MAXQDA", "MAXQDA"),
    ("R Studio", "R"), ("RStudio", "R"), ("Python", "Python"),
]

_METHODS = [
    ("PLS-SEM", "PLS-SEM"), ("PLS SEM", "PLS-SEM"), ("SEM", "SEM"),
    ("تحليل موضوعي", "Thematic analysis"), ("Thematic Analysis", "Thematic analysis"),
    ("مقابلات شبه منظمة", "Semi-structured interviews"),
    ("Semi-structured interviews", "Semi-structured interviews"),
    ("استبانة", "Survey"), ("Survey", "Survey"),
    ("انحدار", "Regression"), ("Regression", "Regression"),
    ("Content Analysis", "Content analysis"), ("تحليل مضمون", "Content analysis"),
]


def _latin_token(token: str) -> re.Pattern[str]:
    r"""حدود آمنة لمصطلح لاتيني داخل نص عربي.

    `\b` يفشل هنا: في «وSmartPLS» تلتصق واو العطف بالكلمة اللاتينية، وكلاهما
    حرف كلمة، فلا حدّ بينهما. نستخدم بدلًا منه نفيًا للحروف اللاتينية والشرطة
    على الجانبين — فيلتقط «وSmartPLS» ولا يلتقط «SEM» من داخل «PLS-SEM».
    """
    return re.compile(rf"(?<![A-Za-z0-9\-]){re.escape(token)}(?![A-Za-z0-9\-])")


def _is_latin(token: str) -> bool:
    return all(ord(ch) < 128 for ch in token)


def _finditer(token: str, text: str):
    if _is_latin(token):
        return _latin_token(token).finditer(text)
    return re.finditer(re.escape(token), text)


def _window(text: str, match: re.Match[str], padding: int = 60) -> str:
    """اقتباس يحيط بالمطابقة — يبقى حرفيًا من النص الأصلي."""
    start = max(0, match.start() - padding)
    end = min(len(text), match.end() + padding)
    return text[start:end].strip()


class RuleBasedExtractor(Extractor):
    name = "rules"

    async def propose(self, chunks: list[ParsedChunk]) -> ExtractionResult:
        candidates: list[Candidate] = []
        seen: set[tuple[str, str]] = set()

        for chunk in chunks:
            text = chunk.text

            for match in _ORCID.finditer(text):
                key = ("orcid", match.group(1))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    Candidate(
                        memory_category="researcher_fact",
                        field_key="orcid",
                        statement_ar=f"معرّف ORCID للباحث: {match.group(1)}",
                        statement_en=f"Researcher ORCID: {match.group(1)}",
                        value={"orcid": match.group(1)},
                        quote=_window(text, match),
                        chunk_seq=chunk.seq,
                        confidence=0.95,  # نمط صارم، لكن يبقى مرشّحًا لا حقيقة.
                    )
                )

            for arabic, english, code in _RANKS:
                for match in _finditer(arabic, text):
                    key = ("rank", code)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        Candidate(
                            memory_category="researcher_fact",
                            field_key="current_rank",
                            statement_ar=f"الرتبة الأكاديمية المذكورة: {arabic}",
                            statement_en=f"Academic rank mentioned: {english}",
                            value={"rank": code},
                            quote=_window(text, match),
                            chunk_seq=chunk.seq,
                            confidence=0.6,  # قد تكون رتبة شخص آخر في نص السيرة.
                        )
                    )

            for token, canonical in _SOFTWARE:
                for match in _finditer(token, text):
                    key = ("software", canonical)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        Candidate(
                            memory_category="researcher_fact",
                            field_key="software",
                            statement_ar=f"برنامج تحليلي مذكور في المستند: {canonical}",
                            statement_en=f"Analytical software mentioned: {canonical}",
                            value={"skill_kind": "software", "name": canonical},
                            quote=_window(text, match),
                            chunk_seq=chunk.seq,
                            confidence=0.7,
                        )
                    )

            for token, canonical in _METHODS:
                for match in _finditer(token, text):
                    key = ("method", canonical)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        Candidate(
                            memory_category="researcher_fact",
                            field_key="method",
                            statement_ar=f"منهج أو أسلوب تحليل مذكور: {canonical}",
                            statement_en=f"Method or analysis technique mentioned: {canonical}",
                            value={"skill_kind": "method", "name": canonical},
                            quote=_window(text, match),
                            chunk_seq=chunk.seq,
                            confidence=0.6,
                        )
                    )

        by_seq = {chunk.seq: chunk for chunk in chunks}
        grounded, rejected = enforce_grounding(candidates, by_seq)
        return ExtractionResult(candidates=grounded, rejected_unquoted=rejected, extractor=self.name)
