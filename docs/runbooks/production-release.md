# Production release runbook — guarded pipeline

**Workflow:** `.github/workflows/production-release.yml`
**Trigger:** manual only (`workflow_dispatch`). It is never fired by a push.

This runbook covers the release of Wave 1.1 and every release after it. It
describes infrastructure only. **It cannot tell you the product is correct** —
that is a separate acceptance gate, described at the end.

---

## 0. The one invariant everything else serves

**Migrate first, then deploy.**

Wave 1.1's code declares `theses.archived_at` and `theses.archived_by`, so
SQLAlchemy selects them on every read of `theses`. That code **cannot serve any
schema below `0030`** — deploy it first and the Thesis Center's first request
returns `UndefinedColumnError: column theses.archived_at does not exist`.

The currently deployed API (v88) has no archive columns in its model at all,
writes `theses` with its own explicit column list, and never reads an archive.
`0030` is additive and both columns are nullable, so v88 keeps working on the
new schema — both columns simply stay `NULL`, which means "not archived", the
correct state for everything v88 writes.

So there is exactly one window — **old code on the new schema** — and job 3
proves it is safe before any new code is deployed.

---

## 1. One-time GitHub setup

### 1.1 Create the `production` environment

`Settings → Environments → New environment → production`

Every job that can write to production declares `environment: production`
(`db-migrate`, `deploy-api`, `deploy-web`). Configure on that environment:

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
| `DATABASE_MIGRATION_URL` | The privileged migration connection string — the value that lives locally in `.env.production.migration`. Supabase → Project Settings → Database → connection string, using the **migration/owner** role, **port 5432**. Never the runtime role. |
| `SUPABASE_PROJECT_REF` | The Supabase project reference (the identifier after `postgres.` in the pooler username, or the project ref in the dashboard URL). See §4 for why this is required. |
| `DATABASE_VERIFY_URL` | A connection string for the **runtime** role `athera_app`, **port 5432**, used only by the read-only verification scripts. Compose it from the same host with the runtime role and its password. |
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
| `expected_main_sha` | The full 40-character commit SHA on `main` you are releasing. **Wave 1.1 = `9195850dc6ff87f726801a05e02b6fd814846c13`** |
| `deploy_web` | `false` if Vercel Git integration already deploys `main` (§5). `true` only if you have turned that off. |

The workflow refuses to run if the SHA you typed is not currently the head of
`origin/main`. That is deliberate: if `main` moved, what you reviewed is not
what would ship.

---

## 3. What each job does

**1 · Source preflight (read-only).** No production secret enters this job at
all. It verifies the checkout equals the input and equals `origin/main`; that
`infra/db/migrations/versions/0030_thesis_archive.py` exists and declares
`revision = "0030"` / `down_revision = "0029"`; that the migration graph has
**exactly one head** and it is `0030`; that every tool the workflow later calls
actually exists; and that `fly.toml` still has **no `release_command`**, so
deploying the API cannot silently migrate.

**2 · Database preflight and migration** (`environment: production`). Writes the
migration credential to a runner-local file with mode 600 (see §4), then:

- **Gate: refuses to migrate unless `alembic_version` is exactly `0029`.** This
  runs *before* any write. See §6.
- Applies the migration via `scripts/migrate_production.py`.
- Proves the result: `alembic_version == 0030`, exactly one row, the archive
  columns exist and are nullable, `ck_theses_archive_is_named` exists,
  `ix_theses_tenant_live_page` exists, RLS is still `ENABLE` **and** `FORCE` on
  tenant tables, and the runtime role `athera_app` has neither `rolsuper` nor
  `rolbypassrls`.
- Runs `scripts/verify_db_constraints.py`, which attempts every forbidden
  operation and fails if any succeeds.
- Deletes the credential file in an `always()` step.

**3 · Old API healthy on schema 0030.** Probes `/healthz` and `/readyz` on
`athera-api.fly.dev` **before** the new API deploys. `/readyz` is the meaningful
one: it returns 503 unless the runtime role has `rolsuper=false` and
`rolbypassrls=false`. If the already-deployed v88 cannot serve `0030`, the
release stops here rather than deploying on top of a broken state.

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
  of the URL itself.** This is the anti-typo guard, and it is why
  `SUPABASE_PROJECT_REF` is a required secret beyond the connection string:
  without it the script refuses to run at all.

In GitHub Actions the secret arrives as an environment variable, not a file. The
workflow therefore writes it to `${RUNNER_TEMP}/.env.production.migration` under
`umask 077` with `chmod 600`, passes `--env-file`, never echoes it, and removes
it in an `if: always()` step.

**Why port 5432 and not 6543.** 6543 is Supabase's transaction pooler: it does
not guarantee that consecutive statements land on the same session. Alembic's
version lock, `SET LOCAL` tenant context, and the migration itself all assume one
session. Use the direct port. The verification script refuses a
`DATABASE_VERIFY_URL` that names any other port.

---

## 5. Vercel: pick one deploy path — **owner action required**

`apps/web/vercel.json` contains `"github": { "silent": true }`. **`silent` only
suppresses Vercel's PR comments; it does not disable deploys.** So if the Vercel
Git integration is connected to this repository, **merging to `main` already
deploys Web** — with no coordination with the database or API.

> **This breaks the migrate-first invariant.** A Web bundle that ships on merge
> can take traffic before the database is at `0030` and before the new API is
> deployed. Users would hit a front end whose backend cannot serve it.

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

If job 2 stops at *"refuse to migrate unless production is exactly at 0029"*,
**nothing was written.** The gate runs before any write. It means one of:

- the database is already at `0030` — the migration ran before; skip to
  deploying, do not force anything;
- the database is at some other revision — it is not the database you think it
  is, or it is behind; investigate before doing anything;
- `alembic_version` has more than one row — a branched history was merged without
  resolution, and `upgrade head` would be ambiguous.

In all three cases the correct response is to stop and look, not to re-run.

---

## 7. The database is never auto-downgraded

If job 3, 4, 5 or 6 fails **after** the migration succeeded, the schema stays at
`0030` and the workflow fails loudly.

This is deliberate. `0030` is additive and the old v88 API tolerates it, so
sitting at `0030` with the old code deployed is a **safe, serviceable state**. An
automatic downgrade, by contrast, would run destructive DDL during an incident,
at the moment when least is understood. Downgrading is a separate, human
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

**Nobody may declare `WAVE 1.1 PRODUCTION GREEN` on the strength of this
workflow.** The release order is:

1. Production is at schema `0029`, API v88.
2. Apply `0029 → 0030`.
3. Verify schema head is `0030`.
4. Deploy Wave 1.1 API and Web.
5. **Run production acceptance.**
6. Declare `WAVE 1.1 PRODUCTION GREEN` only after production acceptance passes.
7. Do not begin Wave 2-A deployment until Wave 1.1 production is confirmed
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
