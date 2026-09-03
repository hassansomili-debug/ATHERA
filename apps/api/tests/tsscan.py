"""مسحُ شيفرة الواجهة | Scanning frontend source.

**والتعليق يشرح ما أُزيل، فلا يُحاسَب عليه.** وحارسٌ يعاقب على شرحٍ صادق
يُعطَّل ثم لا يحرس شيئًا — وقد وقع ذلك مرّتين: حارسُ اسم المنتج وحارسُ
النطاق، كلاهما سقط على تعليقٍ يذكر ما مُنع.

فيُكتب الماسح مرّة واحدة هنا، ويقرؤه كل حارس — ولا نسختان تفترقان.
"""
from __future__ import annotations

from collections.abc import Iterator


def code_lines(text: str) -> Iterator[tuple[int, str]]:
    """(رقم السطر، ما فيه من شيفرة) — بلا تعليقات سطرية ولا كتلية."""
    in_block = False
    for number, line in enumerate(text.splitlines(), 1):
        rest, visible = line, ""
        while rest:
            if in_block:
                end = rest.find("*/")
                if end < 0:
                    rest = ""
                else:
                    rest, in_block = rest[end + 2:], False
            else:
                start = rest.find("/*")
                slash = rest.find("//")
                if slash >= 0 and (start < 0 or slash < start):
                    visible += rest[:slash]
                    rest = ""
                elif start >= 0:
                    visible += rest[:start]
                    rest, in_block = rest[start + 2:], True
                else:
                    visible += rest
                    rest = ""
        if visible.strip():
            yield number, visible


__all__ = ["code_lines"]
