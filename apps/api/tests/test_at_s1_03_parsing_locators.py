"""AT-S1-03 — كل مقطع يحمل موضعًا قابلًا للاستشهاد (§33.1، §10.2)."""
import pytest

from athera_api.services.parsing import (
    MAX_CHUNK_CHARS,
    UnsupportedDocument,
    parse,
    parse_text,
)


def test_every_chunk_has_a_locator():
    data = (
        "السيرة الذاتية\n\n"
        "الاسم: باحث تجريبي في تخصص الإعلان والاتصال التسويقي بجامعة الإمام.\n\n"
        "الخبرات\n\n"
        "عمل الباحث على مشاريع في مجال الاتصال المؤسسي والعلاقات العامة لسنوات."
    ).encode("utf-8")
    chunks = parse_text(data)
    assert chunks
    for chunk in chunks:
        assert chunk.locator and chunk.locator.strip()
        assert "¶" in chunk.locator


def test_headings_become_section_paths():
    data = (
        "المقدمة\n\n"
        "هذا نص المقدمة الذي يشرح الإطار العام للدراسة وأهميتها بالتفصيل الكافي.\n\n"
        "المنهجية\n\n"
        "اعتمدت الدراسة على منهج كمي باستخدام الاستبانة وتحليل الانحدار المتعدد."
    ).encode("utf-8")
    chunks = parse_text(data)
    sections = {chunk.section_path for chunk in chunks}
    assert "المقدمة" in sections and "المنهجية" in sections


def test_long_paragraph_splits_on_sentence_boundaries():
    sentence = "هذه جملة كاملة عن منهجية البحث الكمي والتحليل الإحصائي المستخدم فيها. "
    data = (sentence * 60).encode("utf-8")
    chunks = parse_text(data)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= MAX_CHUNK_CHARS


def test_unsupported_type_fails_loudly_not_silently():
    with pytest.raises(UnsupportedDocument):
        parse(b"\x00\x01binary", "application/x-spss-sav", "data.sav")


def test_sequences_are_contiguous_and_unique():
    data = ("فقرة أولى تحتوي نصًا كافيًا للتجاوز عن الحد الأدنى للمقطع.\n\n"
            "فقرة ثانية تحتوي أيضًا نصًا كافيًا للتجاوز عن الحد الأدنى للمقطع.").encode("utf-8")
    chunks = parse_text(data)
    seqs = [chunk.seq for chunk in chunks]
    assert seqs == sorted(seqs) == list(range(1, len(seqs) + 1))


# ── اختبارا انحدار لخطأين وُجدا بالتشغيل الفعلي، لا بالمراجعة ──

def test_short_standalone_line_is_detected_as_a_heading():
    """عناوين السير الذاتية العربية («السيرة الذاتية»، «المهارات») لا تظهر في
    أي قائمة كلمات مغلقة. القاعدة البنيوية — سطر قصير وحده بلا علامة نهاية —
    هي ما يلتقطها. بدونها يفقد كل مقطع سياق قسمه.
    """
    data = (
        "السيرة الذاتية\n\n"
        "الرتبة الحالية: أستاذ مشارك في قسم الإعلان والاتصال التسويقي بجامعة الإمام.\n\n"
        "المهارات\n\n"
        "يجيد الباحث استخدام SPSS في تحليل بيانات الاستبانة الكمية بشكل موسّع."
    ).encode("utf-8")
    chunks = parse_text(data)
    sections = {chunk.section_path for chunk in chunks}
    assert "السيرة الذاتية" in sections
    assert "المهارات" in sections


def test_a_normal_short_sentence_is_not_mistaken_for_a_heading():
    """الحد الآخر من القاعدة نفسها.

    جملة تنتهي بعلامة نهاية ليست عنوانًا. وعبارة غير مدرجة في قائمة العناوين
    المعروفة تُعد عنوانًا فقط إذا وقفت وحدها في فقرتها — أما العناوين المعروفة
    بالاسم («المهارات»، «المقدمة») فتُلتقط في الحالتين، وهذا مقصود.
    """
    from athera_api.services.parsing import _is_heading

    assert not _is_heading("يستخدم الباحث برنامج SPSS.", is_whole_paragraph=True)
    assert _is_heading("الأدوات المستخدمة في الدراسة", is_whole_paragraph=True)
    assert not _is_heading("الأدوات المستخدمة في الدراسة", is_whole_paragraph=False)
    # عنوان معروف بالاسم — يبقى عنوانًا بلا شرط بنيوي.
    assert _is_heading("المهارات التحليلية", is_whole_paragraph=False)
