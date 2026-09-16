"""RC-T1-H2-A — **إعادةُ الطلب لا تُكرّر الطفرة** | retry-safe DB mutations.

## العطب، مقيسًا قبل الإصلاح

`RC-T1-H1` أغلق النجاحَ الكاذب. ولم يُغلق **الجوابَ الغامض**: أنّ الإيداعَ
وقع لا يعني أنّ العميلَ عَلِم. فقِيس على PostgreSQL حقيقيّة قبل هذه الدفعة:

    POST /api/v1/workspace/projects  ×٢ بجسمٍ واحد
    ⇒ http1=201 http2=201 · rows=2 · distinct_ids=2

بحثان من نيّةٍ واحدة.

## والحَكَمُ قاعدةٌ لا عمليّة

الصحّةُ قيدُ `uq_idempotency_scope`، لا قفلٌ في الذاكرة: الخوادمُ عدّة.
ولذلك **فحوصُ التزامن هنا على PostgreSQL حقيقيّة** — لا مُحاكاةٌ للإيداع.

## وما لا يُدَّعى

لا «مرّةً واحدةً بالضبط». الطور A يُغطّي الطفرات **الذرّيّة في القاعدة**
وحدها؛ ومساراتُ الانتظار الخارجيّ (`ai.ask`, `brain.ask`, الرفع، التفكيك)
تبقى بلا حماية حتى الطور B. والترويسةُ **اختياريّة**: طلبٌ بلا مفتاحٍ يسلك
مسلكَه القديم حرفيًّا.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from athera_api.services.idempotency import digest_key
from tests.test_at_rc_t1_h3_ai_long_transactions import _client, _observer

pytestmark = pytest.mark.asyncio

WORKSPACE = "/api/v1/workspace/projects"
PORTFOLIO = "/api/v1/portfolio/projects"
#: **والمسارُ `/api/v1/manuscripts`** لا `/api/v1/publishing/manuscripts`:
#: الموجّهُ مضمومٌ بسابقة `/api/v1` وحدها. والمعالجُ هو
#: `publishing.py::create_manuscript` كما هو مقصود.
MANUSCRIPTS = "/api/v1/manuscripts"


def _key(tag: str = "") -> str:
    """مفتاحٌ صالحُ الشكل — ٣٢ محرفًا ست عشريًّا."""
    return (uuid.uuid4().hex + tag)[:32]


async def _scalar(sql: str, params: dict):
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            return (await session.execute(text(sql), params)).scalar_one()
    finally:
        await engine.dispose()


async def _project_rows(tenant_id, title) -> int:
    return await _scalar(
        "SELECT count(*) FROM research_projects "
        "WHERE tenant_id = :t AND working_title_ar = :x",
        {"t": str(tenant_id), "x": title})


async def _records(tenant_id) -> int:
    return await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(tenant_id)})


# ═════════════ ١ · البصمة: معنًى لا بايتات ═════════════


def test_01_key_order_does_not_change_the_fingerprint() -> None:
    """`{"a":1,"b":2}` و`{"b":2,"a":1}` **طلبٌ واحد**.

    وترتيبُ مفاتيح JSON ليس معنًى، ويختلف بين عميلٍ وآخر. فلو بُصِمت
    البايتاتُ الخام لَرُدّ عميلٌ يُعيد طلبَه بتعارضٍ لا سبب له.
    """
    from athera_api.services.idempotency import canonical_fingerprint

    one = canonical_fingerprint(method="POST", operation="POST /x",
                                body={"a": 1, "b": 2})
    two = canonical_fingerprint(method="POST", operation="POST /x",
                                body={"b": 2, "a": 1})
    assert one == two, "ترتيبُ المفاتيح غيّر البصمة"

    nested_one = canonical_fingerprint(
        method="POST", operation="POST /x",
        body={"outer": {"z": 1, "a": [1, 2]}, "n": None})
    nested_two = canonical_fingerprint(
        method="POST", operation="POST /x",
        body={"n": None, "outer": {"a": [1, 2], "z": 1}})
    assert nested_one == nested_two, "التعميقُ كسر التطبيع"


def test_02_different_meaning_changes_the_fingerprint() -> None:
    """**والمعنى المختلفُ يختلف** — وإلّا لصار الحارسُ يجمع طلبَين مختلفين."""
    from athera_api.services.idempotency import canonical_fingerprint

    base = canonical_fingerprint(method="POST", operation="POST /x",
                                 body={"a": 1, "b": 2})
    assert base != canonical_fingerprint(
        method="POST", operation="POST /x", body={"a": 1, "b": 3}), "قيمةٌ"
    assert base != canonical_fingerprint(
        method="POST", operation="POST /y", body={"a": 1, "b": 2}), "عمليّة"
    assert base != canonical_fingerprint(
        method="PUT", operation="POST /x", body={"a": 1, "b": 2}), "فعل"
    # **وترتيبُ المصفوفة معنًى** بخلاف ترتيب المفاتيح.
    assert (canonical_fingerprint(method="POST", operation="POST /x",
                                  body={"a": [1, 2]})
            != canonical_fingerprint(method="POST", operation="POST /x",
                                     body={"a": [2, 1]})), "ترتيبُ مصفوفة"
    # ولا يُخلط الحقلُ الفارغُ بالحقل الغائب.
    assert (canonical_fingerprint(method="POST", operation="POST /x",
                                  body={"a": None})
            != canonical_fingerprint(method="POST", operation="POST /x",
                                     body={})), "فارغٌ ليس غائبًا"


def test_03_the_key_shape_is_enforced_and_the_raw_key_is_never_kept() -> None:
    """شكلُ المفتاح يُرفض مغلقًا، والمخزونُ بصمةٌ لا خام."""
    from athera_api.services.idempotency import (
        KeyInvalid, digest_key, validate_key,
    )

    assert validate_key(None) is None, "غيابُ الترويسة ليس خطأً"
    good = _key()
    assert validate_key(good) == good
    for bad in ("short", "", "x" * 129, "has space" + "x" * 20,
                "has/slash" + "x" * 20, "؟" * 20):
        with pytest.raises(KeyInvalid):
            validate_key(bad)

    digest = digest_key(good)
    assert len(digest) == 64 and digest == digest.lower()
    assert good not in digest


# ═════════════ ٢ · الدعوى الأساسيّة: طفرةٌ واحدة ═════════════


async def test_04_a_repeated_request_with_the_same_key_mutates_once(two_tenants):
    """**الجوابُ الغامض**: العميلُ لم يرَ الجوابَ فأعاد — فبحثٌ واحد.

    وهذه هي حالةُ «قبل» المقيسة، مقلوبةً: كانت `rows=2` فصارت `rows=1`.
    """
    slot = two_tenants["a"]
    title = f"h2a-{uuid.uuid4().hex[:10]}"
    body = {"title_ar": title, "starting_from": "idea"}
    key = _key()

    async with _client(slot) as http:
        first = await http.post(WORKSPACE, json=body,
                                headers={"Idempotency-Key": key})
        second = await http.post(WORKSPACE, json=body,
                                 headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert await _project_rows(slot["tenant_id"], title) == 1, (
        "وقعت الطفرةُ مرّتين")
    assert first.json()["id"] == second.json()["id"], (
        "أُعيد معرّفٌ مختلف — فالعميلُ أُعطي نسخةً لا أصلًا")
    assert first.json() == second.json(), "الجسمُ المُعاد ليس الأصل"
    # الأوّلُ تنفيذٌ فلا علامة، والثاني إعادةٌ فيُعلنها.
    assert "idempotency-replayed" not in {k.lower() for k in first.headers}
    assert second.headers.get("Idempotency-Replayed") == "true"


async def test_05_without_a_key_the_route_behaves_exactly_as_before(two_tenants):
    """**والترويسةُ اختياريّة**: بلا مفتاحٍ يبقى السلوكُ القديم حرفيًّا.

    وهذا شرطُ نشرٍ لا تفضيل: الإنتاجُ يعمل الآن بعملاءَ لا يرسلون مفتاحًا،
    واشتراطُه يكسرهم.
    """
    slot = two_tenants["a"]
    title = f"h2a-nokey-{uuid.uuid4().hex[:8]}"
    body = {"title_ar": title, "starting_from": "idea"}

    before = await _records(slot["tenant_id"])
    async with _client(slot) as http:
        first = await http.post(WORKSPACE, json=body)
        second = await http.post(WORKSPACE, json=body)

    assert first.status_code == 201 and second.status_code == 201
    assert await _project_rows(slot["tenant_id"], title) == 2, (
        "بلا مفتاحٍ يجب أن يبقى السلوكُ القديم — طفرتان")
    assert await _records(slot["tenant_id"]) == before, (
        "كُتب صفُّ تكرارٍ لطلبٍ بلا مفتاح")
    assert first.json()["id"] != second.json()["id"]


async def test_06_the_same_key_with_a_different_request_is_refused(two_tenants):
    """**مفتاحٌ واحدٌ لطلبَين مختلفَين ⇒ ٤٠٩**، ولا يُعاد جوابُ الأوّل.

    وإعادةُ جوابِ الأوّل كذبٌ: العميلُ طلب شيئًا آخر. وتنفيذُ الثاني تحت
    المفتاح نفسِه يجعل المفتاحَ بلا معنى.
    """
    slot = two_tenants["a"]
    key = _key()
    first_title = f"h2a-a-{uuid.uuid4().hex[:8]}"
    other_title = f"h2a-b-{uuid.uuid4().hex[:8]}"

    async with _client(slot) as http:
        first = await http.post(
            WORKSPACE, json={"title_ar": first_title, "starting_from": "idea"},
            headers={"Idempotency-Key": key})
        clash = await http.post(
            WORKSPACE, json={"title_ar": other_title, "starting_from": "idea"},
            headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert clash.status_code == 409, clash.text
    error = clash.json()["error"]
    assert error["code"] == "idempotency.key_reused", clash.text
    # **ورسالةٌ تُقرأ، لا مفتاحٌ يُعرض** — درسُ RC-T1-H3-B.
    assert error["messages"]["ar"] != error["code"]
    assert "التكرار" in error["messages"]["ar"], error["messages"]["ar"]
    assert "already used" in error["messages"]["en"], error["messages"]["en"]
    # ولا جسمَ الأوّل أُعيد، ولا الثاني نُفِّذ.
    assert "id" not in clash.json()
    assert await _project_rows(slot["tenant_id"], other_title) == 0


async def test_07_a_malformed_key_is_refused_before_anything_happens(two_tenants):
    """مفتاحٌ مشوَّهٌ ⇒ ٤٠٠ ولا طفرةَ ولا صفَّ تكرار."""
    slot = two_tenants["a"]
    title = f"h2a-bad-{uuid.uuid4().hex[:8]}"
    before = await _records(slot["tenant_id"])

    async with _client(slot) as http:
        response = await http.post(
            WORKSPACE, json={"title_ar": title, "starting_from": "idea"},
            headers={"Idempotency-Key": "too-short"})

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == "idempotency.key_invalid", response.text
    assert error["messages"]["ar"] != error["code"]
    assert "غيرُ صالح" in error["messages"]["ar"], error["messages"]["ar"]
    assert "not valid" in error["messages"]["en"], error["messages"]["en"]
    assert await _project_rows(slot["tenant_id"], title) == 0, "نُفِّذت الطفرة"
    assert await _records(slot["tenant_id"]) == before, "كُتب صفُّ تكرار"


# ═════════════ ٣ · التزامن — على PostgreSQL لا في الذاكرة ═════════════


async def test_08_two_concurrent_identical_requests_mutate_once(two_tenants):
    """**طلبان متزامنان بمفتاحٍ واحد ⇒ طفرةٌ واحدة**، والقاعدةُ هي الحَكَم.

    ولا قفلَ في العمليّة: الثاني يقف على مُدخَل الفهرس غير المُودَع حتى
    يُحسم الأوّل، ثمّ يقرأ جوابَه.
    """
    slot = two_tenants["a"]
    title = f"h2a-race-{uuid.uuid4().hex[:10]}"
    body = {"title_ar": title, "starting_from": "idea"}
    key = _key()

    async with _client(slot) as one, _client(slot) as two:
        responses = await asyncio.gather(
            one.post(WORKSPACE, json=body, headers={"Idempotency-Key": key}),
            two.post(WORKSPACE, json=body, headers={"Idempotency-Key": key}),
        )

    codes = sorted(r.status_code for r in responses)
    assert codes == [201, 201], [r.text for r in responses]
    assert await _project_rows(slot["tenant_id"], title) == 1, (
        "طلبان متزامنان أنشآ بحثَين")
    ids = {r.json()["id"] for r in responses}
    assert len(ids) == 1, f"معرّفان مختلفان: {ids}"
    replayed = [r.headers.get("Idempotency-Replayed") == "true" for r in responses]
    assert sum(replayed) == 1, (
        f"يُنتظر تنفيذٌ واحدٌ وإعادةٌ واحدة، ووُجد {replayed}")


async def test_09_five_concurrent_identical_requests_mutate_once(two_tenants):
    """وخمسةُ متزامنين كذلك — ولا ٥٠٠ ولا `IntegrityError` يتسرّب."""
    slot = two_tenants["a"]
    title = f"h2a-race5-{uuid.uuid4().hex[:10]}"
    body = {"title_ar": title, "starting_from": "idea"}
    key = _key()

    clients = [_client(slot) for _ in range(5)]
    opened = [await c.__aenter__() for c in clients]
    try:
        responses = await asyncio.gather(*[
            c.post(WORKSPACE, json=body, headers={"Idempotency-Key": key})
            for c in opened])
    finally:
        for c in clients:
            await c.__aexit__(None, None, None)

    assert all(r.status_code == 201 for r in responses), (
        [r.status_code for r in responses])
    assert await _project_rows(slot["tenant_id"], title) == 1
    assert len({r.json()["id"] for r in responses}) == 1
    assert await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t "
        "AND request_fingerprint IS NOT NULL AND state = 'completed' "
        "AND response_status = 201 AND response_body->>'id' = :i",
        {"t": str(slot["tenant_id"]), "i": responses[0].json()["id"]}) == 1


async def test_10_two_concurrent_requests_reusing_an_expired_key_mutate_once(
    two_tenants,
):
    """**واستعادةُ مفتاحٍ منتهٍ متزامنةً ⇒ طفرةٌ واحدة**.

    والفهرسُ يبقى يحمل المفتاحَ المنتهي حتى يُحذف، فلا يكفي تجاهلُه. فيُحذف
    ثمّ يُدرَج في المعاملة نفسِها، والقيدُ يبقى الحَكَم بين المتسابقين.
    """
    from sqlalchemy import text

    slot = two_tenants["a"]
    first_title = f"h2a-exp1-{uuid.uuid4().hex[:8]}"
    reuse_title = f"h2a-exp2-{uuid.uuid4().hex[:8]}"
    key = _key()

    async with _client(slot) as http:
        first = await http.post(
            WORKSPACE, json={"title_ar": first_title, "starting_from": "idea"},
            headers={"Idempotency-Key": key})
    assert first.status_code == 201, first.text

    # يُشيَّخ الصفُّ بحقوق المالك — ولا انتظارَ أربعًا وعشرين ساعة.
    engine, factory = await _observer()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "UPDATE idempotency_records SET expires_at = now() - interval '1 hour'"
                    " WHERE tenant_id = :t"), {"t": str(slot["tenant_id"])})
    finally:
        await engine.dispose()

    body = {"title_ar": reuse_title, "starting_from": "idea"}
    async with _client(slot) as one, _client(slot) as two:
        responses = await asyncio.gather(
            one.post(WORKSPACE, json=body, headers={"Idempotency-Key": key}),
            two.post(WORKSPACE, json=body, headers={"Idempotency-Key": key}),
        )

    assert all(r.status_code == 201 for r in responses), (
        [r.text for r in responses])
    assert await _project_rows(slot["tenant_id"], reuse_title) == 1, (
        "متسابقان على مفتاحٍ منتهٍ أنشآ بحثَين")
    assert len({r.json()["id"] for r in responses}) == 1


# ═════════════ ٤ · الذرّيّة: الصفُّ والطفرةُ معًا أو لا ═════════════


async def test_11_a_failed_mutation_leaves_no_idempotency_record(two_tenants):
    """**طفرةٌ أخفقت لا تُخلّف مفتاحًا مُكتمِلًا** — فلا مفتاحٌ يُسمَّم.

    و`/portfolio/projects` يشترط مِلفًّا تعريفيًّا ويرفض بدونه بـ٤٠٤. فهو
    إخفاقٌ بعد اكتساب الملكيّة — والمعاملةُ ترجع بالصفّ معها.
    """
    slot = two_tenants["b"]        # مستأجرٌ بلا مِلفٍّ تعريفيّ
    key = _key()
    before = await _records(slot["tenant_id"])

    async with _client(slot) as http:
        response = await http.post(
            PORTFOLIO, json={"working_title_ar": "بحثٌ بلا مِلفّ"},
            headers={"Idempotency-Key": key})

    assert response.status_code == 404, response.text
    assert await _records(slot["tenant_id"]) == before, (
        "بقي صفُّ تكرارٍ بعد طفرةٍ أخفقت — مفتاحٌ مُسمَّم")

    # وإعادةُ المحاولة بالمفتاح نفسِه ليست محجوبة.
    async with _client(slot) as http:
        again = await http.post(
            PORTFOLIO, json={"working_title_ar": "بحثٌ بلا مِلفّ"},
            headers={"Idempotency-Key": key})
    assert again.status_code == 404, again.text


async def test_12_no_committed_record_is_ever_observable_as_in_progress(
    two_tenants,
):
    """**ولا `in_progress` مُودَعٌ في الطور A** — الحجزُ والطفرةُ معاملةٌ واحدة."""
    slot = two_tenants["a"]
    title = f"h2a-state-{uuid.uuid4().hex[:8]}"

    async with _client(slot) as http:
        created = await http.post(
            WORKSPACE, json={"title_ar": title, "starting_from": "idea"},
            headers={"Idempotency-Key": _key()})
    assert created.status_code == 201, created.text

    states = await _scalar(
        "SELECT count(*) FROM idempotency_records "
        "WHERE tenant_id = :t AND state <> 'completed'",
        {"t": str(slot["tenant_id"])})
    assert states == 0, "صفٌّ مُودَعٌ بحالٍ غيرِ نهائيّة"
    assert await _scalar(
        "SELECT count(*) FROM idempotency_records "
        "WHERE tenant_id = :t AND completed_at IS NULL",
        {"t": str(slot["tenant_id"])}) == 0, "حالٌ نهائيّةٌ بلا زمنِ إتمام"


# ═════════════ ٥ · العزل: مستأجرٌ وفاعل ═════════════


async def test_13_the_same_key_in_two_tenants_is_independent(two_tenants):
    """مفتاحٌ واحدٌ في مستأجرَين ⇒ طفرتان مستقلّتان، ولا اصطدام."""
    key = _key()
    titles = {}
    for label in ("a", "b"):
        slot = two_tenants[label]
        titles[label] = f"h2a-iso-{label}-{uuid.uuid4().hex[:8]}"
        async with _client(slot) as http:
            response = await http.post(
                WORKSPACE, json={"title_ar": titles[label], "starting_from": "idea"},
                headers={"Idempotency-Key": key})
        assert response.status_code == 201, response.text
        assert response.headers.get("Idempotency-Replayed") is None, (
            "مفتاحُ مستأجرٍ آخر عُدَّ إعادةً")

    for label in ("a", "b"):
        assert await _project_rows(
            two_tenants[label]["tenant_id"], titles[label]) == 1


async def test_14_the_same_key_for_two_actors_in_one_tenant_is_independent(
    two_tenants,
):
    """**والفاعلُ حدٌّ ثانٍ**: الصفُّ يحمل جوابًا يُعاد، فلا يراه غيرُ صاحبه."""
    from athera_api.models.identity import User
    from athera_api.security import hash_password

    slot = two_tenants["a"]
    key = _key()

    # فاعلٌ ثانٍ في المستأجر نفسِه، بعضويّةٍ كعضويّة الأوّل.
    # **والدورُ يُقرأ باتصالٍ يرى الصفوف**: `roles` محميٌّ بـRLS، و
    # `system_session` بلا سياقِ مستأجرٍ ترى صفرًا. فيُقرأ المعرّفُ باتصال
    # المالك — قراءةٌ في تجهيزِ فحصٍ لا في مسارِ منتج.
    role_id = await _scalar(
        "SELECT id FROM roles WHERE tenant_id = :t AND key = 'researcher'",
        {"t": str(slot["tenant_id"])})

    # والعضويّةُ تُدسّ باتصال المالك كذلك: `memberships` محميٌّ بـRLS،
    # وتجهيزُ فاعلٍ ثانٍ ليس مسارَ منتجٍ يُفحص هنا.
    from sqlalchemy import text

    second_id = uuid.uuid4()
    engine, factory = await _observer()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "INSERT INTO users (id, email, password_hash, full_name_ar,"
                    " full_name_en) VALUES (:i, :e, :p, :a, :b)"),
                    {"i": str(second_id),
                     "e": f"h2a-{uuid.uuid4().hex[:10]}@example.com",
                     "p": hash_password("correct-horse-battery-staple"),
                     "a": "فاعلٌ ثانٍ", "b": "Second actor"})
                await session.execute(text(
                    "INSERT INTO memberships (id, tenant_id, user_id, role_id)"
                    " VALUES (:i, :t, :u, :r)"),
                    {"i": str(uuid.uuid4()), "t": str(slot["tenant_id"]),
                     "u": str(second_id), "r": str(role_id)})
    finally:
        await engine.dispose()
    other = {"tenant_id": slot["tenant_id"], "user_id": second_id}
    assert User is not None  # الاستيرادُ يُثبّت وجودَ النموذج المقصود

    first_title = f"h2a-act1-{uuid.uuid4().hex[:8]}"
    other_title = f"h2a-act2-{uuid.uuid4().hex[:8]}"
    async with _client(slot) as http:
        a = await http.post(WORKSPACE,
                            json={"title_ar": first_title, "starting_from": "idea"},
                            headers={"Idempotency-Key": key})
    async with _client(other) as http:
        b = await http.post(WORKSPACE,
                            json={"title_ar": other_title, "starting_from": "idea"},
                            headers={"Idempotency-Key": key})

    assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)
    # **ولا يُعاد جوابُ الأوّل للثاني** — وهو الخطرُ الذي يمنعه حدُّ الفاعل.
    assert b.headers.get("Idempotency-Replayed") is None
    assert a.json()["id"] != b.json()["id"], "أُعيد جوابُ فاعلٍ لفاعلٍ آخر"
    assert await _project_rows(slot["tenant_id"], first_title) == 1
    assert await _project_rows(slot["tenant_id"], other_title) == 1


async def test_15_rls_conceals_another_actors_record_and_refuses_to_write_it(
    two_tenants,
):
    """سياسةُ الصفّ: مستأجرٌ **وفاعل** — والجلسةُ بلا فاعلٍ لا ترى شيئًا.

    وتُفحص على PostgreSQL بدور التطبيق (`athera_app`) لا بدور المالك.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session_maker

    slot = two_tenants["a"]
    title = f"h2a-rls-{uuid.uuid4().hex[:8]}"
    async with _client(slot) as http:
        created = await http.post(
            WORKSPACE, json={"title_ar": title, "starting_from": "idea"},
            headers={"Idempotency-Key": _key()})
    assert created.status_code == 201, created.text

    # (أ) صاحبُ الصفّ يراه.
    async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as s:
        mine = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"))).scalar_one()
    assert mine >= 1, "صاحبُ الصفّ لا يراه"

    # (ب) فاعلٌ آخر في المستأجر نفسِه لا يراه.
    async with tenant_session_maker(slot["tenant_id"], uuid.uuid4())() as s:
        theirs = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"))).scalar_one()
    assert theirs == 0, "فاعلٌ آخر يرى صفَّ غيره — جوابٌ مخزونٌ مكشوف"

    # (ج) ولا يُعدّله ولا يحذفه.
    async with tenant_session_maker(slot["tenant_id"], uuid.uuid4())() as s:
        deleted = (await s.execute(text(
            "DELETE FROM idempotency_records RETURNING id"))).rowcount
    assert deleted in (0, -1), "فاعلٌ آخر حذف صفًّا ليس له"

    # (د) وجلسةٌ بلا فاعلٍ تفشل مغلقةً — `app_current_actor()` تُعيد NULL.
    async with tenant_session_maker(slot["tenant_id"], None)() as s:
        blind = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"))).scalar_one()
    assert blind == 0, "جلسةٌ بلا فاعلٍ رأت صفوفًا"

    # (هـ) والمخزونُ بصمةٌ لا مفتاحٌ خام.
    async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as s:
        digests = (await s.execute(text(
            "SELECT key_digest FROM idempotency_records"))).scalars().all()
    assert all(len(d) == 64 and d == d.lower() for d in digests), digests


# ═════════════ ٦ · التفويضُ يعلو على الجواب المخزون ═════════════


async def test_16_a_replay_never_bypasses_current_authorization(two_tenants):
    """**والتفويضُ الحاليُّ يعلو على جوابٍ مخزون** — وهذه الدعوى الأمنيّة.

    باحثٌ أنشأ مخطوطةً في بحثٍ يملك فيه التحرير، ثمّ سُحبت صلاحيّتُه، ثمّ
    أعاد الطلبَ بالمفتاح نفسِه. فلا يُعاد له الجسمُ المخزون: يُردّ بجواب
    التفويض الحاليّ.

    وهذا هو سببُ أن يكون الحارسُ **بعد** `ensure_project_access` لا قبله،
    وسببُ ألّا يكون وسيطًا عامًّا يبحث في الجدول قبل أن يوجد تفويضٌ أصلًا.
    """
    from sqlalchemy import text

    slot = two_tenants["a"]
    key = _key()

    # **والبحثُ يُنشأ بالمسار الحقيقيّ**: الملكيّةُ تُشتقّ من فاعلِ حدثِ
    # الإنشاء في سجلّ التدقيق (`collaboration.owner_user_id`)، فبحثٌ يُدسّ
    # في القاعدة بلا ذلك لا مالكَ له ولا يفتحه أحد.
    async with _client(slot) as http:
        project = await http.post(
            WORKSPACE, json={"title_ar": f"بحثٌ للتفويض {uuid.uuid4().hex[:6]}",
                             "starting_from": "idea"})
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]

        body = {"project_id": project_id, "title_ar": "مخطوطةٌ أولى",
                "language": "ar"}
        created = await http.post(MANUSCRIPTS, json=body,
                                  headers={"Idempotency-Key": key})
    assert created.status_code == 201, created.text
    manuscript_id = created.json()["id"]

    # تُسحب الصلاحيةُ: يُحذف البحثُ نفسُه، فيصير التفويضُ معدومًا.
    # **والسحبُ يحترم بنيةَ المخطَّط**: `manuscripts.project_id` غيرُ فارغ،
    # فلا يُفرَّغ. يُحذف أثرُ المخطوطة ثمّ البحث — فيصير التفويضُ معدومًا.
    engine, factory = await _observer()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "DELETE FROM manuscripts WHERE id = :m"), {"m": manuscript_id})
                await session.execute(text(
                    "DELETE FROM research_projects WHERE id = :p"),
                    {"p": str(project_id)})
    finally:
        await engine.dispose()

    # **والصفُّ باقٍ** — وهذا هو بيتُ القصيد: الجوابُ مخزونٌ وموجود، ومع
    # ذلك لا يُعاد، لأنّ التفويضَ يُفحص قبله.
    assert await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t"
        " AND state = 'completed'", {"t": str(slot["tenant_id"])}) >= 1

    async with _client(slot) as http:
        retried = await http.post(MANUSCRIPTS, json=body,
                                  headers={"Idempotency-Key": key})

    assert retried.status_code == 404, (
        "أُعيد جوابٌ مخزونٌ بعد سحب التفويض — التفافٌ على الصلاحية: "
        f"HTTP {retried.status_code}: {retried.text[:200]}")
    assert retried.json()["error"]["code"] == "publishing.project_not_found", (
        retried.text)
    assert retried.headers.get("Idempotency-Replayed") is None


# ═════════════ ٧ · التنظيف المحدود ═════════════


async def test_17_cleanup_is_bounded_and_never_required_for_correctness(
    two_tenants,
):
    """التنظيفُ محدودٌ بمئة، **ولا تتّكل الصحّةُ عليه**."""
    from athera_api.services.idempotency import CLEANUP_LIMIT, bounded_cleanup

    assert CLEANUP_LIMIT == 100, CLEANUP_LIMIT

    from athera_api.db import tenant_session_maker

    slot = two_tenants["a"]
    async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as s:
        removed = await bounded_cleanup(s, tenant_id=slot["tenant_id"])
    assert removed >= 0

    import inspect

    source = inspect.getsource(bounded_cleanup)
    assert ".limit(" in source, "التنظيفُ غيرُ محدود"
    assert "tenant_id" in source, "التنظيفُ غيرُ مقيَّدٍ بمستأجر"


# ═════════════ ٨ · النطاق: ما لم يُحمَ بعد ═════════════


def test_18_only_the_four_declared_routes_are_protected_in_phase_a() -> None:
    """**والطور A أربعةٌ لا أكثر** — ولا مسارٌ خارجيٌّ يُحمى بعد.

    فمساراتُ الانتظار الخارجيّ تحتاج حجزًا وإجارةً (الطور B)، ودمجُها هنا
    يعني إمّا معاملةً عبر الشبكة — وذاك ينقض RC-T1-H3 — أو حجزًا مُودَعًا
    لا يُنهيه أحد.
    """
    import ast
    import pathlib

    expected = {
        ("workspace.py", "create_project"),
        ("portfolio.py", "create_project"),
        ("analysis.py", "create_run"),
        ("publishing.py", "create_manuscript"),
    }
    forbidden = {"ai.py", "brain.py", "files.py", "profile.py", "thesis.py",
                 "literature.py", "manuscript_drafting.py", "planning.py"}

    found = set()
    routers = pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"
    for path in sorted(routers.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr == "begin" \
                        and getattr(node.func.value, "id", "") == "idempotency":
                    found.add((path.name, fn.name))

    assert found == expected, f"المحميّ اليوم: {sorted(found)}"
    assert not {f for f, _ in found} & forbidden, (
        "مسارٌ من الطور B حُمي في الطور A")


# ═════════════ ٩ · المساراتُ الأربعة، كلٌّ ببرهانه على HTTP ═════════════
#
# **والبرهانُ البنيويُّ لا يكفي بوّابةَ دمج.** `test_18` يُثبت أنّ أربعةَ
# معالجاتٍ تنادي `idempotency.begin`، ولا يُثبت أنّ أيًّا منها **يتصرّف**
# كما يجب: قد يُنادى الحارسُ ثمّ يُهمَل جوابُه، وقد يُوضع في موضعٍ لا
# تبلغه الطفرة. فيُطرق كلُّ بابٍ بطلبٍ حقيقيّ على PostgreSQL حقيقيّة.


async def _profile_for(slot) -> uuid.UUID:
    """مِلفٌّ تعريفيٌّ — شرطُ `/portfolio/projects` قبل أن يُنشئ بحثًا."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherProfile

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        found = (await session.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.user_id == slot["user_id"]))).scalar_one_or_none()
        if found is not None:
            return found.id
        profile = ResearcherProfile(
            tenant_id=slot["tenant_id"], user_id=slot["user_id"],
            institution_ar="جامعةُ الفحص", primary_field_ar="منهجيّاتُ البحث")
        session.add(profile)
        await session.flush()
        return profile.id


async def _completed_records(tenant_id, operation) -> int:
    """صفوفٌ مُكتمِلةٌ لعمليّةٍ بعينها — لا لكلّ الجدول."""
    return await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE tenant_id = :t AND operation = :o AND state = 'completed'",
        {"t": str(tenant_id), "o": operation})


async def test_19_portfolio_creation_replays_and_refuses_a_different_body(
    two_tenants,
):
    """**محفظةُ الأبحاث**: إعادةٌ واحدةٌ لا بحثان، ثمّ تعارضٌ يُردّ.

    و`/portfolio/projects` مسارٌ آخرُ يكتب **الجدولَ نفسَه**
    (`research_projects`) بشروطٍ أخرى — فبرهانُ `workspace` لا ينوب عنه.
    """
    slot = two_tenants["a"]
    await _profile_for(slot)
    title = f"h2a-pf-{uuid.uuid4().hex[:10]}"
    body = {"working_title_ar": title}
    key = _key()
    operation = f"POST {PORTFOLIO}"
    before = await _completed_records(slot["tenant_id"], operation)

    async with _client(slot) as http:
        first = await http.post(PORTFOLIO, json=body,
                                headers={"Idempotency-Key": key})
        second = await http.post(PORTFOLIO, json=body,
                                 headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert await _project_rows(slot["tenant_id"], title) == 1, "بحثان من نيّةٍ واحدة"
    assert first.json()["id"] == second.json()["id"], "أُعيد معرّفٌ مختلف"
    assert first.json() == second.json(), "الجسمُ المُعاد ليس الأصل"
    assert "idempotency-replayed" not in {k.lower() for k in first.headers}
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert await _completed_records(slot["tenant_id"], operation) == before + 1, (
        "عددُ الصفوف المُكتمِلة لهذه العمليّة ليس واحدًا")

    # وبصمةُ الصفّ بصمةُ الطلب الأوّل، ولا أثرَ للمفتاح الخام فيه.
    stored = await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE tenant_id = :t AND operation = :o AND response_status = 201"
        "   AND response_body->>'id' = :i",
        {"t": str(slot["tenant_id"]), "o": operation, "i": first.json()["id"]})
    assert stored == 1, "الجوابُ المخزون لا يُطابق ما رآه العميل"

    # والمفتاحُ نفسُه بجسمٍ مختلفٍ يُردّ — على هذا المسار كما على غيره.
    async with _client(slot) as http:
        clash = await http.post(
            PORTFOLIO, json={"working_title_ar": f"{title}-other"},
            headers={"Idempotency-Key": key})
    assert clash.status_code == 409, clash.text
    assert clash.json()["error"]["code"] == "idempotency.key_reused", clash.text
    assert await _project_rows(slot["tenant_id"], f"{title}-other") == 0, (
        "نُفِّذ الطلبُ المتعارض")


async def _runnable(owner_slot, actor_slot, project_id):
    """خطّةٌ مقفولةٌ ونسخةٌ مجمّدة — شرطا تشغيلةٍ تُقبل، بالمسارات الحقيقيّة.

    ولا يُدسّ صفٌّ في القاعدة: التجميدُ والاعتمادُ بوّابتان علميّتان
    (§17.3، §9 G7)، وتشغيلةٌ تُبنى على صفوفٍ مدسوسةٍ تُثبت غيرَ ما نريد.
    """
    async with _client(actor_slot) as http:
        created = await http.post("/api/v1/analysis/datasets", json={
            "project_id": str(project_id), "name_ar": "بياناتُ التكرار",
            "classification": "C3", "raw_label": "الرفع الأول",
            "raw_checksum": "a" * 64, "row_count": 50})
        assert created.status_code == 201, created.text
        dataset_id = created.json()["dataset_id"]
        raw_version = created.json()["id"]

        derived = await http.post(
            f"/api/v1/analysis/datasets/{dataset_id}/versions", json={
                "parent_version_id": raw_version, "state": "cleaned",
                "label": "منقّاة", "checksum": "d" * 64,
                "change_note_ar": "تنقية", "row_count": 48})
        assert derived.status_code == 201, derived.text
        version_id = derived.json()["id"]

        frozen = await http.post(
            f"/api/v1/analysis/datasets/versions/{version_id}/freeze")
        assert frozen.status_code == 200, frozen.text

        plan = await http.post("/api/v1/analysis/plans", json={
            "project_id": str(project_id), "version_label": "v1",
            "summary_ar": "خطّةُ التكرار",
            "tests": [{"test_key": "pearson_r", "test_kind": "correlation",
                       "note_ar": "علاقةٌ مُفترضة"}]})
        assert plan.status_code == 201, plan.text
        plan_id = plan.json()["id"]

    # **والاعتمادُ صلاحيةٌ أخرى** (`approve_scientific_candidates`) لا
    # يوسّعها `manage_data` — فيقفل الخطّةَ صاحبُ البحث.
    async with _client(owner_slot) as http:
        approved = await http.post(f"/api/v1/analysis/plans/{plan_id}/approve")
        assert approved.status_code == 200, approved.text

    return {"plan_id": plan_id, "dataset_version_id": version_id,
            "tool": "python", "executed_test_keys": ["pearson_r"],
            "code_hash": "e" * 64, "runtime": "3.12", "random_seed": 7}


async def _runs_for(plan_id) -> int:
    return await _scalar(
        "SELECT count(*) FROM analysis_runs WHERE plan_id = :p", {"p": str(plan_id)})


async def test_20_an_analysis_run_replays_without_running_twice(two_tenants):
    """**تشغيلةُ تحليلٍ واحدةٌ لا اثنتان** — والمسارُ يملك معاملتَه في متنه.

    وهذا المسارُ أصعبُ الأربعة: الحارسُ يقع **داخل** `_scope_pair`، على
    جلسةٍ ليست جلسةَ الطلب ومستأجرٍ قد لا يكون مستأجرَ الرمز. فبرهانُه
    يجب أن يكون سلوكيًّا لا بنيويًّا.
    """
    from tests.test_at_rc_t1a_project_access import _owned_project

    slot = two_tenants["a"]
    project_id = await _owned_project(slot, title="بحثُ تشغيلةِ التكرار")
    body = await _runnable(slot, slot, project_id)
    key = _key()

    async with _client(slot) as http:
        first = await http.post("/api/v1/analysis/runs", json=body,
                                headers={"Idempotency-Key": key})
        second = await http.post("/api/v1/analysis/runs", json=body,
                                 headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert await _runs_for(body["plan_id"]) == 1, "شُغّلت الخطّةُ مرّتين"
    assert first.json()["id"] == second.json()["id"], "أُعيد معرّفُ تشغيلةٍ أخرى"
    assert first.json() == second.json(), "الجسمُ المُعاد ليس الأصل"
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert "idempotency-replayed" not in {k.lower() for k in first.headers}
    assert await _completed_records(
        slot["tenant_id"], "POST /api/v1/analysis/runs") >= 1


async def test_21_two_concurrent_analysis_runs_execute_once(two_tenants):
    """**وتزامنُ تشغيلتين بمفتاحٍ واحد ⇒ تشغيلةٌ واحدة** — ولا ٥٠٠.

    والتزامنُ هنا يمسّ ما لا يمسّه `workspace`: جلسةُ النطاق تُودِع عند
    خروجها هي، لا `TransactionalRoute`. فلو تسرّب `IntegrityError` من
    القيد لَظهر ٥٠٠ بدل إعادةٍ صادقة.
    """
    from tests.test_at_rc_t1a_project_access import _owned_project

    slot = two_tenants["a"]
    project_id = await _owned_project(slot, title="بحثُ التزامن التحليليّ")
    body = await _runnable(slot, slot, project_id)
    key = _key()

    async with _client(slot) as one, _client(slot) as two:
        responses = await asyncio.gather(
            one.post("/api/v1/analysis/runs", json=body,
                     headers={"Idempotency-Key": key}),
            two.post("/api/v1/analysis/runs", json=body,
                     headers={"Idempotency-Key": key}),
        )

    assert all(r.status_code == 201 for r in responses), (
        [f"{r.status_code}: {r.text[:200]}" for r in responses])
    assert await _runs_for(body["plan_id"]) == 1, "متسابقان شغّلا الخطّةَ مرّتين"
    assert len({r.json()["id"] for r in responses}) == 1, "معرّفان لتشغيلةٍ واحدة"
    # **تنفيذٌ واحدٌ وإعادةٌ واحدةٌ بالضبط** — لا اثنان ولا صفر.
    replays = [r for r in responses
               if r.headers.get("Idempotency-Replayed") == "true"]
    assert len(replays) == 1, (
        f"عددُ الإعاداتِ {len(replays)} — يُنتظر واحدة بالضبط")
    assert await _completed_records(
        slot["tenant_id"], "POST /api/v1/analysis/runs") == 1


async def test_22_a_cross_tenant_collaborator_gets_the_effective_tenant(
    two_tenants,
):
    """**والصفُّ يُكتب حيث تقع الطفرة** — في مستأجر البحث لا مستأجر الرمز.

    وهذا هو الحدُّ الذي لا يُرى إن لم يُقَس. فمسارُ التشغيلة يمرّ بـ
    `_scope_pair` ← `project_session` ← `scoped_tenant`، والجلسةُ تنتقل
    إلى مستأجر البحث. فلو كُتب صفُّ التكرار بـ`principal.tenant_id`
    — مستأجرِ الضيف — لَخالف الصفُّ سياستَه هو: الجلسةُ في مستأجرٍ
    والصفُّ في آخر، فلا يُقرأ ولا يُعاد، **وتقع الطفرةُ مرّتين بصمت**.

    والفاعلُ يبقى الضيفَ نفسَه: المستأجرُ وحده يتبدّل.
    """
    from tests.test_at_rc_t1a_project_access import _owned_project
    from tests.test_at_rc_t1c_project_bridge import _external_member

    owner = two_tenants["a"]
    guest = two_tenants["b"]
    project_id = await _owned_project(owner, title="بحثٌ يتعاون عليه غريب")
    await _external_member(owner, guest, project_id,
                           permissions=["view_project", "manage_data"])

    body = await _runnable(owner, guest, project_id)
    key = _key()

    async with _client(guest) as http:
        first = await http.post("/api/v1/analysis/runs", json=body,
                                headers={"Idempotency-Key": key})
        second = await http.post("/api/v1/analysis/runs", json=body,
                                 headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert await _runs_for(body["plan_id"]) == 1, "شُغّلت الخطّةُ مرّتين"
    assert first.json()["id"] == second.json()["id"]

    # ══ الدعوى بعينها: المستأجرُ مستأجرُ البحث، والفاعلُ الضيف ══
    rows = await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE operation = 'POST /api/v1/analysis/runs'"
        "   AND tenant_id = :owner AND actor_user_id = :guest",
        {"owner": str(owner["tenant_id"]), "guest": str(guest["user_id"])})
    assert rows == 1, "الصفُّ ليس في مستأجر البحث بفاعل الضيف"

    stray = await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE operation = 'POST /api/v1/analysis/runs'"
        "   AND tenant_id = :guest_home",
        {"guest_home": str(guest["tenant_id"])})
    assert stray == 0, (
        "كُتب صفُّ التكرار في مستأجر الضيف — صفٌّ لا تقرؤه جلسةُ الطفرة")

    # ══ وRLS لا تُخترق بالعبور ══
    from athera_api.db import tenant_session_maker

    from sqlalchemy import text

    # الضيفُ في مستأجر البحث يرى صفَّه هو.
    async with tenant_session_maker(owner["tenant_id"], guest["user_id"])() as s:
        mine = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"
            " WHERE operation = 'POST /api/v1/analysis/runs'"))).scalar_one()
    assert mine == 1, "الضيفُ لا يرى صفَّه في مستأجر البحث"

    # وصاحبُ البحث نفسُه لا يراه — الفاعلُ حدٌّ ثانٍ ولو اتّحد المستأجر.
    async with tenant_session_maker(owner["tenant_id"], owner["user_id"])() as s:
        theirs = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"
            " WHERE operation = 'POST /api/v1/analysis/runs'"))).scalar_one()
    assert theirs == 0, "صاحبُ البحث يرى جوابَ ضيفه المخزون"

    # والضيفُ في مستأجره هو لا يرى شيئًا — الصفُّ ليس هناك أصلًا.
    async with tenant_session_maker(guest["tenant_id"], guest["user_id"])() as s:
        home = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"
            " WHERE operation = 'POST /api/v1/analysis/runs'"))).scalar_one()
    assert home == 0


async def test_23_a_manuscript_replays_without_a_second_initial_version(
    two_tenants,
):
    """**مخطوطةٌ واحدةٌ ونسخةٌ أولى واحدة** — والمسارُ يكتب صفَّين لا صفًّا.

    وهذا ما يجعل برهانَ هذا المسار مختلفًا: `create_manuscript` يُنشئ
    المخطوطةَ **ونسختَها الأولى** ويربطهما. فطفرةٌ مُعادةٌ هنا لا تُنتج
    مخطوطتين فحسب، بل نسختَي «v1» — وتاريخُ نسخٍ مزدوجٌ من أوّل يوم.

    **والمسارُ `/api/v1/manuscripts`**: الموجّهُ مضمومٌ بسابقة `/api/v1`
    وحدها، والمعالجُ `publishing.py::create_manuscript`.
    """
    from tests.test_at_rc_t1a_project_access import _owned_project

    slot = two_tenants["a"]
    project_id = await _owned_project(slot, title="بحثُ المخطوطة المُعادة")
    body = {"project_id": str(project_id), "title_ar": "مخطوطةٌ تُعاد",
            "language": "ar"}
    key = _key()

    async with _client(slot) as http:
        first = await http.post(MANUSCRIPTS, json=body,
                                headers={"Idempotency-Key": key})
        second = await http.post(MANUSCRIPTS, json=body,
                                 headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    manuscript_id = first.json()["id"]
    assert second.json()["id"] == manuscript_id, "أُعيد معرّفُ مخطوطةٍ أخرى"
    assert first.json() == second.json(), "الجسمُ المُعاد ليس الأصل"
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert "idempotency-replayed" not in {k.lower() for k in first.headers}

    assert await _scalar(
        "SELECT count(*) FROM manuscripts WHERE project_id = :p",
        {"p": str(project_id)}) == 1, "مخطوطتان من نيّةٍ واحدة"
    # **ولا نسخةَ «v1» ثانية** — وهذه لا يمسّها برهانُ المخطوطة وحدها.
    assert await _scalar(
        "SELECT count(*) FROM manuscript_versions WHERE manuscript_id = :m",
        {"m": manuscript_id}) == 1, "نسختا «v1» لمخطوطةٍ واحدة"
    assert await _completed_records(
        slot["tenant_id"], f"POST {MANUSCRIPTS}") == 1


# ═════════════ ١٠ · التعارضُ يُدوَّن، ويبقى بعد الرفض ═════════════


async def test_24_a_key_conflict_leaves_a_durable_audit_event(two_tenants):
    """**إشارةُ سلامةٍ تبقى بعد ٤٠٩** — وإلّا فليست إشارة.

    ومفتاحٌ واحدٌ لجسمَين مختلفَين إمّا عميلٌ معطوب وإمّا محاولةُ تخمين.
    وكلاهما يُنظر فيه لاحقًا، **ولا يُنظر في ما لم يُكتب**.

    ## والفخُّ الذي يُتجنّب هنا بعينه

    الطريقُ البديهيّ — أن تُكتب الحادثةُ ثمّ يُرفع ٤٠٩ — **يمحوها**:
    الرفعُ يُرجِع المعاملة، فيذهب الحدثُ معها. فالحدثُ يُكتب ويُعاد جوابُ
    الرفض **قيمةً لا استثناءً**، فتُودِع البنيةُ المعاملةَ قبل إرسال
    الجواب. وهذا الفحصُ يقرأ الجدولَ **بعد أن يكتمل الطلبُ كلُّه**.
    """
    slot = two_tenants["a"]
    key = _key()
    kept = f"h2a-audit-a-{uuid.uuid4().hex[:8]}"
    refused = f"h2a-audit-b-{uuid.uuid4().hex[:8]}"

    before = await _scalar(
        "SELECT count(*) FROM audit_events"
        " WHERE tenant_id = :t AND action = 'idempotency.conflict'",
        {"t": str(slot["tenant_id"])})

    async with _client(slot) as http:
        first = await http.post(
            WORKSPACE, json={"title_ar": kept, "starting_from": "idea"},
            headers={"Idempotency-Key": key})
        clash = await http.post(
            WORKSPACE, json={"title_ar": refused, "starting_from": "idea"},
            headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert clash.status_code == 409, clash.text
    assert clash.json()["error"]["code"] == "idempotency.key_reused"

    # ══ (أ) الحدثُ موجودٌ، وواحدٌ بالضبط ══
    after = await _scalar(
        "SELECT count(*) FROM audit_events"
        " WHERE tenant_id = :t AND action = 'idempotency.conflict'",
        {"t": str(slot["tenant_id"])})
    assert after == before + 1, (
        f"حوادثُ التعارض {before} ← {after} — يُنتظر واحدٌ بالضبط")

    # ══ (ب) وما فيه: عمليّةٌ وسببٌ وفاعل — ولا أكثر ══
    row = await _scalar(
        "SELECT to_jsonb(e) FROM audit_events e"
        " WHERE e.tenant_id = :t AND e.action = 'idempotency.conflict'"
        " ORDER BY e.chain_seq DESC LIMIT 1", {"t": str(slot["tenant_id"])})
    assert row["object_type"] == "idempotency_key", row
    assert row["actor_user_id"] == str(slot["user_id"]), row
    assert row["state_after"] == {
        "operation": f"POST {WORKSPACE}", "cause": "fingerprint_mismatch"}, row
    assert row["state_before"] is None, row

    # ══ (ج) ولا مفتاحٌ خام، ولا جسمٌ، ولا بصمة ══
    blob = json.dumps(row, ensure_ascii=False, default=str)
    assert key not in blob, "المفتاحُ الخام في سجلّ التدقيق"
    assert digest_key(key) not in blob, "بصمةُ المفتاح في سجلّ التدقيق"
    assert kept not in blob and refused not in blob, (
        "عنوانُ بحثٍ في سجلّ التدقيق — محتوى طلبٍ لا بيانَ سلامة")

    # ══ (د) والطفرةُ الأصليّةُ واحدةٌ، والمرفوضةُ لم تقع ══
    assert await _project_rows(slot["tenant_id"], kept) == 1
    assert await _project_rows(slot["tenant_id"], refused) == 0

    # **ولا تحمل معاملةُ الرفض إلّا الحدث**: لا صفَّ تكرارٍ ثانيًا، ولا
    # صفَّ مجالٍ — فليست كتابةً نصفيّةً تحت جوابِ رفض.
    assert await _completed_records(slot["tenant_id"], f"POST {WORKSPACE}") == 1, (
        "كُتب صفُّ تكرارٍ ثانٍ في معاملة الرفض")

    # ══ (هـ) وسلسلةُ التدقيق ما زالت متّصلة ══
    from athera_api.services import audit as audit_service

    assert await _scalar(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
        "   AND action = 'idempotency.conflict' AND prev_hash IS NOT NULL"
        "   AND hash <> ''", {"t": str(slot["tenant_id"])}) >= 1
    assert audit_service.GENESIS_HASH is not None


# ═════════════ ١١ · سياسةُ الصفّ: الأفعالُ الثلاثةُ كلُّها ═════════════


async def test_25_rls_refuses_select_update_and_delete_across_actors(
    two_tenants,
):
    """**والقراءةُ ليست كلَّ الخطر** — فصفٌّ يُعدَّل أخطرُ من صفٍّ يُقرأ.

    ولو أمكن لفاعلٍ أن يكتب `response_body` في صفِّ فاعلٍ آخر لَصار قادرًا
    على أن **يُملي عليه جوابًا** يستلمه عند أوّل إعادة: لا تسريبٌ فحسب،
    بل حَقنُ جواب. فتُقاس الأفعالُ الثلاثةُ صراحةً، لا القراءةُ وحدها.

    ويُقاس بدور التطبيق (`athera_app`) — الذي لا يتجاوز السياسة — وبفاعلٍ
    **حقيقيٍّ** له عضويّةٌ في المستأجر نفسِه، لا بمعرّفٍ مُختلَق.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session_maker
    from tests.test_at_rc_t1a_project_access import _second_user

    slot = two_tenants["a"]
    intruder = await _second_user(slot["tenant_id"],
                                  email=f"h2a-rls-{uuid.uuid4().hex[:8]}@example.test")
    operation = f"POST {WORKSPACE}"

    async with _client(slot) as http:
        created = await http.post(
            WORKSPACE, json={"title_ar": f"h2a-rls2-{uuid.uuid4().hex[:8]}",
                             "starting_from": "idea"},
            headers={"Idempotency-Key": _key()})
    assert created.status_code == 201, created.text

    mine = await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE tenant_id = :t AND actor_user_id = :u AND operation = :o",
        {"t": str(slot["tenant_id"]), "u": str(slot["user_id"]), "o": operation})
    assert mine >= 1, "لا صفَّ أصلًا — فالفحصُ لا يفحص شيئًا"

    owner_rows = "SELECT count(*) FROM idempotency_records WHERE actor_user_id = :u"

    # ══ (أ) الفاعلُ الثاني لا يقرأ ══
    async with tenant_session_maker(slot["tenant_id"], intruder["user_id"])() as s:
        seen = (await s.execute(text(owner_rows),
                                {"u": str(slot["user_id"])})).scalar_one()
    assert seen == 0, "فاعلٌ آخر يقرأ صفَّ غيره — جوابٌ مخزونٌ مكشوف"

    # ══ (ب) ولا يُعدّل — والسياسةُ تُخفي فلا يُطابق شيءٌ ══
    async with tenant_session_maker(slot["tenant_id"], intruder["user_id"])() as s:
        changed = (await s.execute(text(
            "UPDATE idempotency_records SET response_body = '{\"id\": \"injected\"}'"
            " WHERE actor_user_id = :u RETURNING id"),
            {"u": str(slot["user_id"])})).rowcount
    assert changed in (0, -1), "فاعلٌ آخر عدّل صفًّا ليس له — حَقنُ جواب"

    # **والصفُّ يُقرأ بعدها فيُتحقّق أنّه لم يتبدّل** — فالرقمُ صفرٌ قد
    # يعني «لم يُطابق» وقد يعني «لم يُبلَّغ»، والصفُّ نفسُه هو الفيصل.
    injected = await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE actor_user_id = :u AND response_body->>'id' = 'injected'",
        {"u": str(slot["user_id"])})
    assert injected == 0, "الجوابُ المخزون حُقن بقيمةِ غريب"

    # ══ (ج) ولا يحذف صفًّا سارِيًا ══
    async with tenant_session_maker(slot["tenant_id"], intruder["user_id"])() as s:
        removed = (await s.execute(text(
            "DELETE FROM idempotency_records WHERE actor_user_id = :u"
            "   AND expires_at > now() RETURNING id"),
            {"u": str(slot["user_id"])})).rowcount
    assert removed in (0, -1), "فاعلٌ آخر حذف صفًّا ساريًا ليس له"
    assert await _scalar(owner_rows, {"u": str(slot["user_id"])}) == mine, (
        "نقص عددُ صفوف صاحبها بعد محاولةِ غريب")

    # ══ (د) ومستأجرٌ آخر لا يرى شيئًا ولو بفاعلٍ صحيح ══
    other = two_tenants["b"]
    async with tenant_session_maker(other["tenant_id"], other["user_id"])() as s:
        across = (await s.execute(text(owner_rows),
                                  {"u": str(slot["user_id"])})).scalar_one()
    assert across == 0, "مستأجرٌ آخر يرى صفوفَ غيره"

    # ══ (هـ) وجلسةٌ بمستأجرٍ بلا فاعلٍ تفشل مغلقةً ══
    async with tenant_session_maker(slot["tenant_id"], None)() as s:
        blind = (await s.execute(text(
            "SELECT count(*) FROM idempotency_records"))).scalar_one()
    assert blind == 0, "جلسةٌ بلا فاعلٍ رأت صفوفًا — `app_current_actor()` لم تفشل مغلقةً"


async def test_26_the_conflict_audit_survives_on_a_route_that_owns_its_commit(
    two_tenants,
):
    """**والدعوى تُعاد على المسار المختلفِ بنيةً** — لا على أسهلها.

    فـ`workspace` تُودِعه `TransactionalRoute` بعد أن يبني جوابَه، أمّا
    `analysis.create_run` **فيملك معاملتَه في متنه**: جلسةُ `_scope_pair`
    تُودِع عند خروج السياق. وجوابُ ٤٠٩ يُعاد من **داخل** ذلك السياق، فلو
    كان خروجًا بالاستثناء لَرجعت المعاملةُ ولَذهبت الحادثةُ معها.

    وهذا هو الفرقُ الذي يجعل برهانَ `test_24` وحدَه غيرَ كافٍ.
    """
    from tests.test_at_rc_t1a_project_access import _owned_project

    slot = two_tenants["a"]
    project_id = await _owned_project(slot, title="بحثُ تعارضِ التشغيلة")
    body = await _runnable(slot, slot, project_id)
    key = _key()

    before = await _scalar(
        "SELECT count(*) FROM audit_events"
        " WHERE tenant_id = :t AND action = 'idempotency.conflict'",
        {"t": str(slot["tenant_id"])})

    async with _client(slot) as http:
        first = await http.post("/api/v1/analysis/runs", json=body,
                                headers={"Idempotency-Key": key})
        # المفتاحُ نفسُه، وجسمٌ يختلف في بذرةٍ واحدة — فبصمةٌ أخرى.
        clash = await http.post("/api/v1/analysis/runs",
                                json={**body, "random_seed": 99},
                                headers={"Idempotency-Key": key})

    assert first.status_code == 201, first.text
    assert clash.status_code == 409, clash.text
    assert clash.json()["error"]["code"] == "idempotency.key_reused", clash.text

    after = await _scalar(
        "SELECT count(*) FROM audit_events"
        " WHERE tenant_id = :t AND action = 'idempotency.conflict'",
        {"t": str(slot["tenant_id"])})
    assert after == before + 1, (
        f"حوادثُ التعارض {before} ← {after} — ضاعت الحادثةُ مع خروج النطاق")

    # **ولا تشغيلةَ ثانية**: الرفضُ رفضٌ، والحادثةُ وحدَها ما بقي.
    assert await _runs_for(body["plan_id"]) == 1, "نُفِّذ الطلبُ المتعارض"

    row = await _scalar(
        "SELECT to_jsonb(e) FROM audit_events e"
        " WHERE e.tenant_id = :t AND e.action = 'idempotency.conflict'"
        " ORDER BY e.chain_seq DESC LIMIT 1", {"t": str(slot["tenant_id"])})
    assert row["state_after"]["operation"] == "POST /api/v1/analysis/runs", row
    assert key not in json.dumps(row, ensure_ascii=False, default=str)
