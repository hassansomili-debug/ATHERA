# Wave 1.1 — Thesis Center stabilization

**Branch:** `hotfix/thesis-center-stabilization` · **Base:** `main` @ `3fb473d`
**Migration:** `0030_thesis_archive` (`down_revision = 0029`) — coordinated; Wave 2-A rebases after.
No production touched, no deploy, no merge.

---

## Root cause: two disjoint architectures presented as one workflow

`ThesisSection` is constructed in exactly one place in the repository — inside
the legacy `POST /theses/{id}/parse`. The modern upload path
(`document_intelligence`) never writes `ThesisSection` or `ThesisResult`; it
writes `FactCandidate`. And `POST /theses/{id}/mine-opportunities` reads **only**
`ThesisSection` and `ThesisResult`.

So on a thesis processed by the canonical pipeline the miner has **no evidence at
all** — and the card gated its mine button on `thesis.parsed_at`, a stamp only
`/parse` ever sets. The button was permanently dead, or, if pressed, stamped
"scanned and found nothing" onto a thesis that was never scanned.

Three smaller failures rode on the same card: buttons the server refuses
("Parse thesis" on a fileless thesis → 422; any action mid-processing → 409); one
page-level busy flag and one page-level error banner, so a click on card 15
reported nothing and the error never said which card it belonged to; and no way
to remove a thesis at all.

---

## What shipped

### One authoritative card state machine

`services/thesis/card_actions.py` — one pure function decides what a card may
offer. The screen renders it and re-derives nothing; `actions.primary` even
decides which control gets primary styling, so no second ordering can drift.

| Card state | Primary | Also |
|---|---|---|
| `queued` / `parsing` / `extracting` | *(none)* | running notice only |
| `uploaded`, file attached | Read the thesis | ⋯ |
| `uploaded`, **no file** | **Attach thesis file** | ⋯ (no trash-file) |
| `awaiting_consent` / `ready_for_review` / `completed` | **Review extracted information** | Reprocess, ⋯ |
| `failed` | Try again | ⋯ |
| `text_layer_missing` | *(none)* | blocked reason (no OCR yet) |
| archived | **Restore** | *(no work action)* |

### Archive, not deletion

- Migration `0030_thesis_archive` adds `archived_at` and `archived_by`, a paired
  check `(archived_at IS NULL) = (archived_by IS NULL)` so no archive event
  lacks a time or an actor, and a partial index for the default listing.
- **No physical deletion anywhere**: no `DELETE` endpoint on theses, no
  `delete(Thesis)` in any router, no S3 object deletion in any path. AST tests
  fail if any returns.
- `POST /theses/{id}/archive`, `POST /theses/{id}/restore`,
  `GET /theses/{id}/removal-preview`. The default listing excludes archived rows;
  an **Archived view** exists in the UI — an archive with no visible way back is
  a deletion in the researcher's experience.
- **Everything is preserved.** The DB test counts sections, results,
  opportunities and the thesis row before and after archive **and** restore and
  asserts the census is identical. `rows_deleted: 0` is stated, not implied.
- **Library Trash is a separate action from Thesis Center archive.** Archiving
  never touches the file; trashing the file never archives the record; the menu
  says so, and it remains a soft trash.

### Dependency preview and explicit acknowledgement

The preview computes in **one statement** (eight scalar subqueries; the DB is in
Mumbai and the API in Singapore, so eight round trips would cost half a second
before "are you sure?" is even shown).

| Dependency | Needs acknowledgement? |
|---|---|
| extracted sections, extracted results | **no** — machine output, a second read reproduces it |
| sections you verified yourself | **yes** |
| fact candidates approved / rejected / marked *unknown* | **yes** |
| candidate publication opportunities | **yes** |
| projects converted from its opportunities | **yes** |
| authorship agreements | **yes** |
| rights approvals | **yes** |

Archiving something human-decided requires explicit `acknowledge: true`; the
server answers 409 `thesis.archive_needs_acknowledgement` without it. It asks
rather than refuses, because archiving is reversible.

### Object-level authorization

`parse`, `mine-opportunities`, `removal-preview`, `archive` and `restore` all
pass through one guard calling `rbac.require_object_action` on the thesis's
linked file — the same model `document_intelligence` uses, resolving from the
`ObjectGrant` that `files.upload_file` writes, not from `uploaded_by`. Levels:
`read` for preview, `write` for parse and mine, `delete` for archive and restore.

A **same-tenant** second user with the researcher role gets **403** on all five,
with the thesis asserted untouched afterwards; a companion test asserts the
file's owner still succeeds at all five, since a guard that refuses everyone is
its own defect. A thesis with no linked file has no object to check; tenant scope
alone applies there, stated in prose rather than left to be inferred.

### Honest mining availability, and no invented title

`mining_state` answers the real question — does `thesis_sections` or
`thesis_results` hold anything — instead of reading `parsed_at`. Three states:
`available`, `in_flight`, `no_evidence`. In `no_evidence` there is no button;
there is a bilingual sentence naming the missing integration.

`theses.title_ar` is nullable and `ThesisFacts.title` was typed `str`, so
`" ".join(...)` raised `TypeError` and returned **500** on a valid path. The
miner is now title-optional and **invents nothing**: the four proposal kinds
whose working title derives from the thesis title are withheld with a count and
a reason (`withheld_for_missing_title`, `title_note`); the question-derived
proposal still runs. A PostgreSQL HTTP test asserts 202, never 5xx, and that no
invented title reaches the column or the card.

### Duplicate opportunities cannot recur

The miner is deterministic, the loop had no existence check, there is no unique
constraint, and no test covered mining at all — so every press rewrote the whole
set, and identical rows then raised a **false salami-slicing alert** in the
overlap matrix, demanding a human ruling on a conflict a double click created.
Now: the thesis row is locked `FOR UPDATE` inside the read that already
happened, an identity key `(opportunity_kind, paper_kind, working_title_ar)`
skips existing proposals, within-run duplicates fold, and
`opportunities_already_present` distinguishes "already there" from "found
nothing". Proven by mining three times and asserting the row count never grows.

### Legacy `/parse`: hidden from the card, unchanged as an API

`/parse` is **still live** and still returns `thesis.no_file` for a fileless
thesis. What was withdrawn is its presentation as a card action, via a named
predicate whose docstring gives the reason: running both paths on one thesis
produces two parallel candidate sets, one outside the review screen. A test
iterates every state × file/no-file and fails if any offers it.

**Neither its success nor its failure path can regress newer canonical state.**
It read the state, did slow work, then wrote what it had read unconditionally —
stamping `extracting` back over a pipeline that had reached review. And the
failure path did the same, dragging a review-ready thesis down to "Analysis
failed" because an older path was tried and did not work. Both now share one
condition from one vocabulary (`LEGACY_PARSE_MAY_SETTLE`) evaluated in the
database at write time; `processing.mark` gained an `only_from` guard that
becomes a real `WHERE` and returns the row count, and the audit says explicitly
when a state write was skipped and why. `/parse` is also refused 409 while work
is in flight.

### Malformed documents no longer leak as 500

`/parse` caught only `NoTextLayer` and `UnsupportedDocument`; anything else —
`PdfReadError` on a truncated file — escaped as a **500**. The failure vocabulary
already contained `parse_failed`, bilingual, **with no code path writing it**.
It is wired now: named code, a safe technical detail (exception class and
truncated message, never document text), and **422**, because the input failed
and not the service.

### In-flight lifecycle actions blocked server-side

For `queued` / `parsing` / `extracting`, archive and trash are withdrawn with a
bilingual reason stating there is **no cancellation contract** rather than
pretending one exists. The server enforces it: `archive` returns 409
`thesis.processing_in_flight`, proven per in-flight state with the row asserted
still unarchived.

**And the source file itself is protected at its own endpoint.**
`POST /files/{file_id}/trash` previously checked only ownership and project
links, so a direct API client could pull the file out from under a running
pipeline. It now refuses with 409 `library.file_busy_processing` when a thesis
linked by `theses.file_id` is in `processing.IN_FLIGHT` — **imported from the
canonical vocabulary, not copied** — writing neither `trashed_at` nor
`trashed_by`, changing no thesis, faking no cancellation. The check runs
**before** the project-link confirmation, because `confirm` may override a
warning but never a prohibition; a test reads the AST to hold that ordering.
Six PostgreSQL HTTP tests cover it: each in-flight state separately, the same
file trashable once processing settles, an unrelated file and a settled thesis's
file unchanged, and the project-link confirmation neither bypassed nor weakened.

### Per-card feedback

`cardState` per thesis id: busy carries the *name* of the running action, so each
button shows its own working label and conflicting controls disable. Success and
failure render inside that card. Nothing about an action is reported at page
level any more, except the one case where the card itself leaves the list.

### Bilingual parity

Every new state, reason, dependency label and error exists in both `ar` and `en`,
in `messages/*.json` and the API catalogue, enforced by the existing parity
tests.

---

## Deployment order

1. Production is at schema `0029`, API **v88**.
2. **Apply `0029 → 0030` first.**
3. **Verify head = `0030`.**
4. **Then** deploy the Wave 1.1 API and Web.
5. Run production smoke / acceptance.
6. **Do not begin Wave 2-A deployment until Wave 1.1 production is confirmed
   GREEN.**

**Why migrate-first, precisely.** `models/thesis.py` declares `archived_at` and
`archived_by`, so SQLAlchemy selects them on every read of `theses`; Wave 1.1
cannot serve any schema below `0030` — deploying first yields
`UndefinedColumnError: column theses.archived_at does not exist` on the Thesis
Center's first request. Conversely the deployed v88 `Thesis` model has no archive
columns at all, writes `theses` with its own explicit column list, and never
reads an archive — and `0030` is additive and nullable, so both columns land
`NULL`, meaning "not archived", the correct state for everything v88 writes.

**Rolling-deploy compatibility — old v88 must keep working on schema `0030`.**
That is the only window, and it is proved in
`test_at_rolling_deploy_compatibility.py` § 3: v88's three real writes to
`theses` — the upload INSERT, the `processing.mark` UPDATE and the
`claim_for_processing` UPDATE — replayed as raw SQL with v88's exact column list,
each asserting `rowcount == 1` so RLS cannot silently filter a write to nothing
and leave a green test on no work. Plus: `ck_theses_archive_is_named` never
refuses a v88 write, and that constraint is proved live by rejecting a half mark.

The Wave 1 `0028` expand-window job was retired — **replacement first, removal
second**. Wave 1's rollout was the mirror image (migrate to `0028`, deploy onto
it, contract to `0029`), so its property was "new code on an older schema". That
rollout is complete; with Wave 1.1 migrate-first, the property is unnecessary and
permanently unachievable, and a job asserting it would fail forever on a correct
design. Removed with it: the CI steps building `athera_expand` and the one test
needing that database — a permanently skipped test reads as coverage while
guarding nothing. Consequently `PINNED_BY_DESIGN` is empty and the CI pin
assertion is `== set()` rather than `<= {"0028"}`, and a new guard
(`test_the_rc_head_pin_says_one_number_and_it_is_the_chain_head`) asserts the RC
journey's pinned schema equals the chain head and appears as exactly one number
across the step's name, condition, log line and error text — so the next
migration breaks a unit test on the branch instead of a workflow after merge.

---

## API changes

| Method | Path | Change |
|---|---|---|
| `GET` | `/api/v1/theses` | **+** `actions`, `results_extracted`, `source_file_id`, `archived_at`; archived excluded by default; **+** `view=archived` |
| `POST` | `/api/v1/theses` | same additions on the created card |
| `POST` | `/api/v1/theses/{id}/parse` | **still live**; 403 without file `write`, 409 while in flight, conditional state write, 422 (not 500) on an unreadable document |
| `POST` | `/api/v1/theses/{id}/mine-opportunities` | idempotent; **+** `opportunities_already_present`, `withheld_for_missing_title`, `title_note`; 403 without file `write`; no 5xx on a null title |
| `GET` | `/api/v1/theses/{id}/removal-preview` | **new** — `needs_acknowledgement` |
| `POST` | `/api/v1/theses/{id}/archive` | **new** — 200, or 409 `thesis.archive_needs_acknowledgement` / `thesis.processing_in_flight` |
| `POST` | `/api/v1/theses/{id}/restore` | **new** |
| `POST` | `/api/v1/files/{file_id}/trash` | **+** 409 `library.file_busy_processing` while a linked thesis is in flight; existing behaviour otherwise unchanged |
| `DELETE` | `/api/v1/theses/{id}` | **does not exist** — no physical deletion |

New bilingual error keys: `thesis.archive_needs_acknowledgement`,
`thesis.archived`, `thesis.not_archived`, `thesis.parse_failed`,
`library.file_busy_processing`.

---

## Files changed

**API** — `services/thesis/card_actions.py` *(new)*, `services/thesis/removal.py`
*(new)*, `services/thesis/processing.py`, `services/thesis/miner.py`,
`routers/thesis.py`, `routers/files.py`, `schemas/thesis.py`, `models/thesis.py`,
`i18n/catalog.py`, `tests/test_at_thesis_center_stabilization.py` *(new)*,
`tests/test_at_rolling_deploy_compatibility.py`, `tests/test_at_s0_12_13_infra.py`,
`tests/db_safety.py`, `tests/test_at_wave1_on_expand_window.py` *(deleted)*

**DB** — `infra/db/migrations/versions/0030_thesis_archive.py` *(new)*

**Web** — `src/app/[locale]/theses/page.tsx`, `messages/ar.json`,
`messages/en.json`, `tests/thesis-center.spec.ts` *(new)*,
`tests/rc-thesis-journey.spec.ts`, `package.json`

**CI** — `.github/workflows/ci.yml`, `.github/workflows/rc-e2e.yml`

---

## Coverage

**Real PostgreSQL**, over HTTP with real identities: archive preserves every row
and restore returns it; acknowledgement required and refused without it;
same-tenant object-level 403 with owner still succeeding; nullable-title mining
never 5xx; mining idempotent across three runs; legacy parse cannot regress
canonical state (success and failure); in-flight archive refused per state;
in-flight source-file trash refused per state with the settled case succeeding;
v88's writes on schema `0030` with `rowcount` asserted; tenant isolation across
list, preview, mine, archive and restore.

**Real browser** (`thesis-center.spec.ts`, network-intercepted, runs on every
PR): every case clicks a control, captures the request, answers it and asserts
what changed **in that card** — never that a button exists. Queued/parsing/
extracting offer no dead action and emit no lifecycle write; the three read
labels are mutually exclusive per state; review CTA navigates; reprocess changes
visible state; mining offered only with evidence and never duplicates; a failed
action reports in the right card and no other; a manual thesis offers Attach, not
Parse; archive previews then hides, the neighbour untouched, and the archived
view finds it; restore returns it; acknowledgement is sent explicitly; and the
product never sends a DELETE in any state.

**RC full-stack journey** asserts the schema head is `0030` and drives the real
API and database end to end.

**Hard rules held.** No `session.commit()` added — `tenant_session` owns the
transaction. RLS untouched: no policy, role or grant changed; the
`tenant_isolation` policy is `FOR ALL`, and `athera_app` remains non-BYPASSRLS.
Catalogue parity enforced. The new browser spec is wired into `package.json`
**and** `ci.yml`. No production credentials on the branch.

## Explicitly not in this PR

Reviewed-`FactCandidate` → miner integration; the `publication_opportunities`
unique index; anything in Wave 2-A or PR #103.
