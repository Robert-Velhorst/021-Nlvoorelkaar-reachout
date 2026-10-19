# NLvoorelkaar Reachout

NLvoorelkaar Reachout is a local-first outreach operations tool for people who
need to contact potential volunteers through a careful, auditable, human-reviewed
workflow.

It was originally a desktop automation prototype. It has since been hardened
into an operator application with a shared backend, a desktop GUI, an
authenticated web dashboard, command-line tools, a read-only HAI feed, SQLite
storage, privacy controls, release packaging, and CI/security gates.

The central rule is simple: the app may help an operator organize outreach, draft
messages, track replies, and keep evidence, but it does not silently send
messages or claim provider access. Live NLvoorelkaar actions are disabled by
default and require explicit feature flags plus a private written authorization
record for the exact action being attempted.

## Who This Repository Is For

This repository is useful for three groups:

- Non-technical operators who want a safer way to manage volunteer outreach,
  review every message before it is sent, track responses, and keep a privacy
  record.
- Software developers who need to maintain, test, extend, package, or audit the
  application.
- Technical owners who need to understand exactly which external systems are
  involved, which credentials are needed, what remains blocked, and what evidence
  proves the local application works.

## Plain-English Summary

NLvoorelkaar Reachout helps an operator:

1. Import a reviewed list of candidate volunteers from CSV or JSON.
2. Create an outreach campaign.
3. Generate personalized message drafts from a campaign template.
4. Review, edit, approve, or reject each exact draft.
5. Send messages manually and record proof, or explicitly enable bounded live
   sending after written provider approval.
6. Record replies and follow-up tasks.
7. Review old records for archive or redaction.
8. Make verified backups and privacy-safe support bundles.
9. Share a privacy-minimized read-only work feed with HAI.

The app is built for assistance and traceability, not autonomous mass messaging.
The safest and default mode is local-only/manual-send mode.

## What This Is Not

This repository is not:

- An official NLvoorelkaar product.
- A guarantee that NLvoorelkaar permits automated login, search, or messaging.
- A scraper that should be run without current written platform approval.
- A bulk sender.
- A SaaS product with multi-tenant accounts.
- A tool that can revoke historically exposed credentials for you.
- A replacement for the operator's privacy, consent, and platform-policy
  responsibilities.

Any live provider use must be separately validated by the owner/operator against
current NLvoorelkaar terms, account permissions, selectors, rate limits, and
message confirmation behavior.

## Current Release Shape

- Application version: `3.1.0`
- Runtime model: single-operator, local-first application
- Primary platform: Windows desktop
- Supported Python: `3.10`, `3.11`, and `3.12`
- Unsupported Python: `3.13+` and machine-default `3.14` are rejected by the
  launcher
- Database: local SQLite with schema migrations and foreign keys
- Web interface: FastAPI plus compiled React/Vite assets
- CLI: `nlve_cli.py` and packaged `NLVE-Operator.exe`
- Desktop GUI: Python desktop application entry point
- Release packaging: unsigned Windows ZIP, SHA-256 checksum, SBOM, and GitHub
  Actions provenance
- External network features: disabled by default

## Major Features

### Candidate Intake

Candidates can be imported from reviewed CSV or JSON files. Imports are local,
audited, and idempotent by volunteer ID. Importing candidates does not contact
NLvoorelkaar.

Accepted identifiers include:

- `volunteer_id`
- legacy `profile_id`

Useful optional fields include:

- `name`
- `location`
- `description`
- `skills`
- `categories`
- `availability`
- `contact_info`
- `profile_url`

### Campaigns and Drafts

Operators create campaigns with a target location/category, description, and
message template. The shared application service creates reviewable message
drafts and stores the exact rendered message snapshot for approval.

### Human Review Gate

Every draft must be reviewed before completion. Approval and rejection require a
non-empty reason. Manual send completion requires operator-entered evidence.

The app is intentionally strict here: it does not infer that a message was sent
from a UI state, local assumption, or provider-side ambiguity.

### Assisted Sending

The default delivery model is assisted/manual:

1. The operator approves the exact message.
2. The operator sends it through the appropriate channel.
3. The operator records evidence that delivery was accepted.
4. The app stores that evidence in the local audit trail.

### Optional Live Provider Actions

Live NLvoorelkaar login/search/send paths are fail-closed. They require all of
the following:

- `NLVE_ENV=production`
- the specific live feature flag enabled
- conservative rate and batch limits
- a private provider approval JSON file outside the repository
- provider approval that names the exact action, such as `login`, `search`, or
  `send`
- successful provider preflight validation

Tests cannot enable live provider actions. `NLVE_ENV=test` rejects external
provider flags.

### Responses and Follow-Ups

Operators can record responses, classify outcomes, queue follow-ups, approve
follow-up messages, and record follow-up send evidence. Follow-ups use persisted
message snapshots so approved content is not rebuilt from mutable campaign data.

### Safety Stop

The durable Safety Stop blocks new provider actions and blocks manual completion
flows that would make outreach state progress while the stop is active. It also
requests cancellation of active work. It cannot retract a request already
accepted by an external provider.

If a provider send result is ambiguous, the app records
`external_outcome_unknown`. The operator must inspect provider history before
retrying.

### Privacy Controls

The app supports:

- reviewed volunteer export
- retention candidate review
- archive decisions
- redaction decisions
- privacy-safe support bundles
- backups that exclude credential, token, session, and runtime-only files

Retention proposals do not delete automatically. Archive and redaction require
explicit operator action and an audit reason.

### Backups and Restore Safety

Local backup and restore are built around safety checks:

- filtered backup contents
- traversal checks
- symlink checks
- compression expansion checks
- staging before restore
- rollback backup before restore
- restore abort if rollback protection cannot be created

### Google Drive Backup

Google Drive support is optional and disabled by default. It uses the `drive.file`
scope and is intended for app-created backup files only.

Creating the Drive manager has no authentication, browser, refresh-token, or
remote-write side effects. Upload is an explicit operator action after a verified
local backup exists.

### Authenticated Web Dashboard

The web UI exposes the same local application service as the desktop and CLI.
It includes views for:

- Dashboard
- Candidate Intake
- Campaigns
- Messages
- Responses
- Follow-ups
- Privacy
- Operations

The API uses bearer authentication, disables public docs, applies trusted-host
checks, sets defensive browser headers, limits request rates, and bounds uploads
and pagination.

### HAI Connector

The HAI integration is read-only and privacy-minimized. It can expose review work
and stable references, but it does not expose message bodies, volunteer names,
contact details, credentials, provider approval evidence, or execution authority.

HAI cannot approve drafts, send messages, clear Safety Stop, change retention, or
mutate NLvoorelkaar Reachout.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `main.py` | Desktop application entry point. |
| `run.py` | Runtime launcher with supported-Python guard. |
| `nlve_cli.py` | Operator CLI commands such as doctor, smoke, backup, serve, and HAI sync. |
| `nlve_operator.py` | Packaged operator entry point. |
| `services/application_service.py` | Transport-independent use-case boundary shared by desktop, web, CLI, and HAI. |
| `services/outreach_ledger.py` | Campaign, draft, approval, send, response, follow-up, outcome, privacy, and HAI projection logic. |
| `services/provider_policy.py` | Written-provider-approval validation and evidence hashing. |
| `services/diagnostics.py` | Doctor, smoke, backup, support bundle, and local readiness tooling. |
| `database/database_manager.py` | SQLite schema, migrations, health checks, and database primitives. |
| `web_api/app.py` | FastAPI transport and static React app serving. |
| `web/` | React/Vite source for the browser operator UI. |
| `web_api/static/` | Compiled web assets packaged with the Python app. |
| `connectors/hai_bridge.py` | Authenticated HAI Generic JSON Feed writer. |
| `google_drive/google_api_services.py` | Optional explicit Google Drive backup adapter. |
| `scripts/start-web.ps1` | Starts the loopback web server. |
| `scripts/build-release.ps1` | Builds the unsigned Windows release archive, checksum, and SBOM. |
| `scripts/check_repository_safety.py` | Rejects committed runtime data, credentials, tokens, and unsafe paths. |
| `docs/` | Operator, API, deployment, security, audit, verification, and roadmap documentation. |
| `tests/` | Backend, workflow, API, safety, performance, and regression tests. |
| `config/runtime.env.example` | Safe environment variable template. |
| `config/provider_authorization.example.json` | Schema template for private provider approval records. |

## Data Stored Locally

Runtime data is local by default and belongs in ignored paths such as:

- `data/`
- `logs/`
- `backups/`
- private files referenced by environment variables

The local database may contain:

- volunteer IDs
- profile URLs and profile text
- locations, skills, categories, and availability
- message drafts and exact approved snapshots
- operator review reasons
- manual send evidence
- responses and follow-up records
- privacy decisions
- audit events

Do not commit runtime data, provider approvals, logs, databases, OAuth files,
tokens, exports, or backup archives.

## Supported Runtime

Required:

- Windows for the supported desktop/operator release path
- Python `3.10`, `3.11`, or `3.12`
- `pip`
- local filesystem access for the SQLite database and backups

Optional:

- Node.js `24` when rebuilding the web frontend from source
- NLvoorelkaar account for explicitly approved live login/search/send
- newly rotated Google OAuth desktop credentials for explicitly enabled Drive
  backup

The launcher intentionally rejects unsupported Python versions. If `python` on a
machine points to Python `3.14`, use a supported Python executable instead.

## Quick Start: Local Desktop

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

The launcher never installs packages automatically. If dependencies are missing,
it reports the problem and exits.

## Quick Start: CLI

```powershell
python -m pip install -r requirements.txt
python nlve_cli.py doctor
python nlve_cli.py smoke
```

Installed console scripts are also available when the package is installed:

```powershell
nlve doctor
nlve smoke
nlve-gui
```

Important CLI commands:

| Command | Purpose |
| --- | --- |
| `doctor` | Check local readiness without provider network calls. |
| `smoke` | Run the isolated network-free critical path. |
| `reconcile-sends` | Mark stale ambiguous sends for operator reconciliation. |
| `import-volunteers` | Import reviewed CSV/JSON candidate data. |
| `export-volunteers` | Export active volunteer data. |
| `backup` | Create and verify a privacy-filtered local backup. |
| `support-bundle` | Create a privacy-safe diagnostic ZIP. |
| `provider-preflight` | Validate a private provider approval record without network access. |
| `hash-approval-evidence` | Compute the SHA-256 used by a provider approval record. |
| `serve` | Run the authenticated web application. |
| `hai-sync` | Write an authenticated HAI Generic JSON Feed. |

## Quick Start: Web UI

Generate a private token of at least 32 characters, then start the local web app:

```powershell
$env:NLVE_WEB_API_TOKEN = "use-a-private-random-value-of-at-least-32-characters"
.\scripts\start-web.ps1 -Port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Enter the same bearer token in the login screen. The browser stores the token in
session storage, not local storage, so it is cleared when the tab session ends or
the operator disconnects.

## Hetzner deployment

Public hosting targets Hetzner. Keep workstation runs on loopback and follow `DEPLOYMENT_TARGET.md` and the deployment runbook for public HTTPS. This repository no longer ships a workstation tunnel.

## Safe Production Defaults

Start from `config/runtime.env.example` and keep private values outside the
repository:

```powershell
$env:NLVE_ENV = "production"
$env:NLVE_LIVE_SEARCH_ENABLED = "0"
$env:NLVE_LIVE_SEND_ENABLED = "0"
$env:NLVE_GOOGLE_DRIVE_ENABLED = "0"
$env:NLVE_MAX_SEARCH_PAGES = "5"
$env:NLVE_MAX_SEND_BATCH = "5"
$env:NLVE_DAILY_SEND_LIMIT = "20"
```

These defaults allow local intake, review, manual-send evidence, responses,
follow-ups, privacy actions, local backups, diagnostics, web UI, and HAI feed.
They do not enable provider automation.

## Enabling Live NLvoorelkaar Actions

Live provider actions require a private authorization record based on
`config/provider_authorization.example.json`.

1. Obtain written platform approval that names the approved account and exact
   actions.
2. Store the completed approval JSON and supporting evidence outside the
   repository.
3. Hash the evidence file:

```powershell
python nlve_cli.py hash-approval-evidence C:\private\approval-email.pdf
```

4. Put the hash in the private approval JSON.
5. Validate the approval record:

```powershell
python nlve_cli.py provider-preflight C:\private\nlvoorelkaar_provider_approval.json --action search --action send
```

6. Set:

```powershell
$env:NLVE_PROVIDER_APPROVAL_PATH = "C:\private\nlvoorelkaar_provider_approval.json"
$env:NLVE_LIVE_SEARCH_ENABLED = "1"
$env:NLVE_LIVE_SEND_ENABLED = "1"
```

Only enable the action flags that are actually approved and needed. Keep search
pages, send batches, and daily send limits conservative.

## Google Drive Backup

Drive backup is disabled by default:

```powershell
$env:NLVE_GOOGLE_DRIVE_ENABLED = "0"
```

To enable it, use newly rotated private OAuth credentials:

```powershell
$env:NLVE_GOOGLE_DRIVE_ENABLED = "1"
$env:NLVE_GOOGLE_CLIENT_SECRET_PATH = "C:\private\google_credentials.json"
$env:NLVE_GOOGLE_TOKEN_PATH = "C:\private\google_token.json"
```

Do not reuse any OAuth client, token, refresh token, or access token that was
historically committed. Treat historically exposed Google material as
compromised until the owner revokes and rotates it in Google Cloud.

## Import, Export, Backup, and Support Examples

Import reviewed candidates:

```powershell
python nlve_cli.py import-volunteers C:\private\reviewed-candidates.csv
```

Export active volunteers:

```powershell
python nlve_cli.py export-volunteers C:\private\volunteers.json --format json
```

Create a verified backup:

```powershell
python nlve_cli.py backup --name before-maintenance
```

Create a privacy-safe support bundle:

```powershell
python nlve_cli.py support-bundle C:\private\nlve-support.zip
```

Reconcile ambiguous sends:

```powershell
python nlve_cli.py reconcile-sends --minutes 15
```

## Web API Summary

The FastAPI app in `web_api/app.py` exposes the shared application service.

Authentication:

- `GET /healthz` is unauthenticated for health checks.
- Every `/api/v1/*` route requires `Authorization: Bearer <token>`.
- `NLVE_WEB_API_TOKEN` must be at least 32 characters.
- OpenAPI, Swagger UI, and ReDoc are disabled.

Important read routes:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/status` | Runtime, database, provider, HAI, and Safety Stop state. |
| `GET` | `/api/v1/dashboard` | Operating summaries and current queues. |
| `GET` | `/api/v1/volunteers` | Paginated candidate records. |
| `GET` | `/api/v1/campaigns` | Campaign list. |
| `GET` | `/api/v1/messages/review` | Drafts requiring review. |
| `GET` | `/api/v1/messages?message_status=approved` | Approved drafts awaiting completion. |
| `GET` | `/api/v1/responses` | Recorded response inbox. |
| `GET` | `/api/v1/follow-ups` | Follow-up queue. |
| `GET` | `/api/v1/privacy/retention` | Retention review candidates. |
| `GET` | `/api/v1/hai/feed` | Privacy-minimized HAI feed. |

Important mutation routes:

| Method | Route | Evidence required |
| --- | --- | --- |
| `POST` | `/api/v1/volunteers/import` | Reviewed CSV or JSON file. |
| `POST` | `/api/v1/campaigns` | Campaign fields and template. |
| `POST` | `/api/v1/campaigns/{id}/drafts` | Optional bounded volunteer ID list. |
| `POST` | `/api/v1/messages/{id}/approve` | Review reason. |
| `POST` | `/api/v1/messages/{id}/reject` | Review reason. |
| `POST` | `/api/v1/messages/{id}/confirm-manual-send` | Operator-observed delivery evidence. |
| `POST` | `/api/v1/responses` | Volunteer ID, campaign ID, and response content. |
| `POST` | `/api/v1/follow-ups/{id}/approve` | Persisted suggested follow-up snapshot. |
| `POST` | `/api/v1/follow-ups/{id}/confirm-manual-send` | Operator-observed delivery evidence. |
| `POST` | `/api/v1/privacy/retention/{id}/archive` | Retention decision reason. |
| `POST` | `/api/v1/privacy/retention/{id}/redact` | Retention decision reason. |
| `PUT` | `/api/v1/operations/safety-stop` | Explicit active/clear state. |

See `docs/API_DOCUMENTATION.md` for the full API contract.

## Security Model

Important controls:

- external provider flags are off by default
- live provider actions require a private written approval record
- exact message snapshots are approved before completion
- manual send completion requires evidence
- atomic send claims avoid duplicate sends
- stale ambiguous sends are reconciled instead of retried automatically
- durable Safety Stop blocks new provider actions
- web API uses bearer auth and constant-time token comparison
- trusted-host middleware restricts public hostnames
- CSP, `no-store`, frame denial, and other defensive headers are applied
- public API docs are disabled
- no broad CORS grant is configured
- uploads and list routes are bounded
- backups filter sensitive and runtime-only files
- repository safety checks reject tracked credentials, tokens, logs, databases,
  backups, build output, and completed provider approvals
- dependency audits run in local verification and CI
- CodeQL runs in GitHub Actions

See `docs/SECURITY_AND_PRIVACY.md` for the threat model and privacy design.

## Historical Credential Incident

Older history contained Google OAuth material. Source cleanup and history hygiene
have been performed, but rewriting history is not the same as revoking a
credential.

The owner must still:

- revoke exposed Google OAuth clients and tokens
- rotate replacement credentials
- inspect Google Cloud/OAuth activity
- avoid reusing any historically committed secret

Do not dismiss secret-scanning alerts as false positives unless the owner has
confirmed revocation and rotation.

## Development Setup

Create a supported Python environment:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Run the core checks:

```powershell
python scripts\check_repository_safety.py
python -m compileall -q .
python -m pytest -q
python nlve_cli.py smoke
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
python -m pip_audit -r requirements-build.txt
```

Build the frontend from source:

```powershell
cd web
npm.cmd ci
npm.cmd run build
npm.cmd audit --audit-level=high
```

The compiled frontend is copied into `web_api/static/` for packaged serving.

## Release Build

Install build requirements, then run:

```powershell
python -m pip install -r requirements-build.txt
.\scripts\build-release.ps1
```

The release script creates ignored artifacts such as:

- unsigned Windows ZIP
- SHA-256 checksum
- CycloneDX SBOM
- packaged desktop/operator executables

The GitHub Windows release workflow performs the release build in CI and attaches
build provenance. The produced binary is unsigned unless a signing certificate is
provided separately.

## CI and Quality Gates

CI is designed to verify a clean checkout, not just the developer machine. Gates
include:

- Python `3.10`, `3.11`, and `3.12` test matrix
- repository safety scan
- reachable-history forbidden-path scan
- Python compilation
- unit and workflow tests
- local critical-path smoke test
- dependency audits
- frontend install/build/audit
- CodeQL
- Windows release workflow

Local tests or mocks are not treated as proof of live NLvoorelkaar acceptance,
Google Drive acceptance, Hetzner deployment acceptance, or signed Windows release
readiness.

## Architecture Notes for Developers

The application is deliberately centered on a transport-independent service
layer:

- Desktop, web, CLI, and HAI use the same application service.
- The service layer owns workflow rules rather than duplicating them in the UI.
- SQLite is the source of truth for campaigns, drafts, approvals, send attempts,
  responses, follow-ups, privacy decisions, and Safety Stop state.
- Provider adapters sit behind runtime policy checks.
- Tests can exercise local workflows without network access.

Key invariants:

- A draft cannot be completed without approval.
- A send completion cannot be recorded without evidence.
- Live provider actions require both a feature flag and written approval.
- Test mode cannot enable external provider actions.
- Ambiguous provider outcomes are not automatically retried.
- Privacy actions require explicit reasons.
- HAI is read-only and privacy-minimized.

## External Blockers and Non-Claims

The repository contains the local application and verification gates, but the
following cannot be truthfully completed by source code alone:

- current NLvoorelkaar written approval
- current NLvoorelkaar live selector/login/send acceptance
- owner-side Google credential revocation and rotation
- real Google Drive upload/readback/restore acceptance with private credentials
- Hetzner host, domain, and TLS acceptance
- Windows code-signing certificate and signed clean-machine acceptance
- manual accessibility and non-technical operator acceptance

These are external gates. They should remain visible in release notes and
operator documentation until the owner completes them with real evidence.

## Documentation Index

| Document | What it covers |
| --- | --- |
| `docs/OPERATOR_RUNBOOK.md` | How to run the product safely as an operator. |
| `docs/API_DOCUMENTATION.md` | Web API routes, authentication, errors, and service notes. |
| `docs/WEB_DEPLOYMENT.md` | Local web and Hetzner hosting. |
| `docs/HAI_CONNECTOR.md` | Read-only HAI feed setup and limits. |
| `docs/SECURITY_AND_PRIVACY.md` | Threat model, privacy design, and controls. |
| `docs/TECHNICAL_AUDIT.md` | Audit findings and dispositions. |
| `docs/FINAL_VERIFICATION_REPORT.md` | Verification evidence and blocked external evidence. |
| `docs/GOAL_COMPLETION_MATRIX.md` | Requirement-by-requirement implementation status. |
| `docs/TECHNICAL_DEBT.md` | Remaining maintenance and improvement items. |
| `docs/ACCEPTANCE_TESTS.md` | Acceptance test matrix. |
| `docs/UI_ACTION_AUDIT.md` | UI action coverage and routing. |
| `docs/TASK_GRAPH.md` | Dependency and task graph. |
| `docs/CODEX_WORKLOG.md` | Implementation worklog. |

## License and Responsibility

This repository uses the included proprietary `LICENSE`.

Operators remain responsible for complying with NLvoorelkaar terms, privacy law,
credential handling, consent, retention, and incident response. The software
provides guardrails and auditability, but it does not remove those obligations.
