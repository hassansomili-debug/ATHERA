# Thesis Automation Contract — what canonical knowledge is safe to mine

**Status:** T0.1 eligibility contract **implemented** in
`apps/api/athera_api/services/thesis/fact_eligibility.py` and consumed by
`services/thesis/canonical_facts.py`. **P0-T1 automatic opportunity triggering
implemented by PR #115** — see §12.

---

## 1. The product principle

> **The researcher approves scientific decisions, not intermediate machine
> extraction.**

The previous contract required `FactCandidate.status == "approved"` *and* a
verified `ResearcherMemory` before a fact could reach the opportunity miner. That
made every extracted sentence a decision the researcher had to sign, which is not
what their judgement is for — and it meant a thesis could be fully extracted,
patiently reviewed, and still mine nothing.

That prerequisite is **superseded**. Machine facts can now feed the miner.

**This removes the human check that was carrying the safety.** Nothing else
stood between a model's guess and a persisted publication opportunity. So the
deterministic classification below is now load-bearing: it is the only guard, and
it is written on the principle that **exclusion is the default and eligibility is
earned**.

---

## 2. Four operational classes

These are **mining-eligibility states, not claims about scientific truth**. They
are computed at read time. There is **no database enum, no new table, and no
migration** — a fact's class is derived, never stored, so it always reflects
current policy rather than the policy in force when the row was written.

| Class | Meaning |
|---|---|
| `AUTO_ELIGIBLE` | may be used as miner input |
| `SUPPORT_ONLY` | may inform queries, keywords, ranking and context — **never independently creates an opportunity**, and never grounds a result, variable, sample ref, tested hypothesis or overlap identity |
| `REVIEW_REQUIRED` | a material unresolved conflict, or an extraction review flag; **the affected concept is withheld, the thesis is not blocked** |
| `EXCLUDED` | does not enter anything |

For T0.1, `SUPPORT_ONLY` facts are simply **omitted from `ThesisFacts`**. The
miner has no separate channel for supporting context, and inventing one would
mean redesigning the miner — out of scope. Omission is the honest behaviour: they
cannot ground anything, so they do not appear.

---

## 3. AUTO_ELIGIBLE hard gates — all required

1. ExtractionRun state is one that produced advanced extraction evidence
2. candidate status is compatible with automation (`unverified` or `approved`)
3. `extraction_status == "extracted"`, read from **inside the `value` JSON**
4. `field_key` is a known mining field
5. same tenant
6. same thesis `source_file_id`
7. a `DocumentChunk` exists
8. `quote_is_grounded(candidate.quote, chunk.text)` — the existing verifier at
   `services/extraction/base.py:57`, reused, not reimplemented
9. usable, structurally valid value
10. field-specific confidence threshold satisfied
11. no deterministic unresolved material conflict for that concept

**`extraction_status` is not a column.** It lives in the `value` JSON, and
`"not_found"` is a real alternative value. A missing key is treated
**deliberately** — a candidate that does not say how it was extracted is excluded,
not assumed successful.

---

## 4. Confidence is extraction confidence, not scientific truth

`0.99` means "this text was probably read correctly from the document". It does
not mean the content is scientifically sound, and **it buys no exemptions**:

| Situation | Result |
|---|---|
| `0.99` + `ambiguous` | `REVIEW_REQUIRED` |
| `0.99` + `needs_review` | `REVIEW_REQUIRED` |
| `0.99` + ungrounded quote | `EXCLUDED` |
| `0.99` + wrong tenant or wrong file | `EXCLUDED` |

The check order in `classify()` enforces this: **ownership first** (confidence
cannot buy it), then **grounding** (an integrity failure, which dominates even a
review flag), then the review flag, and the threshold **last**.

**A low-confidence fact is never promoted because the miner wants more
evidence.** That inversion is the specific failure the thresholds exist to
prevent.

---

## 5. Thresholds — one policy map, calibrated over time

Defaults: `AUTO_ELIGIBLE ≥ 0.85`, `SUPPORT_ONLY 0.70–0.85`, `EXCLUDED < 0.70`.
Field-specific overrides are **stricter**, because a wrong value there reshapes
every downstream inference:

| Field | auto | support |
|---|---|---|
| `sample_size`, `hypothesis_results` | 0.95 | 0.85 |
| `population`, `primary_findings` | 0.92 | 0.80 |
| `title_ar`, `questions`, `hypotheses`, `constructs`, `instruments`, `sampling` | 0.90 | 0.75 |
| `qualitative_themes` | 0.88 | 0.75 |

They live in `FIELD_THRESHOLDS` — **one map, never scattered numerics in the
router**. They are **operational defaults to be calibrated against real
extraction quality**, not constants of nature.

---

## 6. Processing scope is a separate axis from evidence quality

`local_only` and `awaiting_consent` mean local deterministic extraction
completed and advanced extraction did not run — because the researcher declined
external processing, or has not decided yet.

**These are not failures, and a privacy decision must never surface as extraction
failure.** They also do not imply mineable scientific extraction exists. So
`processing_scope` is reported independently of evidence counts; collapsing the
two axes is what would misreport a consent-declining researcher as having a
broken thesis.

---

## 7. Conflicts — what is decidable, and what is deliberately deferred

**Implemented:** `sample_size`. Two different population counts for one study is
a contradiction with no reading that reconciles it. Detection reads integers
**with their sign** and in either Arabic-Indic or Western digits, so `"n = 310"`
and `"310"` and `"٣١٠"` agree, while `"0"`, `"-310"` and `"n = -310"` are refused
outright. An earlier pattern matched `\d+` only, which left the minus outside the
match and silently reinterpreted a negative as a valid positive count. On conflict, **only
`sample_size` is withheld** — unrelated evidence keeps mining and the thesis is
not blocked.

**Deferred, explicitly:**

- **`hypothesis_results` contradictions.** Detecting these correctly requires
  proving both results belong to *the same hypothesis identity*. The model
  carries no stable hypothesis identifier, so pairing would rest on text
  similarity.
- **Construct identity incompatibility.** Requires semantic judgement.

**No semantic similarity heuristic ships in T0.1.** A heuristic that guesses here
does not fail safely: it marks *correct, distinct* evidence as conflicting and
silently withholds it. A documented gap is better than a confident mislabel.

Reported as `conflicts_detected` and `facts_withheld_for_conflict`, **with no
document text in logs** — reasons are recorded by code and fact id only.

---

## 8. Human decisions outrank machine extraction, always

| Signal | Effect |
|---|---|
| `rejected` | `EXCLUDED` |
| `unknown` | `REVIEW_REQUIRED` |
| `approved` + verified same-file `ResearcherMemory` | highest trust |

**No history is deleted** — rows remain; only their eligibility changes.

How far a human decision reaches depends on whether the field can hold more than
one value, read from `FieldSpec.multi` in the existing catalogue rather than a
second list that would drift from it:

- **Singleton fields** (e.g. `title_ar`): a verified human decision **may suppress
  machine alternatives field-wide**. A thesis has one title; approving one settles
  the field.
- **Multi-value fields** (`questions`, `hypotheses`, `constructs`, `instruments`,
  `primary_findings`, `hypothesis_results`, `qualitative_themes`): approving one
  item **does not erase unrelated machine items** that merely share a `field_key`.
  Suppression there would need **deterministic item identity**, which the model
  does not carry — and **an unknown relation is not supersession**. So no
  suppression happens without it.

Field-wide suppression on a multi-value field was the earlier behaviour; it
discarded correct, distinct evidence for no reason beyond a shared key.

---

## 9. Precedence, and no escape hatch

1. approved + verified canonical
2. `AUTO_ELIGIBLE` machine facts
3. legacy `ThesisSection` / `ThesisResult` — **only when no mining-relevant
   canonical footprint owns the thesis**

**Ownership is mining-relevant, not merely "some extraction happened".** The
footprint is a `FactCandidate` whose `field_key` is in `READ_KEYS`. It holds even
when every such candidate ends up `SUPPORT_ONLY`, `REVIEW_REQUIRED` or
`EXCLUDED` — that is exactly what preserves `canonical_withheld`.

Candidates for **non-mining metadata only** (`page_count`, `source_filename`) do
**not** by themselves block legacy fallback: nothing extracted from them is
mineable, so blocking on them would refuse a legitimate legacy run on the
strength of an unrelated artefact.

**The modern footprint owns the thesis.** If mining-relevant canonical facts
exist but are low-confidence, conflicted or withheld, the pipeline does **not**
fall back to legacy tables. Doing so would convert a deliberate withholding into a silent
downgrade — publishing through the back door exactly what was refused at the
front. That state is reported as `canonical_withheld`.

**Legacy and canonical are never concatenated.**

---

## 10. Preserved inference guards

Unchanged from the previous contract, and still enforced:

- absence of a significance claim ≠ a null result
- a theme ≠ a study phase
- a thesis result ≠ a published result
- the thesis UUID ≠ a sample identity
- a missing variable ≠ an absent variable
- a missing external paper ≠ global novelty

---

## 11. Outcomes and the mining timestamp

`opportunities_created` · `already_present` ·
`eligible_evidence_but_no_opportunity` · `no_eligible_evidence` ·
`evidence_withheld_for_conflict` · `withheld_for_missing_title` ·
`legacy_evidence_but_no_opportunity`

**`eligible_evidence_but_no_opportunity` is the canonical zero-result outcome.**
`reviewed_evidence_but_no_opportunity` and `no_reviewed_canonical_evidence` were
retired with T0.1 and are **not emitted**: human review is no longer the condition
of eligibility, so naming it in the outcome would describe a policy the code does
not follow.

Audit reasons are written per `evidence_basis` for the same reason — `canonical`,
`legacy`, `canonical_withheld` and `none` each state what actually happened,
including that legacy fallback was *intentionally* suppressed in the withheld
case. **No document text appears in any of them.**

`opportunities_mined_at` is stamped **only when a real attempt ran on eligible
evidence** — including when that attempt legitimately found nothing. It is not
stamped when there was no eligible evidence, because the card would then read
"the scan completed and found no candidate opportunity" to a researcher whose
thesis was never actually scanned.

Audit events describe what occurred: `thesis.opportunities_mined` for a real
attempt, `thesis.opportunity_scan_skipped_no_evidence` otherwise.

---

## 12. T1 — the automatic pipeline (PR #115)

T0.1 settled *which facts are safe to mine*. T1 settles *who starts the mining*:
the system does, and the researcher's first decision is a scientific one.

### 12.1 The path, end to end

    upload
      → extraction
      → automatic eligibility classification (T0.1, §2)
      → automatic thesis-internal mining
      → mining state persisted on `theses` (migration 0031)
      → Thesis Center shows a real opportunity count
      → "View publication opportunities"
      → the researcher selects the scientific opportunity

**No per-fact approval is required anywhere on this path, and no manual mine
button appears on it.** High-confidence eligible machine facts feed the miner
automatically under the T0.1 gates (§§3, 5); the researcher is never asked to
sign intermediate extraction.

The trigger is `_mine_after_extraction` in
`services/document_intelligence/pipeline.py`, and it runs only where extraction
reached `AWAITING_REVIEW`. `local_only` and `awaiting_consent` never reach it: a
privacy decision is neither mined for nor reported as a mining failure.

### 12.2 What these opportunities are — and are not

Opportunities produced here are **preliminary and thesis-internal**, derived
from the elements of one thesis alone.

**Not in T1: literature validation, novelty judgement, and final ranking.** An
opportunity carries no claim that it is new, and no claim about its standing
against any other opportunity.

**The rights and authorship gate comes later** — when a researcher selects an
opportunity and it becomes a Paper Project. Nothing on the automatic path
advances a paper or assigns authorship.

### 12.3 Mining state is durable, and separate from extraction state

Migration `0031` adds `theses.mining_state` with five durable values:

`not_started` · `running` · `completed` · `withheld` · `failed`

**`running` is transaction-local in the current implementation and is not an
externally durable observable.** `mining.run` writes `running` and its terminal
value inside the same transaction, so no second session ever reads it. It is an
in-transaction guard, not a state the product can observe or recover from, and
the card reaches "in flight" from `processing_state` instead. Committing
`running` on its own would create stale-`running` rows after process death and
would need a recovery path — deliberately out of scope here, and named as a
limitation rather than left to be mistaken for a capability.

**A mining failure never rewrites a successful extraction.** Failure is recorded
on the mining axis alone and in its own transaction: `processing_state` stays
`ready_for_review`, and the fact candidates stay exactly as extraction left them.

### 12.4 Three different facts, three different things said

`failed`, `withheld` and `completed_empty` are **distinct product meanings**, and
the card never collapses them into one:

- **`failed`** — the scan broke. Extraction still succeeded, and a retry is
  offered.
- **`withheld`** — extracted knowledge exists, and some evidence was withheld
  from automatic use for confidence, consistency or evidence-integrity reasons
  (§§3, 7, 8). This is policy working as designed, not a defect, and **nothing
  needs the researcher's approval for the automation to run**. Review is
  optional quality control that may make more evidence usable.
- **`completed_empty`** — the card surface for a durable `completed` that
  produced nothing: the scan ran on eligible evidence and could not form a
  reliable opportunity. It does **not** claim that no publication opportunity
  exists, which is a statement about the world the system cannot support.

### 12.5 Manual mining is a recovery path, not the golden path

`POST /theses/{id}/mine-opportunities` remains, and the card offers it only
where a retry means something — `failed`, `withheld`, and the legacy path that
has no automation behind it. It is **absent on the golden path**, where
opportunities exist and the card's action is to open them.

---

## 13. Not in T1

Literature federation and validation · novelty validation · final opportunity
ranking · rights and authorship conversion of a selected opportunity into a
Paper Project · the Journey Orchestrator · G9 analysis provenance · AI idea
persistence · the reviewer and revision workflow.

**T0.1 governs what canonical thesis knowledge is safe to mine; T1 governs who
starts the mining and what the researcher is shown.** Neither makes any claim
about the published literature.

---

## 14. AI Journey V1 — who walks the path, and what each step costs

T1 settled *who starts the mining*. AI Journey V1 settles *what happens after
the researcher is shown opportunities*: the six-step path from a read thesis to
a manuscript the Paper Studio can open.

### 14.1 The six steps, and the sixteen states behind them

    thesis analysis → paper opportunities → rights and authorship
      → building the paper → literature update → Paper Studio

**There is no percentage anywhere on this path.** "60% complete" is a number
with no measurement behind it, and a researcher reads it as a promise. The
journey reports a *named state*, and every state is a row that can be pointed
at. `services/thesis/journey.py` holds the vocabulary; `derive_state` is a pure
function over `JourneyFacts`, and `load_facts` is the only impure layer.

`draft_ready` was retired. It was declared in the vocabulary and drawn on the
screen, and no branch of `derive_state` ever returned it — dead vocabulary that
survived because the guard compared two sets that both contained it. The guard
is now a **reachability** test: every state in `STATES` is one the function
actually returns.

### 14.2 Every fact is loaded, or the state built on it cannot occur

`JourneyFacts` has fourteen fields. Six were never populated —
`thread_ready`, `sections_drafted`, `sections_expected`, `literature_pending`,
and the two gate fields below. The consequence was not a wrong state but an
**absent** one: the journey froze at `manuscript_created` however much was
written into the manuscript, and three of the six steps could never become the
current step. A defaulted fact is not a neutral omission; it silently deletes
every state that depends on it.

### 14.3 Selection and rights are two gates, not one

`planning_status` is the researcher's decision — "is this the paper I want?" —
and `status` is the paper-production lifecycle. `models/thesis.py` separates
them deliberately, because merging them makes "rejected" mean two different
judgements made by two different people at two different moments.

The journey read **selection** out of the production lifecycle
(`status in {ready_to_submit, converted}`), which is the same condition it read
**rights** from. Two gates evaluating one condition are one gate:
`rights_required` could not occur, and the "rights and authorship" step was
never the current step at any moment of any journey.

Selection is now read from `planning_status`, and rights from the GT1 stamps
(`rights_approved_at` **and** `authorship_approved_at`) that
`rights.approve_gate` writes — the gate's own mark, not a state that resembles
it. An opportunity already advanced through GT1 still counts as selected: a
researcher does not approve authorship for a paper they did not choose.

### 14.4 The researcher could not select at all

The only decision endpoint was `POST /planning/{project_id}/publication-opportunities/{id}/decide`,
and it reads the opportunity with `project_id == project_id`. **A thesis-derived
opportunity has no project until it is converted**, so the one action T1's
contract ends on — "the researcher selects the scientific opportunity" — had no
door. Every thesis on the golden path stopped at step two permanently, with the
build control disabled forever because the server would never allow it.

`POST /theses/{id}/opportunities/{oid}/select` is that door. The write itself
lives in `services/thesis/selection.py` and **both** routers call it: two copies
of one decision drift apart at the first edit, and one of them would stop
recording what the other records.

### 14.5 A built paper the Studio can open

`Manuscript → ManuscriptVersion → ManuscriptSection` is a chain that does not
start from its middle. Every entry to the Paper Studio — overview, reading a
section, drafting it, approving it — resolves the current version first.
`build_paper` created a `Manuscript` with no version, so the journey's terminal
action offered "Open in Paper Studio" for a manuscript the Studio answered
`publishing.manuscript_not_found` for. The version is written with the
manuscript now, exactly as `manuscript_from_opportunity` has always written it.

### 14.6 The golden thread is reachable

`journey.build_thread` — the evidence-grounded model call whose unresolvable
references are rejected outright, never repaired — was written, tested and
called by nothing. It is now `POST /theses/{id}/opportunities/{oid}/thread`,
and takes no request-scoped transaction: the read closes, the model call runs
with no transaction open, and the write is its own.

### 14.7 What still does not happen

- **`ready_for_paper_studio` is not reachable from real rows yet.**
  `literature_validation_status` defaults to `pending` and nothing moves it,
  because the literature record is closed until S5F. So a completed draft
  honestly stops at "literature update" and names what it waits for. This is
  reported rather than hidden: the alternative — treating pending literature as
  satisfied — would announce a paper ready that is not.
- **The journey screen has no browser coverage.** Node is not available on this
  machine, so no Playwright spec was written for it and none was run. The
  Python-side checks pin the component's state map, its message keys, its
  controls and its bilingual copy against the server vocabulary; everything
  about its *behaviour in a browser* is unverified, and is stated so rather
  than presented otherwise.
- Literature federation and validation, novelty judgement, final ranking, the
  Journey Orchestrator, G9 analysis provenance, and the reviewer workflow remain
  outside this slice, as §13 says.
