# Wave 1.1 — Thesis Center stabilization

**Branch:** `hotfix/thesis-center-stabilization` · **Base:** `main` @ `3fb473d`
**Migration `0030`** (coordinated: Wave 2-A rebases after). No production touched, no deploy, no merge.

---

## Root cause: two disjoint architectures presented as one workflow

`ThesisSection` is constructed in exactly one place in the repository —
`apps/api/athera_api/routers/thesis.py`, inside the legacy
`POST /theses/{id}/parse`. The modern upload path (`document_intelligence`)
never writes `ThesisSection` or `ThesisResult`; it writes `FactCandidate`.
And `POST /theses/{id}/mine-opportunities` reads **only** `ThesisSection` and
`ThesisResult`.

So on a thesis processed by the canonical pipeline the miner has **no
evidence at all** — and the card gated the mine button on `thesis.parsed_at`,
a stamp only `/parse` ever sets. The button was therefore either permanently
dead, or, if pressed, wrote `opportunities_mined_at` and stamped
"scanned and found nothing" onto a thesis that was never scanned.

Three smaller failures rode on the same card:

- **Buttons the server refuses.** "Parse thesis" was rendered on every card,
  including a manually registered thesis with no file (`thesis.no_file`, 422)
  and a card mid-processing (`thesis.processing_in_flight`, 409).
- **Silent clicks.** One page-level `busyId` and one page-level error banner.
  A researcher clicking card 15 saw nothing happen, then had to scroll to the
  top to read an error that never said which card it belonged to.
- **No exit.** The product had no way to remove a thesis at all.

---

## Fixed

### A · One authoritative card state machine

`apps/api/athera_api/services/thesis/card_actions.py` — one pure function
computes what the card may offer. The screen renders it and re-derives
nothing; `actions.primary` even decides which control gets primary styling,
so there is no second ordering in JSX that can silently diverge.

| Card state | Primary | Also offered |
|---|---|---|
| `queued` / `parsing` / `extracting` | *(none)* | running notice only |
| `uploaded`, file attached | Read the thesis | ⋯ |
| `uploaded`, **no file** | **Attach thesis file** | ⋯ (no trash-file) |
| `awaiting_consent` / `ready_for_review` / `completed` | **Review extracted information** | Reprocess, ⋯ |
| `failed` | Try again | ⋯ |
| `text_layer_missing` | *(none)* | blocked reason (no OCR yet) |

Mining is offered on top of that only when the miner has something to read.

### B · Legacy UX duplication removed, endpoint kept

`POST /theses/{id}/parse` is **untouched and still live** — a test pins that
it still exists and still returns `thesis.no_file` for a fileless thesis. What
was withdrawn is its presentation as a card action. `card_actions.offers_parse`
is a named predicate returning `False` for every state, with the reason in its
docstring: running both paths on one thesis produces two parallel candidate
sets, one of them outside the review screen. A test iterates every state ×
file/no-file and fails if any offers it.

### C · Per-card action feedback

`cardState: Record<thesisId, {busy, error, notice, menuOpen, preview,
trashNeedsConfirm}>`. Busy carries the *name* of the running action, so the
button shows its own working label and conflicting controls disable. Success
and failure render inside that card (`data-testid="card-notice"` /
`"card-error"`). Nothing about an action is reported at page level any more.

### D · Opportunity mining — honest, not faked

**The misleading CTA is gone.** `card_actions.mining_state` answers the real
question — does `thesis_sections` or `thesis_results` hold anything for this
thesis — instead of reading `parsed_at`. Three states: `available`,
`in_flight`, `no_evidence`. In `no_evidence` there is no button; there is a
sentence, bilingual, from the server, that names the missing integration:

> Opportunity mining is not available yet. The miner reads extracted sections
> and results, and none were written for this thesis: the current reading
> pipeline produces reviewable fact candidates and writes neither sections nor
> results. It becomes available once your reviewed extraction is wired into
> the miner — and no button promises that before it is true.

Opportunities remain candidates throughout; no copy claims publication
readiness or a guaranteed gap.

### E · Safe removal — *superseded by review round 2 below*

> The dependency preview and the Mumbai-latency reasoning below still
> stand. What changed: there is no delete, the action is a reversible
> archive, and the blocking set now asks for an acknowledgement instead
> of refusing. Read § 1 of “Review round 2” for the contract that shipped.

`⋯` menu per card: Review · Reprocess (when valid) · **Remove from Thesis
Center** · **Move source file to Trash** (only when a file exists) — with a
line in the menu itself saying the last two are different actions.

`apps/api/athera_api/services/thesis/removal.py` computes a dependency
preview in **one statement** (eight scalar subqueries — the DB is in Mumbai
and the API in Singapore; eight round trips would cost half a second before
the "are you sure?" is even shown).

| Dependency | Needs an acknowledgement? |
|---|---|
| extracted sections, extracted results | **no** — machine output, a second read reproduces it |
| sections you verified yourself | **yes** |
| fact candidates you approved / rejected / marked *unknown* | **yes** |
| candidate publication opportunities | **yes** |
| projects converted from its opportunities | **yes** |
| authorship agreements | **yes** |
| rights approvals | **yes** |

`GET /theses/{id}/removal-preview` returns the preview before the confirm is
offered. `DELETE /theses/{id}` recomputes it under a `FOR UPDATE` lock and
returns **409 `thesis.removal_blocked`** with the blocking counts if anything
human-decided rests on the thesis. Nothing is ever cascade-deleted silently.

Audit history survives: `audit_events.object_id` has no FK to `theses`
(deliberately), and the table carries an immutability trigger plus revoked
UPDATE/DELETE for `athera_app`. The library file is untouched by removal —
trashing it is `POST /files/{id}/trash`, a separate call the researcher makes
explicitly, and it is a soft trash. **No S3 object is ever permanently
deleted**; a test scans every router for `delete_object`.

---

## Opportunity idempotency result — stated plainly

**Duplicates were possible, and this proves it.** `mine_opportunities` looped
`for draft in drafts: session.add(PublicationOpportunity(...))` with no
existence check; there is no unique constraint on `publication_opportunities`;
no test covered mining at all. The miner is fully deterministic — same facts,
byte-identical drafts. So every press wrote the whole set again. The second
consequence was worse than the duplication: identical opportunities then get
compared to each other in the overlap matrix (§23.7), raising a **false
salami-slicing alert** and demanding a human ruling on a conflict a double
click created.

Now:

1. The thesis row is locked with `FOR UPDATE` **in the read that was already
   happening** — no extra round trip. Two concurrent requests serialize; the
   second reads a fresh snapshot that includes the first's committed rows.
2. Identity key `(opportunity_kind, paper_kind, working_title_ar)` — exactly
   what the miner derives deterministically from thesis elements.
3. Duplicates *within* one run are folded too.
4. `MineResponse.opportunities_already_present` separates "wrote nothing
   because it already exists" from "found nothing" — the second run says
   `created=0, already_present=N` instead of a bare, misleading zero.

**Proved by** `test_over_http_mining_twice_never_produces_a_duplicate`: mine
three times, assert the row count in the database equals the first run's
count and that runs 2 and 3 report `created=0, already_present=N`.

**Residual, named:** the fix is a row lock, not a database constraint. A
partial unique index on `(thesis_id, opportunity_kind, paper_kind,
working_title_ar)` would make it structural, and that needs a migration —
deliberately not created here (see below).

---

## Deployment order — migrate first, then deploy

**Migrate `0029 → 0030`, then deploy this branch. Not the other way round.**

Why, precisely:

- **New code requires the columns.** `models/thesis.py` declares `archived_at`
  and `archived_by`, so SQLAlchemy selects them on every read of `theses`.
  Wave 1.1 therefore cannot serve any schema below `0030` — deploying first
  produces `UndefinedColumnError: column theses.archived_at does not exist` on
  the Thesis Center's first request.
- **Old code tolerates them.** The deployed v88 `Thesis` model has no archive
  columns at all (verified against `origin/main`; the `archived_at` hits there
  belong to `research_projects`, a different table's pre-existing soft delete).
  It writes `theses` with its own explicit column list, so both new columns
  land `NULL` — which reads as "not archived", the correct state for
  everything it writes. `0030` is additive and nullable, so nothing it does
  breaks.

So the only window is **v88 serving schema `0030`**, between the migration and
the deploy. That window is proved in
`apps/api/tests/test_at_rolling_deploy_compatibility.py` § 3: v88's three real
writes to `theses` — the upload INSERT, the `processing.mark` UPDATE and the
`claim_for_processing` UPDATE — replayed as raw SQL with v88's exact column
list, each asserting `rowcount == 1` so RLS cannot silently filter the write to
nothing and leave a green test on no work at all. Plus: the new
`ck_theses_archive_is_named` constraint never refuses a v88 write (it leaves
both columns `NULL`), and that constraint is proved live by rejecting a half
mark.

### The `0028` expand-window job was retired — replacement first

Wave 1's rollout was the mirror image: migrate to `0028`, deploy Wave 1 onto
it, then contract to `0029`. Its window was therefore "**new** code on an
**older** schema", guarded by a dedicated job and
`test_at_wave1_on_expand_window.py`. That rollout is complete and production
sits at `0029`.

Because Wave 1.1 is migrate-first, that property is now both unnecessary and
permanently unachievable — a job asserting it would fail forever on a correct
design. It was removed **only after** the replacement above was in place and
passing, never the reverse. Removed with it: the CI steps that build, migrate
and grant `athera_expand`, and the one rolling-deploy test that needed that
database — a permanently skipped test reads as coverage while guarding
nothing.

Two guards were narrowed rather than weakened as a consequence:

- `PINNED_BY_DESIGN` is now empty and the CI pin assertion is `== set()`, not
  `<= {"0028"}`. The old form passed vacuously today and would have passed
  again the day `0028` reappeared with no step to justify it.
- `athera_expand` is gone from the permitted test-database names in
  `db_safety.py`.

And one guard was **added**, because the failure that caused this round had
none: `test_the_rc_head_pin_says_one_number_and_it_is_the_chain_head` asserts
the RC journey's pinned schema equals the repository's chain head and appears
as exactly one number across the step's name, condition, log line and error
text — so the next migration breaks a unit test on the branch instead of a
workflow after merge. It reads that step alone, not the file, so honest prose
elsewhere ("production is at `0029`") is not a false positive; a companion test
proves the guard fails on a stale pin and on two disagreeing numbers.

---

## Migration `0030` — what it is and why it is safe

Round one shipped no migration, on the reading that a thesis with no
dependency could simply be deleted. Review rejected that, correctly, and
granted this wave `0030`; Wave 2-A (PR #103) rebases and renumbers afterwards,
which is the coordinator's to sequence, not mine.

`0030_thesis_archive.py` adds exactly:

- `theses.archived_at` — nullable timestamp, no server default
- `theses.archived_by` — nullable FK to `users`, `ON DELETE RESTRICT`
- `ck_theses_archive_is_named` — `(archived_at IS NULL) = (archived_by IS NULL)`,
  so there is no such thing as an archive event with no time or no actor. Every
  existing row is `NULL` in both, so all of them satisfy it on day one.
- A partial index `(tenant_id, created_at DESC, id DESC) WHERE archived_at IS NULL`
  for the new default listing filter — Mumbai/Singapore means statement cost is
  response time, and the filter must not cost a scan.

**Why it cannot break the deployed Wave 1 server** (schema 0029, API v88):
nullable, no `server_default` writing anything, no constraint touching a column
the old server knows, and no `ALTER`/`DROP`/`UPDATE`/`DELETE` on existing data.
The old server inserts with its own explicit column list, so both columns land
`NULL` — which reads as "not archived", the correct state for everything it
writes; and nothing in v88 deletes a thesis or reads an archive. Two tests hold
this: a static one asserting the migration is purely additive, and a live one
performing exactly the v88-shaped INSERT on schema 0030 and asserting it
succeeds with both columns `NULL` and the card reading `is_archived: false`.

**Still not created:** a unique index on publication opportunities. Mining
idempotency remains a row lock plus an in-transaction identity check, as
instructed.

One knock-on the migration caused and this PR fixes: two rolling-deploy tests
guarded on `head != "0029"` and would have become silent skips the moment any
migration landed after 0029 — leaving the 0029 contract enforced in the
database with no test witnessing it. The guard is now "has reached 0029".

---

## Deferred (with the exact work required)

1. **Wire reviewed canonical facts into the miner.** This is the real fix for
   the root cause and is out of scope for a bounded hotfix. Required:
   `document_intelligence` (or a promotion step after review) must project
   **approved** `FactCandidate` rows into `ThesisSection` / `ThesisResult` —
   or `miner.ThesisFacts` must be built from approved candidates directly.
   Concretely: `questions` currently comes from sections with
   `section_key == "questions"`, which `/parse` never even writes (it writes
   only `results` and `research_problem`); `results` comes from
   `ThesisResult`, which nothing in the modern path writes; `variables` comes
   from `ThesisResult.variables`. Each needs a named source among the reviewed
   candidate field keys, and each must keep its locator and verbatim quote so
   the grounding barrier holds. Until then `mining_state` stays `no_evidence`
   and says so.
2. **A DB uniqueness constraint for opportunities** — needs a migration number
   coordinated with Wave 2-A.
3. **Removal RBAC.** Removal is tenant-scoped like the rest of this router.
   Whether destroying a Thesis Center record should require an approver
   permission rather than any member is a product decision, not a hotfix one.
4. **Keyboard menu semantics.** The `⋯` panel is a labelled `role="group"` of
   real buttons, not `role="menu"` — because arrow-key menu navigation is not
   implemented, and an ARIA role that promises it would fail a screen-reader
   user the same way a dead button fails a sighted one.

---

## Test results — what was observed and what was not

**Observed locally** (`/Users/hassansomili/dev/ATHERA/.venv-sec`):

- `pytest -q` from `apps/api` — **1808 passed, 371 skipped** (base on this
  branch point: 1766 / 364). 42 new tests pass; 7 new DB-backed tests skip
  because there is no local PostgreSQL.
- `ruff check .` from `apps/api` — clean (this is the scope CI uses).
- `lint-imports` from `apps/api` — 2 contracts kept, 0 broken.
- The removal-preview statement was compiled against the PostgreSQL dialect
  and inspected: one `SELECT`, eight scalar subqueries, and the `FOR UPDATE`
  clause is emitted on the thesis read.

**Observed in CI on PR #104** (run `33983466943`, commit before the RC fix):
API, Web typecheck/lint/build, Browser and Security jobs all green — including
the 7 DB-backed tests and the new `thesis-center.spec.ts`.

**Not observed locally — no PostgreSQL, no node/npm on this machine:**

- The 7 DB-backed tests in `test_at_thesis_center_stabilization.py`
  (mining idempotency over HTTP, modern-pipeline card, manual thesis, parse
  still refusing a fileless thesis, disposable removal + audit survival,
  removal refused with preview, tenant isolation across list / preview /
  mine / delete).
- `npm run typecheck`, `npm run lint`, `npm run build`.
- The new Playwright spec `apps/web/tests/thesis-center.spec.ts`.

Those run in CI. **No gate above is claimed green that was not run here.**

### Browser spec (`test:thesis-center`, wired into `package.json` and `ci.yml`)

Every case clicks a control, captures the request that left, answers it, and
asserts what changed **in that card** — never that a button exists:

- queued thesis: no legacy parse, no mine, no retry; running notice shown
- `parsing` / `extracting`: no dead action, and no control emits a write
- `ready_for_review`: review CTA navigates to that thesis's review screen
- reprocess: POST observed (202), card's state text visibly becomes "Queued"
- mining: offered only with evidence; second press returns
  `created=0, already_present=3` and the card count does not double
- a failed action shows its error in the right card and in no other card
- manual thesis with no file: no parse, an Attach-file action instead
- disposable thesis: preview → confirm → DELETE observed → card gone, its
  neighbour untouched
- removal refused: named dependencies with counts, no confirm button, and
  **no DELETE request leaves the page**
- a 404 refusal renders inside its own card

The spec's header states plainly that it does **not** prove tenant isolation
— that is proven in the API suite against a live database with two tenants.

---

## Files changed

**API**
- `apps/api/athera_api/services/thesis/card_actions.py` *(new)*
- `apps/api/athera_api/services/thesis/removal.py` *(new)*
- `apps/api/athera_api/routers/thesis.py`
- `apps/api/athera_api/schemas/thesis.py`
- `apps/api/athera_api/i18n/catalog.py`
- `apps/api/tests/test_at_thesis_center_stabilization.py` *(new, 49 tests)*

**Web**
- `apps/web/src/app/[locale]/theses/page.tsx`
- `apps/web/messages/ar.json`, `apps/web/messages/en.json`
- `apps/web/tests/thesis-center.spec.ts` *(new)*
- `apps/web/package.json`

**CI**
- `.github/workflows/ci.yml`

## API changes

| Method | Path | Change |
|---|---|---|
| `GET` | `/api/v1/theses` | **+** `actions`, `results_extracted`, `source_file_id`, `archived_at`; archived rows excluded by default; **+** `view=archived` |
| `POST` | `/api/v1/theses` | same additions on the created card |
| `POST` | `/api/v1/theses/{id}/parse` | **still live**; now 403 without file `write`, 409 while in flight, and its state write is conditional |
| `POST` | `/api/v1/theses/{id}/mine-opportunities` | idempotent; **+** `opportunities_already_present`, `withheld_for_missing_title`, `title_note`; 403 without file `write`; no longer 5xx on a null title |
| `GET` | `/api/v1/theses/{id}/removal-preview` | **new** — `needs_acknowledgement` (not `removable`) |
| `POST` | `/api/v1/theses/{id}/archive` | **new** — 200, or 409 `thesis.archive_needs_acknowledgement` / `thesis.processing_in_flight` |
| `POST` | `/api/v1/theses/{id}/restore` | **new** |
| `DELETE` | `/api/v1/theses/{id}` | **does not exist** — no physical delete anywhere |

All additive on existing responses. New error keys
`thesis.archive_needs_acknowledgement`, `thesis.archived`, `thesis.not_archived`
exist in both catalogue locales.

Every one of `parse`, `mine-opportunities`, `removal-preview`, `archive` and
`restore` resolves object permission on the thesis's linked file: `read` for
preview, `write` for parse and mine, `delete` for archive and restore.

## Hard rules

- No router commits: no `session.commit()` added; `tenant_session` owns the
  transaction. `test_no_router_owns_its_transaction` passes.
- RLS untouched: no policy, role or grant changed. The `tenant_isolation`
  policy is `FOR ALL`, so DELETE is already covered; `athera_app` already has
  DELETE on these tables and remains non-BYPASSRLS.
- Catalogue parity holds in both `messages/*.json` and the API catalogue.
- The new spec is wired into `package.json` **and** `ci.yml`.
- No production credentials on the branch.

## Review round 2 — five defects, all addressed

### 1 · Removal is now a soft archive; physical delete is gone from the product

The first cut wrote `DELETE FROM theses` for a thesis with no scientific
dependency. That was wrong: the row is the head of a chain — sections,
results, fact candidates, opportunities, authorship agreements, rights
approvals, converted projects — and `ON DELETE CASCADE` sits on five tables
beneath it. "No dependency **today**" is not "never will be", and a delete
does not come back.

- **Migration `0030`** adds `archived_at` and `archived_by`, plus a partial
  index for the default listing. Nothing else changes.
- **There is no DELETE endpoint on theses at all**, and no `delete(Thesis)`
  statement in any router. An AST test fails if either returns.
- `POST /theses/{id}/archive` hides; `POST /theses/{id}/restore` brings it
  back. The default listing excludes archived rows; `view=archived` shows
  them, and the screen exposes that view — an archive with no visible way
  back is a delete in the researcher's experience.
- **Everything is preserved.** The DB test counts sections, results,
  opportunities and the thesis row before and after archive **and** restore,
  and asserts the census is identical. `rows_deleted: 0` is stated in the
  response, not implied.
- Trashing the source file stays a separate explicit action, still a soft
  trash, and still no S3 object is ever permanently deleted.

**The dependency preview survives, and its meaning changed honestly.** It used
to say "this blocks the delete". The delete is gone, so it now says "this is
what gets hidden with it" — and because hiding a record that live work hangs
from is a decision to take knowingly, it requires an explicit
`acknowledge: true`; the server answers 409 `thesis.archive_needs_acknowledgement`
without it. Refusing a reversible action outright would have been the wrong
shape; asking is the right one.

**Rolling-deploy safety.** Both columns are nullable with no server default
and no constraint touching an existing column, so the deployed Wave 1 server
(schema 0029, API v88) keeps inserting theses with its own column list and
they land `NULL` — meaning "not archived", the correct state for everything it
writes. A live-database test performs exactly that INSERT with only the
columns 0029 knows and asserts it succeeds.

### 2 · The nullable-title mining 5xx

`theses.title_ar` is nullable; `ThesisFacts.title` was typed `str`. So
`" ".join([facts.title, …])` raised `TypeError` and the researcher got a 500
on a perfectly valid path: a thesis parsed by the legacy route (so it has
sections and results) whose title has not been extracted yet. Reproduced
directly before fixing.

The miner is now title-optional **and invents nothing**. Four proposal kinds
derive their working title from the thesis title; with no title they are
withheld, and the response says how many and why (`withheld_for_missing_title`
plus a bilingual `title_note`). The question-derived proposal still runs, so a
missing title narrows the scan instead of failing it. A PostgreSQL HTTP test
asserts the endpoint returns 202, never 5xx, and that no invented title
reaches the column or the card.

### 3 · The legacy `/parse` state regression

`/parse` read `processing_state` at the top of the request, then fetched and
parsed the document — slow work — then wrote the state it had read, with **no
condition**. If the modern pipeline advanced to `ready_for_review` in that
window, parse wrote `extracting` back over it, and the card sat in a running
state with no task to lift it.

Two limits now:

- `/parse` is refused with 409 while work is in flight, so the two pipelines
  never write in parallel.
- `processing.settle_after_legacy_parse` performs a **single conditional
  UPDATE** whose `CASE` reads the state at write time, not read time. It
  advances only `uploaded` / `failed` / `text_layer_missing` to
  `ready_for_review`; anything else is left literally untouched, including
  `awaiting_consent` (the DIC2 gate is never jumped as a side effect). It has
  to be one statement: the `missing_text_layer_says_so` constraint means
  setting `text_layer_state='present'` and lifting the state cannot be split
  without passing through a moment the database rejects.

Two DB tests: the known sequence (extraction reaches review → legacy parse
afterwards → final state must stay canonical and must not be `extracting`),
and a table-driven one asserting the settle rule lifts exactly the three
states it may and leaves every other state byte-identical.

### 4 · Object-level authorization

`parse`, `mine-opportunities`, `removal-preview`, `archive` and `restore` all
pass through one guard that asks `rbac.require_object_action` on the thesis's
linked file — the same model `document_intelligence` uses, resolving from the
`ObjectGrant` that `files.upload_file` writes, not from `uploaded_by`. Levels:
`read` for preview, `write` for parse and mine, `delete` for archive and
restore (only `owner` carries `delete`).

The DB test creates a **second user in the same tenant** with the researcher
role and asserts all five actions return 403, and that the thesis is untouched
afterwards. A companion test asserts the file's owner still passes every one
of them — a guard that refuses everyone is its own defect. A thesis with no
linked file has no object to check; tenant scope alone applies there, and the
guard says so in prose rather than leaving it to be inferred.

### 5 · Destructive lifecycle actions are blocked while processing is in flight

For `queued` / `parsing` / `extracting`, archive and trash are withdrawn, with
a bilingual reason that states there is **no cancellation contract** at this
stage rather than pretending one exists. **The server enforces it**, not only
the UI: `archive` returns 409 `thesis.processing_in_flight`, proven per
in-flight state on a live database, with the row asserted still unarchived.
The Playwright spec asserts that no lifecycle write — DELETE, archive or trash
— leaves the client in any in-flight state, and a further spec drives archive
across four states and asserts the product never sends a DELETE at all.

### Not in this PR, by instruction

The reviewed-FactCandidate → miner integration and the publication-opportunity
unique index. Neither was built.

## RC E2E claim 8 — repaired by state, not by swapping a string

The first RC run failed one claim: «٨ · retry offered where allowed, 409 where
not» asserted a literal `"Try again"` on the text-PDF thesis. That assertion
predates this wave, when one retry button served every state. Section A split
it into three, each honest about what it does:

| State | Control |
|---|---|
| `uploaded` (file attached, never read) | **Read the thesis** — a first read is not a retry |
| `ready_for_review` / `completed` / `awaiting_consent` | **Read it again** — it succeeded; this is a re-read, not a repair |
| `failed` (a read that failed, `failure_code` set) | **Try again** |
| `text_layer_missing` | *none* — plus the written reason |

**No product regression.** A failed first read leaves the thesis in `failed`
with a named `failure_code`, which is retryable, so the card renders **Try
again** exactly as the claim intends. The text PDF simply succeeds, so it
now correctly renders "Read it again" — the harness was asserting a label
that state no longer produces.

The claim now reads the card's state first and demands the control that state
**requires**, from a named table. Not weakened, strengthened in three ways:

1. `expectReadAction` asserts the required control is present **and that the
   other two are absent**. A check that only asserts presence would pass on a
   card showing all three — which is what the card did before this wave.
2. The negative half now denies **all three** controls on the scanned
   document, not just "Try again", and still requires the written reason.
3. No regex that would accept either label regardless of state, and no "any
   button" — either would stop testing the very distinction this wave added.

Reading state rather than pinning a string also fixes the failure in the other
direction: a text PDF whose read genuinely fails in some environment lands on
"Analysis failed", where **Try again** is correct — the claim interrogates the
state, not the luck of the run.

**The `failed` branch is proved deterministically where it can be built.** The
RC journey cannot manufacture a failed read on demand (its text PDF succeeds),
so `thesis-center.spec.ts` gains three intercepted cases — never read, read and
succeeded, read and failed — each asserting its own control and the absence of
the other two.

Both 409 paths in the claim are untouched: `thesis.retry_needs_ocr` on the
scanned document, and `thesis.processing_in_flight` from two concurrent
reprocess requests.

## One rename worth flagging

`actions.in_progress` became `actions.is_running`. The existing guard
`test_no_invented_progress_percentage_anywhere_in_this_feature` fired on the
substring — and it was right to. The name changed; the guard was not weakened.
