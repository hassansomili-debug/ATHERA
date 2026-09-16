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
import uuid

import pytest

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
