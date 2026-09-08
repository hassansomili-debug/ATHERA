# Thesis Automation Contract — what canonical knowledge is safe to mine

**Status:** T0.1. Implemented in `apps/api/athera_api/services/thesis/fact_eligibility.py`
and consumed by `services/thesis/canonical_facts.py`.

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
a contradiction with no reading that reconciles it. Detection normalises to the
first integer, so `"n = 310"` and `"310"` agree. On conflict, **only
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

When the researcher has decided a concept, later machine extraction for that same
field is superseded and stops grounding anything. **No history is deleted** — the
rows remain; only their eligibility changes.

Supersession is applied **at field level**, because that is what the model
actually represents. No semantic supersession relation is invented.

---

## 9. Precedence, and no escape hatch

1. approved + verified canonical
2. `AUTO_ELIGIBLE` machine facts
3. legacy `ThesisSection` / `ThesisResult` — **only when the thesis has no modern
   canonical footprint at all**

**The modern footprint owns the thesis.** If canonical facts exist but are
low-confidence, conflicted or withheld, the pipeline does **not** fall back to
legacy tables. Doing so would convert a deliberate withholding into a silent
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

`opportunities_mined_at` is stamped **only when a real attempt ran on eligible
evidence** — including when that attempt legitimately found nothing. It is not
stamped when there was no eligible evidence, because the card would then read
"the scan completed and found no candidate opportunity" to a researcher whose
thesis was never actually scanned.

Audit events describe what occurred: `thesis.opportunities_mined` for a real
attempt, `thesis.opportunity_scan_skipped_no_evidence` otherwise.

---

## 12. Not in T0.1

Automatic pipeline triggering · Thesis Center UI · auto-calling
`mine-opportunities` after extraction · literature update · opportunity ranking ·
rights and authorship · the Journey Orchestrator.

**This contract changes only what canonical thesis knowledge is safe to mine.**
