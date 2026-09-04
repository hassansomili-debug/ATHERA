"""مقياس المكتبة | The library at scale — «المكتبة ما تتحمل كتب».

**العطب لم يكن في صفٍّ ولا في استعلامٍ خاطئ، بل في عددها.** كانت الشاشة
تقرأ كل ملفات المستأجر بلا حدّ، ثم تسأل القاعدة عن حال **كل ملف على حدة**.
والـAPI في سنغافورة والقاعدة في مومباي، فكل عبارة رحلةٌ بنحو ستين مللي
ثانية عبر البحر: أربعون ملفًا ⇐ مئةٌ وعشرون رحلة ⇐ سبع ثوانٍ من الشبكة
وحدها، تزيد طردًا مع كل كتابٍ يُضاف.

فهنا يُقاس ما لا يظهر في اختبار صحّة: **عدد العبارات**. وثلاثة أشياء
تُثبَت — أن الحساب المجمَّع يساوي الحساب المفرد قيمةً بقيمة، وأن كلفة
الصفحة لا تنمو مع عدد الملفات، وأن الترقيم يمرّ على كل ملفٍ مرّة واحدة
بلا تكرار ولا سقوط.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import uuid

import pytest

from tests.conftest import requires_db

pytestmark = [pytest.mark.asyncio, requires_db]

pytest_asyncio = pytest.importorskip("pytest_asyncio")

# الحالات التي يمرّ بها مستند فعلًا (`services/document_intelligence/states.py`)
# مضافًا إليها `completed` التي تعرضها المكتبة — والخليط مقصود: حارسٌ يفحص
# حالةً واحدة يمرّ على انحرافٍ في السبع الباقيات.
RUN_STATES = ("running", "parsing", "extracting", "awaiting_consent",
              "awaiting_review", "completed", "parse_failed", "extract_failed")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@pytest_asyncio.fixture
async def clients(two_tenants):
    """عميلان مصادقان لمستأجرين مختلفين — الترقيم يُختبر عبر الـHTTP لا تحته."""
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    transport = httpx.ASGITransport(app=app)
    made = {}
    for slot in ("a", "b"):
        tenant = two_tenants[slot]
        token = issue_access_token(
            user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
            roles=["researcher"], mfa_satisfied=True,
        )
        made[slot] = httpx.AsyncClient(
            transport=transport, base_url="http://test",
            headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
        )
    yield made
    for http in made.values():
        await http.aclose()
    from athera_api.db import engine
    await engine.dispose()


async def _add_file(session, *, tenant_id, user_id, name: str):
    from athera_api.models.files import File

    row = File(
        tenant_id=tenant_id,
        storage_key=f"tenants/{tenant_id}/files/{uuid.uuid4()}/{name}",
        original_filename=name, content_type="application/pdf",
        size_bytes=1024, status="stored", uploaded_by=user_id,
    )
    session.add(row)
    await session.flush()
    return row


async def _add_thesis(session, *, tenant_id, file_id):
    from athera_api.models.thesis import Thesis

    thesis = Thesis(tenant_id=tenant_id, file_id=file_id, title_ar="رسالة اختبار")
    session.add(thesis)
    await session.flush()
    return thesis


async def _add_run(session, *, tenant_id, file_id, status: str, created_at=None):
    from athera_api.models.research import ExtractionRun

    run = ExtractionRun(tenant_id=tenant_id, file_id=file_id, extractor="rules",
                        status=status, started_at=_now())
    if created_at is not None:
        run.created_at = created_at
    session.add(run)
    await session.flush()
    return run


async def _add_candidates(session, *, tenant_id, file_id, run_id, total: int, reviewed: int,
                          decided_by):
    """مرشّحون بحالاتٍ حقيقية — والمراجَع ما خرج عن `unverified`.

    **والقرار يحمل فاعله وتاريخه.** `ck_candidate_decided_requires_actor` في
    ترحيل 0005 تشترط أن كل حالٍ غير `unverified` لها `decided_by` و
    `decided_at` — «قرار بلا فاعل وتاريخ غير مقبول، والرفض قرار أيضًا».
    وكان التركيب هنا يعتمد مرشّحًا بلا فاعل، فيمرّ محليًّا حيث لا قاعدة
    ويسقط في CI حيث توجد. والقيمة تُقرأ من قيدها لا من الذاكرة.
    """
    from athera_api.models.research import DocumentChunk, FactCandidate

    text = "نصٌّ مقتبس من المستند"
    for index in range(total):
        chunk = DocumentChunk(tenant_id=tenant_id, file_id=file_id, seq=index + 1,
                              text=text, locator=f"p.1 ¶{index + 1}", page_number=1,
                              paragraph_index=index + 1, char_count=len(text))
        session.add(chunk)
        await session.flush()
        session.add(FactCandidate(
            tenant_id=tenant_id, extraction_run_id=run_id, file_id=file_id,
            chunk_id=chunk.id, memory_category="researcher_fact", field_key="sample",
            statement_ar="عبارة", quote=text, locator=chunk.locator, confidence=0.5,
            **({"status": "approved", "decided_by": decided_by, "decided_at": _now()}
               if index < reviewed else {"status": "unverified"}),
        ))
    await session.flush()


@contextlib.contextmanager
def counting_statements():
    """يعدّ عبارات القاعدة الحقيقية — و`set_config` ليست منها.

    ضبطُ سياق المستأجر عبارتان في كل جلسة مهما كان المسار؛ عدُّهما يخلط
    ثمنًا ثابتًا بثمنٍ ينمو، وما يُقاس هنا هو الثاني.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    seen: list[str] = []
    original = AsyncSession.execute

    async def spy(self, statement, *args, **kwargs):
        rendered = str(statement)
        if "set_config" not in rendered:
            seen.append(rendered)
        return await original(self, statement, *args, **kwargs)

    AsyncSession.execute = spy
    try:
        yield seen
    finally:
        AsyncSession.execute = original


# ══════════ التكافؤ: المجمَّع يساوي المفرد، حالةً بحالة ══════════

async def test_the_batched_state_equals_the_per_file_state_for_every_case(two_tenants):
    """**قيمةً بقيمة، لا رمزَ نجاحٍ ولا «تقريبًا».**

    الصياغتان قائمتان معًا عمدًا: المفردة هي التعريف المرجعي، والمجمَّعة هي
    ما تُستعمل. وحسابان لشيءٍ واحد يفترقان بأول تعديل — وقد وقع ذلك هنا
    من قبل — فهذا الاختبار هو ما يمنع افتراقهما بصمت.
    """
    from athera_api.db import tenant_session
    from athera_api.services import workspace

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    file_ids: list[uuid.UUID] = []

    async with tenant_session(tid, uid) as session:
        # (١) ملفٌ لم يُقرأ أصلًا: لا رسالة ولا تشغيلة.
        bare = await _add_file(session, tenant_id=tid, user_id=uid, name="bare.pdf")
        file_ids.append(bare.id)

        # (٢) رسالةٌ بلا تشغيلة — مسجَّلة ولم تبدأ معالجتها بعد.
        pending = await _add_file(session, tenant_id=tid, user_id=uid, name="pending.pdf")
        await _add_thesis(session, tenant_id=tid, file_id=pending.id)
        file_ids.append(pending.id)

        # (٣) كل حالٍ تمرّ بها تشغيلة.
        for state in RUN_STATES:
            row = await _add_file(session, tenant_id=tid, user_id=uid, name=f"{state}.pdf")
            await _add_thesis(session, tenant_id=tid, file_id=row.id)
            run = await _add_run(session, tenant_id=tid, file_id=row.id, status=state)
            if state in ("awaiting_review", "completed"):
                await _add_candidates(session, tenant_id=tid, file_id=row.id,
                                      run_id=run.id, total=3, reviewed=2,
                                      decided_by=uid)
            file_ids.append(row.id)

        # (٤) تشغيلتان: الأحدث هي المعروضة، والأقدم لا تُقرأ.
        rerun = await _add_file(session, tenant_id=tid, user_id=uid, name="rerun.pdf")
        await _add_thesis(session, tenant_id=tid, file_id=rerun.id)
        await _add_run(session, tenant_id=tid, file_id=rerun.id, status="parse_failed",
                       created_at=_now() - dt.timedelta(hours=2))
        await _add_run(session, tenant_id=tid, file_id=rerun.id, status="completed",
                       created_at=_now())
        file_ids.append(rerun.id)

    async with tenant_session(tid, uid) as session:
        batched = await workspace.files_processing_state(
            session, tenant_id=tid, file_ids=file_ids)
        one_by_one = {}
        for file_id in file_ids:
            one_by_one[file_id] = await workspace.file_processing_state(
                session, tenant_id=tid, file_id=file_id)

    assert batched == one_by_one, "الحساب المجمَّع فارق الحساب المفرد"
    # ولا يُقبل أن يتطابقا على «لا شيء»: الحالات المقصودة موجودة فعلًا.
    assert batched[file_ids[0]] == ("not_processed", 0, 0, None)
    assert batched[file_ids[1]][0] == "not_processed"
    assert batched[file_ids[1]][3] is not None
    assert {batched[fid][0] for fid in file_ids[2:2 + len(RUN_STATES)]} == set(RUN_STATES)
    assert batched[file_ids[-1]][0] == "completed", "التشغيلة الأقدم حجبت الأحدث"
    with_candidates = [batched[fid] for fid in file_ids if batched[fid][1] > 0]
    assert len(with_candidates) == 2
    assert all(state[1] == 3 and state[2] == 2 for state in with_candidates)


async def test_an_empty_page_spends_no_round_trip(two_tenants):
    """صفحةٌ بلا ملفات لا تُنفق زيارةً على سؤالٍ لا موضوع له."""
    from athera_api.db import tenant_session
    from athera_api.services import workspace

    tenant = two_tenants["a"]
    async with tenant_session(tenant["tenant_id"], tenant["user_id"]) as session:
        with counting_statements() as seen:
            empty = await workspace.files_processing_state(
                session, tenant_id=tenant["tenant_id"], file_ids=[])
        assert empty == {}
        assert seen == [], f"عبارةٌ أُنفقت على قائمةٍ فارغة: {seen}"


# ══════════ الكلفة: عبارةٌ واحدة مهما بلغ عدد الكتب ══════════

async def test_the_per_file_state_is_the_n_plus_one_it_was_accused_of_being(two_tenants):
    """**العدد المقيس قبل الإصلاح** — ثلاث عبارات لملفٍ عُولج، وواحدة لغيره.

    ويُقاس ولا يُقدَّر: بغير هذا الرقم لا يُعرف ما وفّره الإصلاح.
    """
    from athera_api.db import tenant_session
    from athera_api.services import workspace

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]

    async with tenant_session(tid, uid) as session:
        plain = await _add_file(session, tenant_id=tid, user_id=uid, name="plain.pdf")
        processed = await _add_file(session, tenant_id=tid, user_id=uid, name="done.pdf")
        await _add_thesis(session, tenant_id=tid, file_id=processed.id)
        await _add_run(session, tenant_id=tid, file_id=processed.id, status="completed")
        plain_id, processed_id = plain.id, processed.id

    async with tenant_session(tid, uid) as session:
        with counting_statements() as seen:
            await workspace.file_processing_state(session, tenant_id=tid, file_id=plain_id)
        assert len(seen) == 1, seen
        with counting_statements() as seen:
            await workspace.file_processing_state(session, tenant_id=tid, file_id=processed_id)
        assert len(seen) == 3, seen


async def test_the_library_page_costs_one_statement_however_many_books(clients, two_tenants):
    """**الكلفة ثابتة، لا تتبع عدد الملفات.**

    وهذا هو الفحص الذي كان غائبًا: كل اختبارات المكتبة كانت تسأل «هل ظهر
    الملف؟» ولا واحد منها يسأل «بكم عبارة؟» — فنما الثمن اثنتي عشرة مرّة
    بلا أن يصرخ شيء.
    """
    from athera_api.db import tenant_session

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    http = clients["a"]

    async with tenant_session(tid, uid) as session:
        for index in range(3):
            row = await _add_file(session, tenant_id=tid, user_id=uid, name=f"few-{index}.pdf")
            await _add_thesis(session, tenant_id=tid, file_id=row.id)
            await _add_run(session, tenant_id=tid, file_id=row.id, status="completed")

    with counting_statements() as few:
        response = await http.get("/api/v1/files?limit=100")
    assert response.status_code == 200, response.text
    small = len(response.json())

    async with tenant_session(tid, uid) as session:
        for index in range(12):
            row = await _add_file(session, tenant_id=tid, user_id=uid, name=f"many-{index}.pdf")
            await _add_thesis(session, tenant_id=tid, file_id=row.id)
            await _add_run(session, tenant_id=tid, file_id=row.id, status="awaiting_review")

    with counting_statements() as many:
        response = await http.get("/api/v1/files?limit=100")
    assert response.status_code == 200, response.text
    assert len(response.json()) >= small + 12, "الملفات الجديدة لم تُعرض أصلًا"

    assert len(few) == len(many) == 1, (
        f"كلفة الصفحة تتبع عدد الملفات: {len(few)} ثم {len(many)}")


# ══════════ الترقيم: صفحةٌ محدودة، ومرورٌ كامل بلا تكرار ══════════

async def test_the_listing_is_bounded_and_pages_cover_every_file_exactly_once(
    clients, two_tenants
):
    """**قائمةٌ بلا حدّ ليست قائمة** — والمرور عليها يجب أن يبلغ آخرها.

    والمؤشّر مفتاحي على `(created_at, id)`: الملفات هنا تُنشأ في معاملةٍ
    واحدة فتتساوى طوابعها الزمنية تمامًا — وهي الحالة التي يسقط عندها
    ترتيبٌ بـ`created_at` وحده، فيتكرّر ملفٌ في صفحتين أو يسقط بينهما.
    """
    from athera_api.db import tenant_session

    tenant = two_tenants["b"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    http = clients["b"]

    async with tenant_session(tid, uid) as session:
        for index in range(30):
            await _add_file(session, tenant_id=tid, user_id=uid, name=f"book-{index:02d}.pdf")

    default_page = await http.get("/api/v1/files")
    assert default_page.status_code == 200
    assert len(default_page.json()) == 25, "الصفحة الافتراضية غير محدودة"

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(20):  # حدٌّ للدوران: حلقةٌ لا تنتهي عطبٌ لا صبر
        path = "/api/v1/files?limit=7" + (f"&after={cursor}" if cursor else "")
        page = await http.get(path)
        assert page.status_code == 200, page.text
        rows = page.json()
        if not rows:
            break
        seen.extend(row["id"] for row in rows)
        assert len(rows) <= 7
        cursor = rows[-1]["id"]
    assert len(seen) == len(set(seen)), "ملفٌ ظهر في صفحتين"
    assert len(seen) == 30, f"المرور لم يبلغ كل الملفات: {len(seen)}"


async def test_the_page_size_cannot_be_pushed_past_its_ceiling(clients):
    """سقفٌ يُطلب تجاوزه يُرفض — لا يُنفَّذ صامتًا."""
    http = clients["a"]
    assert (await http.get("/api/v1/files?limit=1000")).status_code == 422
    assert (await http.get("/api/v1/files?limit=0")).status_code == 422
    assert (await http.get("/api/v1/files?limit=100")).status_code == 200


async def test_a_cursor_from_another_tenant_reveals_nothing(clients, two_tenants):
    """مؤشّرٌ إلى ملف مستأجرٍ آخر لا يفتح صفحته — ولا يقول إنه موجود."""
    from athera_api.db import tenant_session

    other = two_tenants["b"]
    async with tenant_session(other["tenant_id"], other["user_id"]) as session:
        hidden = await _add_file(session, tenant_id=other["tenant_id"],
                                 user_id=other["user_id"], name="secret.pdf")
        hidden_id = hidden.id

    response = await clients["a"].get(f"/api/v1/files?after={hidden_id}")
    assert response.status_code == 200
    assert response.json() == []
