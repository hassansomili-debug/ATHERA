# Production release runbook — guarded pipeline

**Workflow:** `.github/workflows/production-release.yml`
**Trigger:** manual only (`workflow_dispatch`). It is never fired by a push.

This runbook covers every production release. It describes infrastructure only.
**It cannot tell you the product is correct** — that is a separate acceptance
gate, described at the end.

---

## 0. The one invariant everything else serves

**Code is never deployed against a schema it cannot serve.**

Application code that declares a column cannot serve a schema that lacks it: the
first request returns `UndefinedColumnError` instead of a page. So the schema
must never be *behind* the code being deployed.

That yields two — and only two — legitimate release shapes:

| Mode | When | What happens |
|---|---|---|
| `code_only` | the release carries no new migration | the schema is read and compared, never written |
| `schema_and_code` | the release carries a new migration | migrate first, verify, then deploy |

**`code_only` refuses to run if the source's schema head is newer than
production.** That combination is precisely "deploy code the database cannot
serve", and it is the failure the ordering exists to prevent.

**`schema_and_code` refuses to run if there is nothing to migrate**, and tells
you to use `code_only`. That keeps the privileged migration credential out of
runs that have no use for it.

When a migration *is* applied, there is exactly one window — **the currently
deployed (older) code running on the new schema** — and job 3 proves that window
is safe before any new code is deployed. This is why additive, nullable
migrations are strongly preferred: the deployed code tolerates them.

---

## 1. One-time GitHub setup

### 1.1 Create the `production` environment

`Settings → Environments → New environment → production`

Every job that can write to production declares `environment: production`
(`db-release-gate`, `deploy-api`, `deploy-web`). Configure on that
environment:

- **Required reviewers** — add the owner. This is the human gate: the workflow
  pauses before the first job that can touch production and waits for approval.
- **Deployment branches** — restrict to `main`, so a release can never be run
  from a feature branch.

Without required reviewers the workflow still runs its own gates, but nobody is
asked before the migration. **Add the reviewer.**

### 1.2 Secrets — set every value in the `production` environment

Set these as **environment secrets** on `production`, not repository-wide, so
they are unavailable to workflows that do not declare the environment.

| Secret name | Where the value comes from |
|---|---|
| `DATABASE_MIGRATION_URL` | The privileged migration connection string — the value that lives locally in `.env.production.migration`. Supabase → Project Settings → Database → **Session pooler** connection string (`aws-<n>-<region>.pooler.supabase.com`), **port 5432**, using the **migration/owner** role (`postgres.<project-ref>`). Never the runtime role. See §4 for why the pooler and not the direct host. |
| `DATABASE_VERIFY_URL` | A connection string for the **runtime** role (`athera_app.<project-ref>`) on the **same session-pooler host, port 5432**, used only by the read-only verification scripts. |
| `ATHERA_DB_APP_PASSWORD` | The runtime role's password. Only needed if you prefer not to store a full URL: the verification script also accepts `PGHOST` / `PGUSER` / `PGPASSWORD` / `PGDATABASE` instead of `DATABASE_VERIFY_URL`. Set one path or the other. |
| `PRODUCTION_DB_HOST` | Database host, for that same alternative composition path. Optional if `DATABASE_VERIFY_URL` is set. |
| `ATHERA_DB_APP_USER` | Runtime role username, for that same alternative path. Optional if `DATABASE_VERIFY_URL` is set. |
| `FLY_API_TOKEN` | `flyctl tokens create deploy -a athera-api` — a deploy-scoped token, not a personal org-wide token. |
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens. Only needed if you choose the CLI deploy path (§5). |
| `VERCEL_ORG_ID` | Vercel project → Settings → General. Only for the CLI path. |
| `VERCEL_PROJECT_ID` | Vercel project → Settings → General. Only for the CLI path. |

**No value appears in this repository, in the workflow, or in any log.** The
workflow prints check names and results only; it never echoes a connection
string, never runs `set -x`, and never dumps the environment.

---

## 2. Running a release

`Actions → Production release — guarded → Run workflow`

| Input | What to enter |
|---|---|
| `expected_main_sha` | The full 40-character commit SHA on `main` you are releasing. Read it from `origin/main` now. **No SHA is recorded in this runbook** — a written example gets pasted long after it stopped being main's head. |
| `release_mode` | `code_only` (default) or `schema_and_code`. Choose the least privileged mode that does the job; see §0. |
| `expected_schema_before` | The alembic revision you have **just read out of production**, moments before dispatching. |
| `deploy_web` | `false` if Vercel Git integration already deploys `main` (§5). `true` only if you have turned that off. |

The workflow refuses to run if the SHA you typed is not currently the head of
`origin/main`. That is deliberate: if `main` moved, what you reviewed is not
what would ship.

### `expected_schema_before` is an attestation, not a setting

It has **no default, and this runbook prints no example value**, on purpose. A
revision written down anywhere becomes the next stale constant: correct the day
it is written, wrong after the next migration, and unnoticed until a release is
refused — which is exactly the defect that made an earlier version of this
workflow unusable.

Read the value from the database immediately before you dispatch, and type what
you saw. The run verifies your attestation against the live database and stops if
they disagree, so a careless value fails closed rather than proceeding on a
wrong assumption.

---

## 3. What each job does

**1 · Source preflight (read-only).** No production secret enters this job at
all. It verifies the checkout equals the input and equals `origin/main`; it
**derives the source schema head from the revision graph** — following
`revision` / `down_revision`, never filename order — and fails closed on zero
heads, more than one head, a missing parent, or a duplicate revision id; it
checks every tool the workflow later calls actually exists; and that `fly.toml`
still has **no `release_command`**, so deploying the API cannot silently
migrate.

**2 · Database release gate** (`environment: production`). **This job runs in
both modes**, so the jobs after it depend on it normally. A job that were skipped
outright would propagate its skip through `needs` and silently skip the deploy —
the very failure shape this pipeline exists to prevent.

Always, in both modes:

- **Read-only schema preflight.** Verifies live `alembic_version` equals your
  `expected_schema_before`, and that exactly one row is recorded. Nothing is
  written. In `code_only` this *is* the database gate.
- **Mode coherence check**, which runs before any credential exists:
  `code_only` requires the source head to equal production; `schema_and_code`
  requires them to differ. Either violation stops the run here.

Only in `schema_and_code`:

- Writes the migration credential to a runner-local file with mode 600 (§4).
- Applies the migration via `scripts/migrate_production.py`.
- Proves the result: `alembic_version` equals the derived source head, exactly
  one row, RLS still `ENABLE` **and** `FORCE` on tenant tables, and the runtime
  role `athera_app` has neither `rolsuper` nor `rolbypassrls`.
- Runs `scripts/verify_db_constraints.py`, which attempts every forbidden
  operation and fails if any succeeds. **It is write-capable**, so it does not
  run on a path that writes nothing.

Always: deletes the credential file in an `always()` step, whether or not one was
ever written.

**3 · Currently deployed API healthy on the verified schema.** Probes `/healthz`
and `/readyz` on `athera-api.fly.dev` **before** the new API deploys. `/readyz`
is the meaningful one: it returns 503 unless the runtime role has
`rolsuper=false` and `rolbypassrls=false`. After a migration this proves the
older deployed code survives the new schema; in `code_only` it proves what is
running now is healthy before you replace it.

**4 · Deploy API to Fly.** Deploys the exact release commit to `athera-api`,
labelled with the release SHA, then polls health until it passes. This job never
migrates.

**5 · Deploy Web to Vercel** — only if `deploy_web` is `true`. See §5.

**6 · Public smoke.** Non-destructive, unauthenticated probes only, then writes
the run summary.

---

## 4. Why `make migrate-prod`, and why the credential goes into a file

`make migrate` is `cd infra/db && alembic upgrade head`. **It is a local
development command and must never be pointed at production.** It knows none of
the guards below.

The production entry point is `make migrate-prod CONFIRM=<project-ref>`, which
wraps `scripts/migrate_production.py`. That script exists because of a real
incident: the migration credential once lived in the general `.env`, which was
loaded implicitly by every command run from the repository root — and a `pytest`
run consequently reached the production database. So the script:

- reads `DATABASE_MIGRATION_URL` **from a file** (`.env.production.migration` by
  default, overridable with `--env-file`) that nothing loads automatically;
- refuses if the target looks local;
- refuses if the URL uses the runtime role `athera_app`, keeping a BYPASSRLS
  role out of `DATABASE_URL`;
- **requires `--confirm <project-ref>` to match the project reference parsed out
  of the URL itself.** This is the anti-typo guard: a production migration is
  never a typo.

  The workflow supplies that value from a **reviewed constant** in
  `production-release.yml` (`PRODUCTION_SUPABASE_PROJECT_REF`), **not from a
  secret**. A project reference is an identifier, not a credential — it opens
  nothing and authenticates nobody, and it appears in every Supabase dashboard
  URL. It was previously a second secret, which meant one identity written in
  two hand-edited places; the two drifted, and eight release runs were refused
  at this guard. **The guard itself is unchanged** — it still compares the
  constant against the reference inside the URL, and still refuses if they
  differ. What changed is that the comparison now has one reviewed source
  instead of two.

In GitHub Actions the secret arrives as an environment variable, not a file. The
workflow therefore writes it to `${RUNNER_TEMP}/.env.production.migration` under
`umask 077` with `chmod 600`, passes `--env-file`, never echoes it, and removes
it in an `if: always()` step.

**Why port 5432 and not 6543 — and why the pooler host, not the direct host.**

6543 is Supabase's **transaction** pooler: it does not guarantee that
consecutive statements land on the same session. Alembic's version lock,
`SET LOCAL` tenant context, and the migration itself all assume one session.
**Port 6543 is forbidden for both migration and verification**, and the
verification script refuses any `DATABASE_VERIFY_URL` naming another port.

Port 5432 on `aws-<n>-<region>.pooler.supabase.com` is the **session** pooler:
one session per connection, which is exactly what those mechanisms need.

**Use that host, not the direct one.** An earlier version of this runbook called
port 5432 "the direct port", which led to `db.<ref>.supabase.co` — and that host
is **IPv6-only**, while GitHub-hosted runners are IPv4-only. A release run failed
with `connection to server at "2406:da1a:..." failed: Network is unreachable`.
The session pooler resolves to IPv4 and is reachable from Actions. It is also
what makes the `--confirm` guard work as documented: the pooler username is
`postgres.<project-ref>`, so the reference the script parses **is** the project
ref; on the direct host the username is bare `postgres`, and the script falls
back to comparing the whole hostname instead.

---

## 5. Vercel: pick one deploy path — **owner action required**

`apps/web/vercel.json` contains `"github": { "silent": true }`. **`silent` only
suppresses Vercel's PR comments; it does not disable deploys.** So if the Vercel
Git integration is connected to this repository, **merging to `main` already
deploys Web** — with no coordination with the database or API.

> **This breaks the migrate-first invariant.** A Web bundle that ships on merge
> can take traffic before the database is at the release's schema head and
> before the new API is deployed. Users would hit a front end whose
> backend cannot serve it.

You must choose **one** authoritative path:

**Option A — Git integration is authoritative (no change to Vercel).**
Run this workflow with `deploy_web: false`. Accept that Web ships at merge time,
and therefore **do not merge a release to `main` until you are ready to migrate
and deploy immediately after.** Keep the merge-to-release gap short.

**Option B — this workflow is authoritative (recommended for ordered releases).**
In Vercel → Project → Settings → Git, **disable production deployments for the
`main` branch** (turn off automatic deployments, or set Ignored Build Step to
skip). Then run this workflow with `deploy_web: true`. Web then ships only after
the API is verified healthy, preserving the ordering.

**This workflow does not and cannot change your Vercel settings.** Option B
requires the owner to turn Git auto-deploy off first; until then, leave
`deploy_web: false` or you will double-deploy.

---

## 6. What a blocked migration means

If job 2 stops in its read-only preflight or its mode check, **nothing was
written** — both run before any credential exists. It means one of:

- **production disagrees with your `expected_schema_before`.** Either you typed a
  value you did not just read, or it is not the database you think it is. Read
  the live revision again and start over; do not adjust the input to make the run
  proceed.
- **`code_only` was chosen but the source carries a newer migration.** The
  release includes schema work. Dispatch it as `schema_and_code`, or release an
  earlier commit.
- **`schema_and_code` was chosen but the source head already equals
  production.** There is nothing to migrate; dispatch as `code_only` so the
  migration credential is never materialised.
- **`alembic_version` has more than one row** — a branched history was merged
  without resolution, and `upgrade head` would be ambiguous.

In every case the correct response is to stop and look, not to re-run and not to
edit the input until it passes.

---

## 7. The database is never auto-downgraded

If job 3, 4, 5 or 6 fails **after** a migration succeeded, the schema stays where
the migration left it and the workflow fails loudly.

This is deliberate. An additive migration is tolerated by the previously deployed
code — which is why job 3 proves exactly that — so sitting at the new schema with
the old code deployed is a **safe, serviceable state**. An automatic downgrade,
by contrast, would run destructive DDL during an incident, at the moment when
least is understood. Downgrading is a separate, human
authorized operation — `make migrate-down`, run deliberately, by a person who has
read what failed.

---

## 8. Reading the run summary

The final job writes a table to the run summary: release SHA, repository head,
schema before and after, what was verified in the database, the old-API
compatibility result, the API deploy and health result, the Web result (or
`skipped`), and the smoke result. It contains no secrets.

It ends with:

```
INFRA RELEASE GREEN — PRODUCT ACCEPTANCE REQUIRED
```

Read that literally.

---

## 9. Product acceptance is a separate gate

This workflow performs **no authenticated journey**. It proves that the schema
migrated correctly, that the old API survived the migration, that the new API
deployed and reports healthy, and that public URLs respond.

It proves nothing about whether a researcher can upload a thesis, review
extraction, archive a record, or restore one.

**Nobody may declare a wave PRODUCTION GREEN on the strength of this workflow.**
The release order is:

1. Read the live schema revision out of production.
2. Choose the mode: `schema_and_code` if the release carries a migration,
   `code_only` if it does not.
3. Migrate (if any) and verify the resulting schema.
4. Deploy API, and Web by whichever single path is authoritative (§5).
5. **Run production acceptance.**
6. Declare the wave PRODUCTION GREEN only after production acceptance passes.
7. Do not begin the next wave's deployment until the current one is confirmed
   GREEN.

Steps 1–4 are what this workflow automates. Steps 5 and 6 are human.

---

## 10. Known repository finding

`docs/runbooks/deploy-supabase-vercel.md` instructed operators to run
`python scripts/verify_audit_chain.py`. **That script does not exist anywhere in
this repository.** An operator following that runbook would hit
`No such file or directory` mid-release.

This pipeline does not call it. The stale line has been marked in that runbook
rather than silently deleted, because the intent behind it — verifying the audit
hash chain in production — is legitimate and still unimplemented. Writing that
verifier is separate work; it is not part of this release infrastructure.
