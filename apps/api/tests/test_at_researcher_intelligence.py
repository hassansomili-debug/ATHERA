"""ذكاءُ الباحث — الصدقُ العلميّ والعزل | Researcher intelligence (Wave 2-A).

المرجع: `docs/wave2/researcher-intelligence-product-spec.md`.

ومقياسُ النجاح هنا مقلوبٌ كعادة المسارات العلميّة في هذا المنتج: لا يُقاس
بما تستطيع الطبقةُ قولَه، بل **بما ترفض أن تقوله**. فيُثبت هنا سبعة:

١) **الحالاتُ الخمس لا تُدمج اثنتان** — والمرشَّحُ لا يصير مؤكَّدًا إلّا
   بفعلِ إنسانٍ يُنسب إلى صاحبه ووقته. **ويُفحص في القاعدة**، لا في الموجّه:
   موجّهٌ يُكتب غدًا يعيد العطب، والقيدُ لا يُعاد كتابته.

٢) **الرفضُ لا يمسّ الملفَّ الفعّال بشيء** — وهو الفرقُ بين مراجعةٍ وبين
   استخراجٍ يكتب في ملفّ الباحث من وراء ظهره.

٣) **والصيغةُ الصحيحة ليست توثيقًا** — رقمُ ORCID سليمُ البنية يبقى
   `user_declared`. وهذا خلطٌ شائعٌ يُحرس هنا صراحةً، لأنّ ترقيتَه تعني
   ادّعاءَ ملكيّةٍ لا دليل عليها (§9).

٤) **ولا رقمَ يوهم يقينًا** — لا نسبةَ جاهزية ولا احتمالَ قَبول. والمنعُ
   بنيويّ: يُقرأ من مخطَّط OpenAPI نفسه، فلا يكفي ألّا يُكتب اليوم.

٥) **والمعتمَدُ لا يُعدَّل** — والتغييرُ يُنشئ إصدارًا، واللقطةُ تبقى.

٦) **وأربعُ لغاتٍ لا تُخلط** — ومَن بدّل لغةَ الشاشة لم يبدّل لغةَ مخطوطته.

٧) **والعزل** — مستأجرٌ لا يرى ملفَّ آخر ولا أهدافَه ولا قيودَه، و`FORCE`
   قائمةٌ على كلّ جدولٍ جديد، والدورُ لا يتجاوزها.
"""
from __future__ import annotations

import ast
import datetime as dt
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api" / "athera_api"
WEB = REPO / "apps" / "web"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0030_researcher_intelligence.py")

#: الجداولُ التي تُنشئها 0030 — كلُّها مملوكةٌ لمستأجر.
NEW_TABLES = (
    "researcher_profile_candidates",
    "researcher_goals",
    "researcher_constraints",
    "research_strategies",
    "project_strategy_assessments",
)

#: مصادرُ الموجة الثانية — تُفحص نصًّا وبنيةً.
WAVE2_SOURCES = (
    API / "models" / "researcher_intelligence.py",
    API / "schemas" / "researcher.py",
    API / "routers" / "researcher.py",
    API / "services" / "researcher" / "profile.py",
    API / "services" / "researcher" / "strategy.py",
    API / "services" / "researcher" / "orcid.py",
)

#: معرّفاتٌ تدلّ على يقينٍ لا نملكه (§5، §7). ممنوعةٌ في الشيفرة والعقد معًا.
FORBIDDEN_IDENTIFIERS = (
    "readiness",
    "probability",
    "success_score",
    "acceptance_score",
    "acceptance_chance",
    "confidence_score",
    "percent",
    "percentage",
)

#: معرّفاتٌ صحيحةٌ مسموحة رغم أنّها أعداد — والترتيبُ ليس قياسًا.
ALLOWED_INTEGER_FIELDS = ("strategy_version",)

# معرّفاتُ ORCID سليمةُ البنية فعلًا — خانةُ تدقيقها محسوبةٌ لا مخترعة.
VALID_ORCID_X = "0000-0002-1694-233X"   # خانةُ التدقيق `X` — الحالةُ التي
VALID_ORCID = "0000-0001-5109-3567"     # يسقط فيها كلُّ فحصٍ بـisdigit()
INVALID_CHECKSUM_ORCID = "0000-0002-1694-2331"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _migration_module():
    """الترحيلُ يُحمَّل وحدةً — فتُقرأ قوائمُه لا نصُّه وحده."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_migration_0030", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _code_without_comments(path: pathlib.Path) -> str:
    """الشيفرةُ بلا تعليقات — **والنصُّ يُخدع، والشجرُ لا.**

    وتعليقٌ يقول «ولا نسبةَ جاهزية» ليس نسبةَ جاهزية؛ ومسحُ النصّ الخامّ
    كان سيقرأ الحارسَ مخالفةً ويوقف المستودعَ على نفسه.
    """
    return ast.unparse(ast.parse(path.read_text(encoding="utf-8")))


# ═════════════ ١) الحالاتُ الخمس — ولا تُدمج اثنتان ═════════════

def test_the_five_states_exist_by_name_and_none_is_missing():
    """**أهمُّ سطرٍ في الوثيقة** (§2) — ويُقرأ من النموذج ومن الترحيل معًا."""
    from athera_api.models.researcher_intelligence import PROFILE_STATES

    expected = {"user_declared", "document_extracted", "confirmed",
                "externally_verified", "model_suggested"}
    assert set(PROFILE_STATES) == expected, "حالٌ من الخمس سقطت أو أُضيفت سادسة"
    assert len(PROFILE_STATES) == 5

    migration = _migration_text()
    for state in expected:
        assert f"'{state}'" in migration or f'"{state}"' in migration, (
            f"الحالُ {state} ليست في مفردات 0030 — فلا تحرسها القاعدة")


def test_two_states_are_never_inside_the_active_profile():
    """المستخرَجُ والمقترَحُ **لا يدخلان الملفَّ الفعّال** بحال (§2)."""
    from athera_api.models.researcher_intelligence import (
        STATES_OUTSIDE_THE_ACTIVE_PROFILE,
    )

    assert set(STATES_OUTSIDE_THE_ACTIVE_PROFILE) == {
        "document_extracted", "model_suggested"}


def test_the_database_and_not_the_router_binds_a_decision_to_its_owner():
    """**قرارٌ بلا صاحبٍ ووقتٍ لا يكون** — والقيدان مكتوبان في 0030.

    ولو كان الشرطُ في الموجّه وحده لأعاده أوّلُ موجّهٍ يُكتب بعده. وأربعُ
    نقاطٍ في هذا المستودع شُحنت بعطبٍ من هذا النوع من قبل.
    """
    migration = _migration_text()
    assert "(status = 'proposed') = (decided_by IS NULL)" in migration
    assert "(decided_by IS NULL) = (decided_at IS NULL)" in migration
    assert "(profile_state = 'confirmed') = (status = 'confirmed')" in migration


def test_no_router_writes_the_profile_except_through_a_confirmation():
    """**ولا يكتب مرشَّحٌ في الملفّ** — الكتابةُ فعلُ تأكيدٍ منفصل (§4).

    ويُقرأ من الشجر: لا `setattr` على ملفٍّ في الموجّه أصلًا، فالكتابةُ
    كلُّها تمرّ بالخدمة التي تُلزمها بقرارٍ منسوب.
    """
    tree = ast.parse((API / "routers" / "researcher.py").read_text(encoding="utf-8"))
    setattrs = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setattr"
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "profile"
    ]
    assert not setattrs, f"موجّهٌ يكتب في الملفّ رأسًا: أسطر {setattrs}"


# ═════════════ ٢) الصيغةُ الصحيحة ليست توثيقًا ═════════════

@pytest.mark.parametrize("value", [VALID_ORCID, VALID_ORCID_X,
                                   "https://orcid.org/" + VALID_ORCID,
                                   VALID_ORCID.replace("-", "")])
def test_a_well_formed_orcid_passes_the_format_check(value: str):
    from athera_api.services.researcher import orcid

    assert orcid.has_valid_format(value) is True


@pytest.mark.parametrize("value", [INVALID_CHECKSUM_ORCID, "0000-0002-1694",
                                   "abcd-efgh-ijkl-mnop", "", None,
                                   "0000-0002-1694-233Y"])
def test_a_malformed_orcid_fails_the_format_check(value):
    from athera_api.services.researcher import orcid

    assert orcid.has_valid_format(value) is False


def test_the_check_digit_handles_the_x_case():
    """خانةُ `X` هي عشرة — ومن فحص بـisdigit() وحدها رفض معرّفاتٍ صحيحة."""
    from athera_api.services.researcher import orcid

    assert orcid.checksum_digit("000000021694233") == "X"


def test_a_valid_format_never_becomes_verification():
    """**وهذا الفحصُ هو غرضُ §6 كلِّه.**

    رقمٌ يمرّ خانةَ التدقيق يثبت أنّه رقمُ ORCID صالحُ البنية، **ولا يثبت
    أنّ صاحبَ الحساب يملكه**. فأقصى ما يُقال عنه أنّ صاحبَه قاله.
    """
    from athera_api.services.researcher import orcid

    assert orcid.has_valid_format(VALID_ORCID_X) is True
    assert orcid.status_for_declared(VALID_ORCID_X) == "user_declared"
    assert orcid.status_for_declared(VALID_ORCID_X) != "externally_verified"
    assert orcid.status_for_declared(None) == "unverified"


def test_no_function_here_promises_verification_by_its_name():
    """ولا دالّةَ تُسمّى «تحقَّق» — الاسمُ نفسه كان سيكذب."""
    from athera_api.services.researcher import orcid

    exported = [name for name in dir(orcid) if not name.startswith("_")]
    assert not [n for n in exported if "verify" in n.lower()], (
        f"دالّةٌ تَعِد بتوثيقٍ لا يقع: {exported}")


def test_declaring_an_orcid_cannot_declare_its_verification_status():
    """**وحالُ التوثيق ليست مما يُصرَّح به.**

    ولو قبِلها العقدُ مُدخَلًا لكتب باحثٌ `externally_verified` عن نفسه —
    وهي الكذبةُ التي وُجد الحقلُ لمنعها.
    """
    from athera_api.schemas.researcher import ResearcherProfilePatch

    fields = set(ResearcherProfilePatch.model_fields)
    for forbidden in ("orcid_status", "orcid_verified_at", "orcid_source"):
        assert forbidden not in fields, f"{forbidden} يُقبل مُدخَلًا من الباحث"


# ═════════════ ٣) ولا رقمَ يوهم يقينًا ═════════════

def test_no_wave_two_contract_carries_a_certainty_number():
    """**المنعُ بنيويّ لا سلوكيّ** — يُقرأ من مخطَّط OpenAPI نفسه.

    ولا يكفي ألّا يُكتب رقمٌ اليوم: عقدٌ يسمح بنوعٍ عشريّ يُملأ غدًا في
    مراجعةٍ عابرة. فما لا يوجد له نوعٌ لا يُرسَل سهوًا.
    """
    from athera_api.main import app

    spec = app.openapi()
    components = spec["components"]["schemas"]

    # **العقودُ تُبلَغ من مساراتها لا من أسمائها.** والانتقاءُ بالاسم كان
    # يجرّ عقودَ الموجة الأولى — `FactCandidateResponse` وغيرَها — فيفشل
    # الحارسُ على شيفرةٍ ليست من هذه الموجة ولا يحرسها هذا الملفّ.
    def _refs(node) -> set[str]:
        if isinstance(node, dict):
            found = set()
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str):
                    found.add(value.rsplit("/", 1)[-1])
                else:
                    found |= _refs(value)
            return found
        if isinstance(node, list):
            return {name for item in node for name in _refs(item)}
        return set()

    reachable: set[str] = set()
    frontier = _refs({p: v for p, v in spec["paths"].items()
                      if p.startswith("/api/v1/researcher")})
    while frontier:
        name = frontier.pop()
        if name in reachable or name not in components:
            continue
        reachable.add(name)
        frontier |= _refs(components[name])

    # وغلافُ 422 من صنع FastAPI لا من صنع هذه الموجة، و`loc` فيه موضعُ
    # حقلٍ في الطلب — ترتيبٌ لا قياس، ومشتركٌ مع المنتج كلِّه.
    framework_envelopes = {"ValidationError", "HTTPValidationError"}
    researcher_schemas = {
        name: components[name] for name in reachable - framework_envelopes
    }
    assert researcher_schemas, "لم يُعثر على عقود الموجة في المخطَّط"

    offenders: list[str] = []
    for name, schema in researcher_schemas.items():
        for field, definition in (schema.get("properties") or {}).items():
            rendered = str(definition)
            if '"number"' in rendered or "'number'" in rendered:
                offenders.append(f"{name}.{field}: عددٌ عشريّ")
            if ("integer" in rendered and field not in ALLOWED_INTEGER_FIELDS):
                offenders.append(f"{name}.{field}: عددٌ صحيحٌ غيرُ مبرَّر")
            lowered = field.lower()
            for token in FORBIDDEN_IDENTIFIERS:
                if token in lowered:
                    offenders.append(f"{name}.{field}: يحمل «{token}»")

    assert not offenders, "عقدٌ يحمل رقمًا يوهم يقينًا: " + " · ".join(offenders)


def test_no_wave_two_source_names_a_readiness_or_a_probability():
    """ولا في الشيفرة أيضًا — والتعليقاتُ تُنزع قبل الفحص."""
    offenders: list[str] = []
    for path in WAVE2_SOURCES:
        code = _code_without_comments(path).lower()
        offenders += [f"{path.name}: {token}"
                      for token in FORBIDDEN_IDENTIFIERS if token in code]
    assert not offenders, "شيفرةٌ تسمّي يقينًا لا نملكه: " + " · ".join(offenders)


def test_no_wave_two_column_is_a_float_or_a_decimal():
    """**ولا عمودَ عائمًا** — فما لا يُخزَّن لا يُحسب ولا يُعرض."""
    from athera_api.models.base import Base

    offenders: list[str] = []
    for table_name in NEW_TABLES:
        table = Base.metadata.tables[table_name]
        for column in table.columns:
            kind = type(column.type).__name__.lower()
            if any(token in kind for token in ("float", "numeric", "decimal", "real")):
                offenders.append(f"{table_name}.{column.name}: {kind}")
    assert not offenders, "عمودٌ يحمل كسرًا: " + " · ".join(offenders)


def test_the_alignment_verdict_is_four_words_and_not_a_grade():
    """**ولا نسبة** — والحكمُ من أربعةٍ، و`unknown` جوابٌ مشروعٌ منها."""
    from athera_api.models.researcher_intelligence import ALIGNMENT_VERDICTS

    assert set(ALIGNMENT_VERDICTS) == {
        "aligns", "partially_aligns", "conflicts", "unknown"}


def test_the_strategy_always_says_what_it_does_not_know():
    """**والناقصُ يُقال دائمًا** (§7) — وتوصيةٌ تُخفي جهلَها أسوأ من صمت."""
    from athera_api.models.research import ResearcherProfile
    from athera_api.services.researcher import strategy

    bare = ResearcherProfile(orcid_status="unverified")
    missing = strategy.assemble_missing_information(bare, [], [])

    assert strategy.MISSING_NO_GOALS in missing
    assert strategy.MISSING_NO_CONSTRAINTS in missing
    assert strategy.MISSING_ORCID_UNVERIFIED in missing
    assert "profile.institution_ar" in missing


def test_an_absent_constraint_is_unknown_and_not_an_absence_of_limits():
    """**غيابُ القيد «غيرُ معروف»، لا «لا قيد»** (§4).

    والفرقُ ليس لفظيًّا: «لا قيد» يفتح لمحرّكٍ أن يوصي بما تمنعه ميزانيّةٌ
    لم يسألها أحد.
    """
    from athera_api.models.research import ResearcherProfile
    from athera_api.services.researcher import strategy

    missing = strategy.assemble_missing_information(
        ResearcherProfile(orcid_status="unverified"), [], [])
    assert strategy.MISSING_NO_CONSTRAINTS == "constraints.none"
    assert strategy.MISSING_NO_CONSTRAINTS in missing


# ═════════════ ٤) أربعُ لغاتٍ لا تُخلط ═════════════

def test_the_four_language_concepts_are_four_separate_columns():
    """**وتبديلُ لغة الواجهة لا يمسّ لغةَ المخطوطة** (§8).

    ودمجُها في عمودٍ واحد هو بعينه العطب: من قرأ الشاشةَ بالعربية قد يكتب
    ورقتَه بالإنجليزية، والخلطُ يغيّر هدفَ نشرٍ بضغطة زرّ.
    """
    from athera_api.models.base import Base

    columns = set(Base.metadata.tables["researcher_profiles"].columns.keys())
    for field in ("preferred_research_languages", "preferred_working_language",
                  "preferred_manuscript_language", "ai_response_language"):
        assert field in columns, f"{field} غيرُ موجود — المفاهيمُ مدموجة"


def test_the_ui_language_is_not_a_column_in_the_profile_at_all():
    """**ولغةُ الواجهة ليست في هذا الجدول أصلًا** — وهو أقوى ضمانٍ ممكن.

    فما لا يُخزَّن هنا لا يُبدَّل من هنا، ولا يستطيع مسارٌ أن يشتقّ لغةَ
    المخطوطة من ترويسة `Accept-Language`.
    """
    from athera_api.models.base import Base
    from athera_api.schemas.researcher import ResearcherProfilePatch

    columns = set(Base.metadata.tables["researcher_profiles"].columns.keys())
    for forbidden in ("ui_language", "interface_language", "locale", "display_language"):
        assert forbidden not in columns, f"لغةُ الواجهة تُخزَّن في الملفّ: {forbidden}"
        assert forbidden not in ResearcherProfilePatch.model_fields


def test_the_locale_header_never_reaches_a_profile_language_field():
    """ولا سطرَ في الخدمة يشتقّ لغةً من `principal.locale`."""
    code = _code_without_comments(API / "services" / "researcher" / "profile.py")
    assert "locale" not in code, "الخدمةُ تقرأ لغةَ الواجهة — والاشتقاقُ يبدأ هنا"


# ═════════════ ٥) شكلُ الترحيل — توسعةٌ محضة ═════════════

def test_the_migration_is_0030_on_0029_and_the_chain_has_one_head():
    source = _migration_text()
    assert re.search(r'^revision = "0030"', source, re.M)
    assert re.search(r'^down_revision = "0029"', source, re.M)

    versions = MIGRATION.parent
    downs = {
        re.search(r'^down_revision = "?([^"\n]+)"?', p.read_text(encoding="utf-8"), re.M).group(1)
        for p in versions.glob("0*.py")
    }
    revisions = {
        re.search(r'^revision = "([^"]+)"', p.read_text(encoding="utf-8"), re.M).group(1)
        for p in versions.glob("0*.py")
    }
    heads = revisions - downs
    assert heads == {"0030"}, f"السلسلةُ ليست برأسٍ واحد: {sorted(heads)}"


def test_the_migration_adds_no_not_null_column_without_a_server_default():
    """**نافذةُ النشر**: الخادمُ القديم يكتب في مخطَّطٍ لا يعرفه.

    وعمودٌ `NOT NULL` بلا قيمةٍ افتراضية على جدولٍ قائمٍ يُسقط كلَّ إدراجٍ
    من ذلك الخادم. فيُقرأ الشرطُ من الترحيل نفسه لا من نيّة كاتبه.
    """
    upgrade = _migration_text().split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]
    for block in re.findall(r"op\.add_column\((.*?)\n    \)", upgrade, re.S):
        if "nullable=False" in block:
            assert "server_default" in block, (
                "عمودٌ NOT NULL بلا قيمةٍ افتراضية على جدولٍ قائم — "
                f"النافذةُ تصير قاتلة:\n{block}")


def test_the_migration_touches_no_existing_table_but_the_profile():
    """ولا قيدَ يُفرض على جدولٍ يكتب فيه الخادمُ القديم — إلّا ما لا يعرفه."""
    upgrade = _migration_text().split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]

    altered = set(re.findall(r'op\.add_column\(\s*"([a-z_]+)"', upgrade))
    altered |= set(re.findall(r'op\.create_check_constraint\(\s*\n?\s*"[a-z_]+",\s*"([a-z_]+)"',
                              upgrade))
    assert altered <= {"researcher_profiles"}, (
        f"الترحيلُ يمسّ جداولَ قائمةً أخرى: {sorted(altered - {'researcher_profiles'})}")

    # والقيدان المفروضان على `researcher_profiles` يقعان على عمودين
    # **يُنشئهما هذا الترحيلُ نفسه**، فلا يكتبهما خادمٌ قديم ولا يخالفهما.
    for constraint_column in ("orcid_status", "orcid_verified_at", "orcid_source"):
        assert f'sa.Column("{constraint_column}"' in upgrade, (
            f"{constraint_column} مقيَّدٌ ولم يُنشأ هنا — قد يحمل قيمًا قديمة")


def test_every_new_table_enables_and_forces_row_level_security():
    """**و`FORCE` ليست تزيّدًا على `ENABLE`** — بدونها لا تسري على المالك."""
    upgrade = _migration_text()

    # الحلقةُ تكتب الأربعةَ لكلّ جدولٍ في `NEW_TABLES` — فيُفحص الأمران:
    # أنّ الأربعةَ مكتوبة، وأنّ القائمةَ التي تدور عليها هي الجداولُ كلُّها.
    for statement in ("ENABLE ROW LEVEL SECURITY",
                      "FORCE ROW LEVEL SECURITY",
                      "app_current_tenant()",
                      "GRANT SELECT, INSERT, UPDATE, DELETE"):
        assert statement in upgrade, f"الترحيلُ لا يُصدر: {statement}"

    guarded = _migration_module().NEW_TABLES
    assert set(guarded) == set(NEW_TABLES), (
        "قائمةُ الجداول المحروسة تخالف الجداولَ المُنشأة: "
        f"{set(NEW_TABLES).symmetric_difference(guarded)}")


def test_the_downgrade_refuses_to_erase_a_human_decision():
    """التنازلُ يرفض ولا يمحو قرارًا نسبه الباحثُ إلى نفسه."""
    downgrade = _migration_text().split("def downgrade()", 1)[1]
    assert "downgrade refused" in downgrade
    assert "decided_by IS NOT NULL" in downgrade
    assert "'approved', 'superseded'" in downgrade


def test_an_approved_strategy_is_frozen_by_a_trigger_not_by_a_convention():
    """**والمعتمَدُ لا يُعدَّل** — وقيدُ CHECK لا يكفي: لا يرى الصفَّ القديم."""
    upgrade = _migration_text()
    assert "CREATE TRIGGER research_strategies_approved_is_immutable" in upgrade
    assert "BEFORE UPDATE ON research_strategies" in upgrade
    assert "OLD.status = 'approved'" in upgrade
    assert "OLD.status = 'superseded'" in upgrade


# ═════════════ ٦) عبر HTTP، بقاعدةٍ حيّة ═════════════

def _client(slot):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=slot["user_id"], tenant_id=slot["tenant_id"],
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


async def _seed_candidate(slot, profile_id, *, field_name, value,
                          profile_state="document_extracted",
                          source_type="cv_upload",
                          extraction_method="deterministic"):
    """مرشَّحٌ بمفرداتٍ صحيحة — ولا قيمةَ مخترعةٌ خارج القائمة المغلقة."""
    from athera_api.db import tenant_session
    from athera_api.models.researcher_intelligence import ResearcherProfileCandidate

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        row = ResearcherProfileCandidate(
            tenant_id=slot["tenant_id"], profile_id=profile_id,
            field_name=field_name, candidate_value=value,
            source_type=source_type, extraction_method=extraction_method,
            provenance="سيرةٌ ذاتية — صفحة ١", profile_state=profile_state,
            status="proposed")
        session.add(row)
        await session.flush()
        return row.id


@requires_db
@pytest.mark.asyncio
async def test_a_researcher_creates_and_updates_their_own_profile(two_tenants):
    """(أ) الملفُّ يُنشأ عند أوّل قراءة، ويُحدَّث بما يكتبه صاحبُه."""
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            first = await http.get("/api/v1/researcher/profile")
            patched = await http.patch("/api/v1/researcher/profile", json={
                "institution_ar": "جامعةُ الملك سعود",
                "current_rank": "assistant_professor",
                "preferred_manuscript_language": "en",
            })
            again = await http.get("/api/v1/researcher/profile")
    finally:
        await engine.dispose()

    assert first.status_code == 200, first.text
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["institution_ar"] == "جامعةُ الملك سعود"
    assert body["preferred_manuscript_language"] == "en"
    assert again.json()["institution_ar"] == "جامعةُ الملك سعود"

    # وما كتبه بيده يُوسَم `user_declared` — لا `confirmed` ولا `verified`.
    provenance = again.json()["field_provenance"] or {}
    assert provenance["institution_ar"]["state"] == "user_declared"


@requires_db
@pytest.mark.asyncio
async def test_a_declared_orcid_is_never_recorded_as_verified(two_tenants):
    """(ك) عبر HTTP: رقمٌ صحيحُ البنية يبقى `user_declared`."""
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            good = await http.patch("/api/v1/researcher/profile",
                                    json={"orcid": VALID_ORCID_X})
            bad = await http.patch("/api/v1/researcher/profile",
                                   json={"orcid": INVALID_CHECKSUM_ORCID})
    finally:
        await engine.dispose()

    assert good.status_code == 200, good.text
    body = good.json()
    assert body["orcid"] == VALID_ORCID_X
    assert body["orcid_status"] == "user_declared"
    assert body["orcid_status"] != "externally_verified"
    assert body["orcid_verified_at"] is None
    assert body["orcid_source"] is None

    assert bad.status_code == 400, bad.text
    assert "orcid" in bad.json()["error"]["code"]


@requires_db
@pytest.mark.asyncio
async def test_a_candidate_cannot_become_confirmed_without_a_researcher(two_tenants):
    """(ج) **والقاعدةُ ترفض، لا الموجّه.**

    فتُحاول الترقيةُ بـSQL خامّ يتجاوز كلَّ شيفرةِ التطبيق — وهو بالضبط ما
    يفعله موجّهٌ يُكتب غدًا بلا انتباه.
    """
    import sqlalchemy.exc
    from sqlalchemy import text

    from athera_api.db import engine, tenant_session

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            profile_id = (await http.get("/api/v1/researcher/profile")).json()["id"]
        candidate_id = await _seed_candidate(
            a, uuid.UUID(profile_id), field_name="current_rank", value="professor")

        with pytest.raises(sqlalchemy.exc.IntegrityError) as caught:
            async with tenant_session(a["tenant_id"], a["user_id"]) as session:
                await session.execute(text(
                    "UPDATE researcher_profile_candidates "
                    "SET status = 'confirmed', profile_state = 'confirmed' "
                    "WHERE id = :cid"), {"cid": str(candidate_id)})
                await session.flush()

        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            after = (await session.execute(text(
                "SELECT status, profile_state FROM researcher_profile_candidates "
                "WHERE id = :cid"), {"cid": str(candidate_id)})).one()
    finally:
        await engine.dispose()

    assert "decision_has_an_actor" in str(caught.value), str(caught.value)[:300]
    assert after.status == "proposed", "المرشَّحُ تُرقّي نفسَه"
    assert after.profile_state == "document_extracted"


@requires_db
@pytest.mark.asyncio
async def test_confirming_records_the_actor_the_time_and_the_provenance(two_tenants):
    """(هـ) التأكيدُ فعلٌ منسوبٌ — والصفُّ نفسُه يحمل نسبته، لا سجلٌّ جانبيّ."""
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            profile = (await http.get("/api/v1/researcher/profile")).json()
            candidate_id = await _seed_candidate(
                a, uuid.UUID(profile["id"]),
                field_name="department_ar", value="قسمُ علوم الحاسب")

            before = await http.get("/api/v1/researcher/profile")
            confirmed = await http.post(
                f"/api/v1/researcher/profile/candidates/{candidate_id}/confirm",
                json={"reason": "راجعتُها في سيرتي وهي صحيحة"})
            after = await http.get("/api/v1/researcher/profile")
    finally:
        await engine.dispose()

    assert before.json()["department_ar"] is None, "القيمةُ دخلت الملفَّ قبل التأكيد"
    assert confirmed.status_code == 200, confirmed.text

    row = confirmed.json()
    assert row["status"] == "confirmed"
    assert row["profile_state"] == "confirmed"
    assert row["decided_by"] == str(a["user_id"]), "القرارُ بلا صاحب"
    assert row["decided_at"] is not None, "القرارُ بلا وقت"
    assert row["in_active_profile"] is True

    body = after.json()
    assert body["department_ar"] == "قسمُ علوم الحاسب"
    stamp = (body["field_provenance"] or {})["department_ar"]
    assert stamp["state"] == "confirmed"
    assert stamp["candidate_id"] == str(candidate_id)
    assert stamp["decided_by"] == str(a["user_id"])


@requires_db
@pytest.mark.asyncio
async def test_rejecting_a_candidate_leaves_the_confirmed_profile_untouched(two_tenants):
    """(د) **والرفضُ لا يمسّ الملفَّ الفعّال بشيء.**"""
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            await http.patch("/api/v1/researcher/profile",
                             json={"institution_ar": "جامعةُ الملك سعود"})
            profile = (await http.get("/api/v1/researcher/profile")).json()
            candidate_id = await _seed_candidate(
                a, uuid.UUID(profile["id"]),
                field_name="institution_ar", value="جامعةٌ أخرى لم يعمل بها قط",
                profile_state="model_suggested", source_type="model",
                extraction_method="model")

            rejected = await http.post(
                f"/api/v1/researcher/profile/candidates/{candidate_id}/reject",
                json={"reason": "لم أعمل في هذه الجامعة"})
            after = await http.get("/api/v1/researcher/profile")
    finally:
        await engine.dispose()

    assert rejected.status_code == 200, rejected.text
    row = rejected.json()
    assert row["status"] == "rejected"
    assert row["decided_by"] == str(a["user_id"])
    assert row["in_active_profile"] is False
    # وحالُ المنشأ تبقى مقروءةً — فيُعرف من أين جاء ما رُفض.
    assert row["profile_state"] == "model_suggested"

    assert after.json()["institution_ar"] == "جامعةُ الملك سعود", "الرفضُ بدّل الملفّ"


@requires_db
@pytest.mark.asyncio
async def test_a_manual_candidate_waits_for_its_own_author(two_tenants):
    """إدخالٌ يدويّ — **ويبقى خارج الملفّ حتى يؤكّده صاحبُه** (§3)."""
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            created = await http.post("/api/v1/researcher/profile/candidates", json={
                "field_name": "target_rank", "candidate_value": "associate_professor",
                "provenance": "أدخلتُها بيدي لأراجعها لاحقًا"})
            profile = await http.get("/api/v1/researcher/profile")
            listed = await http.get(
                "/api/v1/researcher/profile/candidates?candidate_status=proposed")
            unknown = await http.post("/api/v1/researcher/profile/candidates", json={
                "field_name": "tenant_id", "candidate_value": "x"})
    finally:
        await engine.dispose()

    assert created.status_code == 201, created.text
    assert created.json()["profile_state"] == "user_declared"
    assert created.json()["in_active_profile"] is False
    assert profile.json()["target_rank"] is None, "الإدخالُ اليدويّ دخل الملفَّ بلا تأكيد"
    assert len(listed.json()) == 1
    assert unknown.status_code == 400, "حقلٌ خارج القائمة المغلقة قُبل"


@requires_db
@pytest.mark.asyncio
async def test_a_decided_candidate_is_never_decided_twice(two_tenants):
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            profile = (await http.get("/api/v1/researcher/profile")).json()
            candidate_id = await _seed_candidate(
                a, uuid.UUID(profile["id"]), field_name="country", value="السعودية")
            first = await http.post(
                f"/api/v1/researcher/profile/candidates/{candidate_id}/confirm", json={})
            second = await http.post(
                f"/api/v1/researcher/profile/candidates/{candidate_id}/reject", json={})
    finally:
        await engine.dispose()

    assert first.status_code == 200, first.text
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "researcher.candidate_already_decided"


# ═════════════ ٧) الأهدافُ والقيود ═════════════

@requires_db
@pytest.mark.asyncio
async def test_goals_and_constraints_are_written_read_and_removed(two_tenants):
    """(و) والقيمةُ نصٌّ يقوله الباحث — لا رقمٌ تحسب عليه المنصّة."""
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            goal = await http.post("/api/v1/researcher/goals", json={
                "goal_type": "publication", "target": "ورقتان في مجلّةٍ محكَّمة",
                "priority": "high", "timeframe": "خلال سنة",
                "researcher_confirmed": True})
            constraint = await http.post("/api/v1/researcher/constraints", json={
                "constraint_type": "no_fee_preference",
                "value": "أفضّل مجلّاتٍ بلا رسوم نشر",
                "researcher_confirmed": True})
            goals = await http.get("/api/v1/researcher/goals")
            constraints = await http.get("/api/v1/researcher/constraints")
            patched = await http.patch(
                f"/api/v1/researcher/goals/{goal.json()['id']}",
                json={"status": "deferred"})
            removed = await http.delete(
                f"/api/v1/researcher/constraints/{constraint.json()['id']}")
            after = await http.get("/api/v1/researcher/constraints")
            invalid = await http.post("/api/v1/researcher/goals", json={
                "goal_type": "guaranteed_acceptance", "target": "x"})
    finally:
        await engine.dispose()

    assert goal.status_code == 201, goal.text
    assert constraint.status_code == 201, constraint.text
    assert len(goals.json()) == 1 and len(constraints.json()) == 1
    assert patched.json()["status"] == "deferred"
    assert removed.status_code == 204
    assert after.json() == []
    assert invalid.status_code == 422, "نوعُ هدفٍ مخترَعٌ قُبل"


@requires_db
@pytest.mark.asyncio
async def test_one_tenant_never_reads_another_tenants_researcher_record(two_tenants):
    """(ب) و(و) — العزلُ على الملفّ والمرشَّحات والأهداف والقيود معًا."""
    from athera_api.db import engine

    a, b = two_tenants["a"], two_tenants["b"]
    try:
        async with _client(a) as http:
            await http.patch("/api/v1/researcher/profile",
                             json={"institution_ar": "مؤسّسةُ المستأجر أ"})
            a_profile = (await http.get("/api/v1/researcher/profile")).json()
            a_goal = (await http.post("/api/v1/researcher/goals", json={
                "goal_type": "promotion", "target": "الترقية إلى أستاذٍ مشارك"})).json()
            a_constraint = (await http.post("/api/v1/researcher/constraints", json={
                "constraint_type": "time", "value": "يومان في الأسبوع"})).json()
            a_candidate = await _seed_candidate(
                a, uuid.UUID(a_profile["id"]), field_name="college_ar",
                value="كلّيةُ الحاسب")
            a_strategy = (await http.post("/api/v1/researcher/strategies",
                                          json={})).json()

        async with _client(b) as http:
            b_profile = await http.get("/api/v1/researcher/profile")
            b_goals = await http.get("/api/v1/researcher/goals")
            b_constraints = await http.get("/api/v1/researcher/constraints")
            b_candidates = await http.get("/api/v1/researcher/profile/candidates")
            b_strategies = await http.get("/api/v1/researcher/strategies")

            steal_goal = await http.patch(
                f"/api/v1/researcher/goals/{a_goal['id']}", json={"status": "achieved"})
            steal_constraint = await http.delete(
                f"/api/v1/researcher/constraints/{a_constraint['id']}")
            steal_candidate = await http.post(
                f"/api/v1/researcher/profile/candidates/{a_candidate}/confirm", json={})
            steal_strategy = await http.get(
                f"/api/v1/researcher/strategies/{a_strategy['id']}")
    finally:
        await engine.dispose()

    assert b_profile.status_code == 200
    assert b_profile.json()["id"] != a_profile["id"], "مستأجرانِ يتقاسمان ملفًّا"
    assert b_profile.json()["institution_ar"] is None
    assert "مؤسّسةُ المستأجر أ" not in b_profile.text

    assert b_goals.json() == [] and b_constraints.json() == []
    assert b_candidates.json() == [] and b_strategies.json() == []

    for stolen in (steal_goal, steal_constraint, steal_candidate, steal_strategy):
        assert stolen.status_code == 404, (
            f"مستأجرٌ لمس صفَّ غيره: {stolen.status_code} {stolen.text[:160]}")


# ═════════════ ٨) الاستراتيجيّة — والمعتمَدُ لا يُعدَّل ═════════════

@requires_db
@pytest.mark.asyncio
async def test_version_one_survives_version_two_unchanged(two_tenants):
    """(ز) و(ح) — واللقطةُ تبقى كما اتُّخذ عليها القرار.

    ولا يعني «لم يتغيّر» أنّ الصفَّ لم يُمسّ البتّة: حالُه تصير `superseded`
    ويُذكر خلفُه بالاسم. وما عدا ذلك — الرقمُ واللقطاتُ والتعليلُ ووقتُ
    الاعتماد وصاحبُه — يبقى حرفًا بحرف. **والقرارُ يُقرأ على حاله لا على
    حالٍ لاحقة.**
    """
    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            await http.patch("/api/v1/researcher/profile",
                             json={"institution_ar": "المؤسّسةُ الأولى"})
            await http.post("/api/v1/researcher/goals", json={
                "goal_type": "publication", "target": "هدفُ الإصدار الأوّل",
                "researcher_confirmed": True})

            first = (await http.post("/api/v1/researcher/strategies", json={
                "rationale_ar": "تعليلُ الإصدار الأوّل"})).json()
            approved = await http.post(
                f"/api/v1/researcher/strategies/{first['id']}/approve",
                json={"reason": "راجعتُها واعتمدتُها"})

            # وتتبدّل الحالُ بعد الاعتماد — وهو سببُ وجود اللقطات أصلًا.
            await http.patch("/api/v1/researcher/profile",
                             json={"institution_ar": "المؤسّسةُ الثانية"})
            second = (await http.post("/api/v1/researcher/strategies", json={
                "rationale_ar": "تعليلُ الإصدار الثاني"})).json()

            reread = (await http.get(
                f"/api/v1/researcher/strategies/{first['id']}")).json()
            listed = (await http.get("/api/v1/researcher/strategies")).json()
    finally:
        await engine.dispose()

    assert approved.status_code == 200, approved.text
    approved_body = approved.json()
    assert approved_body["status"] == "approved"
    assert approved_body["approved_by"] == str(a["user_id"])
    assert approved_body["approved_at"] is not None

    assert second["strategy_version"] == 2
    assert first["strategy_version"] == 1

    # **اللقطةُ لم تتحرّك** — وهي كلُّ المسألة.
    assert reread["profile_snapshot"]["institution_ar"] == "المؤسّسةُ الأولى"
    assert second["profile_snapshot"]["institution_ar"] == "المؤسّسةُ الثانية"
    assert reread["rationale_ar"] == "تعليلُ الإصدار الأوّل"
    assert reread["approved_at"] == approved_body["approved_at"]
    assert reread["approved_by"] == approved_body["approved_by"]
    assert reread["goals_snapshot"] == first["goals_snapshot"]

    # ولا يُمحى الأوّل ولا يُعدَّل — يُحال، ويذكر خلفَه بالاسم.
    assert reread["status"] == "superseded"
    assert reread["superseded_by"] == second["id"]
    assert {row["strategy_version"] for row in listed} == {1, 2}


@requires_db
@pytest.mark.asyncio
async def test_an_approved_strategy_cannot_be_silently_mutated(two_tenants):
    """(ح) **والقاعدةُ ترفض التعديلَ الصامت** — بـSQL خامّ يتجاوز التطبيق."""
    import sqlalchemy.exc
    from sqlalchemy import text

    from athera_api.db import engine, tenant_session

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            created = (await http.post("/api/v1/researcher/strategies", json={
                "rationale_ar": "التعليلُ كما اعتُمد"})).json()
            await http.post(
                f"/api/v1/researcher/strategies/{created['id']}/approve", json={})

        with pytest.raises(sqlalchemy.exc.DBAPIError) as caught:
            async with tenant_session(a["tenant_id"], a["user_id"]) as session:
                await session.execute(text(
                    "UPDATE research_strategies SET rationale_ar = 'نصٌّ بُدّل صامتًا' "
                    "WHERE id = :sid"), {"sid": created["id"]})
                await session.flush()

        async with _client(a) as http:
            after = (await http.get(
                f"/api/v1/researcher/strategies/{created['id']}")).json()
            reapprove = await http.post(
                f"/api/v1/researcher/strategies/{created['id']}/approve", json={})
    finally:
        await engine.dispose()

    assert "immutable" in str(caught.value), str(caught.value)[:300]
    assert after["rationale_ar"] == "التعليلُ كما اعتُمد", "المعتمَدُ بُدّل"
    assert reapprove.status_code == 400
    assert reapprove.json()["error"]["code"] == "researcher.strategy_not_approvable"


@requires_db
@pytest.mark.asyncio
async def test_no_researcher_response_carries_a_fractional_number(two_tenants):
    """(ط) و(ي) — **ولا رقمَ يوهم يقينًا** في جوابٍ حقيقيّ عبر HTTP.

    ولا يكفي فحصُ العقد: يُقرأ الجوابُ المرسَل نفسُه، ويُمشى في شجرته كلِّها.
    """
    import json as json_module

    from athera_api.db import engine

    a = two_tenants["a"]
    try:
        async with _client(a) as http:
            await http.post("/api/v1/researcher/goals", json={
                "goal_type": "publication", "target": "هدف", "researcher_confirmed": True})
            await http.post("/api/v1/researcher/constraints", json={
                "constraint_type": "publication_budget", "value": "بلا ميزانيّة"})
            strategy = await http.post("/api/v1/researcher/strategies", json={})
            bodies = {
                "profile": (await http.get("/api/v1/researcher/profile")).text,
                "goals": (await http.get("/api/v1/researcher/goals")).text,
                "constraints": (await http.get("/api/v1/researcher/constraints")).text,
                "strategies": (await http.get("/api/v1/researcher/strategies")).text,
                "strategy": strategy.text,
            }
    finally:
        await engine.dispose()

    def _floats(node, trail="") -> list[str]:
        if isinstance(node, float):
            return [trail]
        if isinstance(node, dict):
            return [x for k, v in node.items() for x in _floats(v, f"{trail}.{k}")]
        if isinstance(node, list):
            return [x for i, v in enumerate(node) for x in _floats(v, f"{trail}[{i}]")]
        return []

    for name, raw in bodies.items():
        assert _floats(json_module.loads(raw)) == [], f"{name} يحمل كسرًا عشريًّا"
        lowered = raw.lower()
        for token in FORBIDDEN_IDENTIFIERS:
            assert token not in lowered, f"{name} يحمل «{token}»"

    # **والناقصُ يُقال** في الجواب نفسه، لا في التوثيق وحده.
    assert strategy.json()["missing_information"], "استراتيجيّةٌ لا تقول ما تجهله"


@requires_db
@pytest.mark.asyncio
async def test_changing_the_response_language_never_changes_the_manuscript_language(
    two_tenants,
):
    """(ن) **وتبديلُ لغة الواجهة لا يمسّ لغةَ المخطوطة** (§8) — عبر HTTP.

    والطلبُ نفسُه يُعاد بترويسةٍ أخرى: من قرأ الشاشةَ بالعربية ثمّ
    بالإنجليزية يجب أن يجد هدفَ نشره كما تركه.
    """
    import httpx

    from athera_api.db import engine
    from athera_api.main import app
    from athera_api.security import issue_access_token

    a = two_tenants["a"]
    token = issue_access_token(user_id=a["user_id"], tenant_id=a["tenant_id"],
                               roles=["researcher"], mfa_satisfied=True)

    def client(locale: str):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})

    try:
        async with client("ar") as http:
            await http.patch("/api/v1/researcher/profile", json={
                "preferred_manuscript_language": "en",
                "preferred_working_language": "ar",
                "ai_response_language": "ar"})
            in_arabic = (await http.get("/api/v1/researcher/profile")).json()
        async with client("en") as http:
            in_english = (await http.get("/api/v1/researcher/profile")).json()
        async with client("ar") as http:
            back_in_arabic = (await http.get("/api/v1/researcher/profile")).json()
    finally:
        await engine.dispose()

    for body in (in_arabic, in_english, back_in_arabic):
        assert body["preferred_manuscript_language"] == "en", (
            "لغةُ المخطوطة تبدّلت بتبديل لغة الواجهة")
        assert body["preferred_working_language"] == "ar"
        assert body["ai_response_language"] == "ar"


# ═════════════ ٩) العزلُ في القاعدة نفسها ═════════════

@requires_db
@pytest.mark.asyncio
async def test_row_level_security_is_enabled_and_forced_on_every_new_table(db_ready):
    """(س) و`FORCE` مطلوبةٌ صراحةً — لا يكفي `ENABLE`."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = (await session.execute(text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(:names)"
        ), {"names": list(NEW_TABLES)})).all()

    seen = {row.relname: (row.relrowsecurity, row.relforcerowsecurity) for row in rows}
    assert set(seen) == set(NEW_TABLES), (
        f"جدولٌ جديد غيرُ موجود في القاعدة: {set(NEW_TABLES) - set(seen)}")
    for table, (enabled, forced) in seen.items():
        assert enabled, f"{table}: RLS غيرُ مفعَّلة"
        assert forced, f"{table}: RLS غيرُ مفروضة على المالك"


@requires_db
@pytest.mark.asyncio
async def test_every_new_table_carries_a_tenant_isolation_policy(db_ready):
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        policies = (await session.execute(text(
            "SELECT tablename, policyname FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = ANY(:names)"
        ), {"names": list(NEW_TABLES)})).all()

    by_table = {row.tablename for row in policies}
    assert by_table == set(NEW_TABLES), (
        f"جدولٌ بلا سياسةِ عزل: {set(NEW_TABLES) - by_table}")


@requires_db
@pytest.mark.asyncio
async def test_the_runtime_role_does_not_bypass_row_level_security(db_ready):
    """(ع) **وحادثةٌ حقيقيّة أوجدت هذا الفحص**: دورٌ يتجاوز أبطل طبقةً كاملة."""
    from athera_api.db import engine
    from athera_api.services import db_posture

    posture = await db_posture.inspect(engine)

    assert posture.bypasses_rls is False, (
        f"دورُ التشغيل يتجاوز العزل: {posture.detail()}")
    assert posture.is_superuser is False, f"دورُ التشغيل خارق: {posture.detail()}"
    assert posture.safe is True


@requires_db
@pytest.mark.asyncio
async def test_the_old_wave_one_server_can_still_write_the_profile_on_this_schema(
    db_ready,
):
    """**نافذةُ النشر** — الخادمُ القديم يكتب في مخطَّط 0030 ولا يسقط.

    ويُحاكى بـSQL خامٍّ يذكر **أعمدةَ الموجة الأولى وحدها**: لا نموذجَ
    موجةٍ ثانية في الطريق، لأنّه يحمل أعمدةً لم يكن ذلك الخادمُ يعرفها،
    فالكتابةُ به ليست كتابتَه.

    والمُثبَتُ شيئان: أنّ الإدراجَ يمرّ، وأنّ `orcid_status` يأخذ قيمتَه
    الافتراضية — فلا يخالف قيدَ المفردات وهو لا يعرفه أصلًا.
    """
    from sqlalchemy import text

    from athera_api.db import system_session
    from athera_api.models.identity import Tenant, User
    from athera_api.security import hash_password

    slug = f"win-{uuid.uuid4().hex[:8]}"
    async with system_session() as session:
        tenant = Tenant(slug=slug, name_ar="نافذة", name_en="Window")
        session.add(tenant)
        await session.flush()
        user = User(email=f"{slug}@example.test",
                    password_hash=hash_password("correct-horse-battery-staple"),
                    full_name_ar="باحثُ النافذة", full_name_en="Window researcher")
        session.add(user)
        await session.flush()
        tenant_id, user_id = tenant.id, user.id

        # **سياقُ المستأجر يُضبط في هذه المعاملة نفسها** — ولولاه لرشّحت
        # RLS كلَّ شيء، ومرّ الفحصُ على صفرِ صفوفٍ بلا خطأ ولا فائدة.
        await session.execute(text("SELECT set_config('app.tenant_id', :t, true)"),
                              {"t": str(tenant_id)})

        # كتابةُ الموجة الأولى حرفيًّا: الأعمدةُ التي كانت تعرفها وحدها.
        await session.execute(text(
            "INSERT INTO researcher_profiles "
            "(id, tenant_id, user_id, institution_ar, current_rank, orcid, "
            " created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :u, 'مؤسّسةٌ قديمة', 'lecturer', "
            "        '0000-0001-5109-3567', now(), now())"),
            {"t": str(tenant_id), "u": str(user_id)})

        # وتحديثُها كما كان `PATCH /api/v1/profile` يفعل — `orcid` وحده.
        await session.execute(text(
            "UPDATE researcher_profiles SET orcid = :o, updated_at = now() "
            "WHERE user_id = :u"),
            {"o": "0000-0002-1694-233X", "u": str(user_id)})

        row = (await session.execute(text(
            "SELECT orcid, orcid_status, orcid_verified_at, orcid_source "
            "FROM researcher_profiles WHERE user_id = :u"),
            {"u": str(user_id)})).one()

    assert row.orcid == "0000-0002-1694-233X", "كتابةُ الخادم القديم لم تقع"
    # **والخادمُ القديم لا يوثّق شيئًا** — القيمةُ الافتراضية تحرس المعنى.
    assert row.orcid_status == "unverified"
    assert row.orcid_verified_at is None and row.orcid_source is None
