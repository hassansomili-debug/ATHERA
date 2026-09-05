# Wave 1.1 — Thesis Center stabilization

**Branch:** `hotfix/thesis-center-stabilization` · **Base:** `main` @ `3fb473d`
**No migration.** No production touched, no deploy, no merge.

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

### E · Safe removal

`⋯` menu per card: Review · Reprocess (when valid) · **Remove from Thesis
Center** · **Move source file to Trash** (only when a file exists) — with a
line in the menu itself saying the last two are different actions.

`apps/api/athera_api/services/thesis/removal.py` computes a dependency
preview in **one statement** (eight scalar subqueries — the DB is in Mumbai
and the API in Singapore; eight round trips would cost half a second before
the "are you sure?" is even shown).

| Dependency | Blocks removal? |
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

## Migration: none — and why

Wave 2-A owns `0030` on `wave2/researcher-intelligence-foundation`. No
competing migration was created, and none turned out to be needed:

- **Soft-removal marker:** not needed at all. `theses.processing_state` is a
  closed vocabulary with a DB check constraint, so adding a `removed` value
  *would* have needed a migration. It is unnecessary because a thesis with no
  human-decided dependency is genuinely disposable: its row is deleted, the
  machine output under it goes with it, and the audit trail — which has no FK
  to `theses` and cannot be deleted by the app role — carries the history. A
  thesis that *does* carry decisions is never removed, so it never needs a
  marker either.
- **Mining uniqueness:** expressed as a row lock plus an in-transaction
  identity check rather than a unique index.

A test asserts the highest migration on this branch is still `0029` and that
no `0030` exists here.

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
| `GET` | `/api/v1/theses` | **+** `actions` object, `results_extracted`, `source_file_id` |
| `POST` | `/api/v1/theses` | same additions on the created card |
| `POST` | `/api/v1/theses/{id}/mine-opportunities` | idempotent; **+** `opportunities_already_present` |
| `GET` | `/api/v1/theses/{id}/removal-preview` | **new** |
| `DELETE` | `/api/v1/theses/{id}` | **new** — 200, or 409 `thesis.removal_blocked` |
| `POST` | `/api/v1/theses/{id}/parse` | **unchanged, still live** |

All additive on existing responses. New error key `thesis.removal_blocked`
exists in both catalogue locales.

## Hard rules

- No router commits: no `session.commit()` added; `tenant_session` owns the
  transaction. `test_no_router_owns_its_transaction` passes.
- RLS untouched: no policy, role or grant changed. The `tenant_isolation`
  policy is `FOR ALL`, so DELETE is already covered; `athera_app` already has
  DELETE on these tables and remains non-BYPASSRLS.
- Catalogue parity holds in both `messages/*.json` and the API catalogue.
- The new spec is wired into `package.json` **and** `ci.yml`.
- No production credentials on the branch.

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
