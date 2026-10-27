# Operator Runbook

## Start and Diagnose

Use Python 3.15.2, install `requirements.txt`, then run `python run.py doctor`. Python 3.11-3.15 are supported compatibility lines; Pillow 13 requires Python 3.11 or later. Warnings for absent provider credentials are expected for local-only use. Database or configuration failures are not.

Run the network-free release smoke test with `python run.py smoke` before using real records.

For the browser interface, set a private `NLVE_WEB_API_TOKEN` of at least 32 characters and run `.\scripts\start-web.ps1`. Public hosting targets Hetzner. Keep workstation use on loopback and follow `DEPLOYMENT_TARGET.md` plus [Web and Hetzner Deployment](WEB_DEPLOYMENT.md) for hosted HTTPS.

## Normal Workflow

Use Candidate Intake, Campaigns, Messages, Responses, Follow-ups, Privacy, and Operations in that order. Approve only an exact message you have read. For assisted delivery, record evidence only after confirming the provider accepted the message.

## Enable a Provider

1. Obtain written platform approval naming the approved login, search, or send actions.
2. Store the completed authorization record and evidence outside the repository, based on `config/provider_authorization.example.json`.
3. Validate it with `python run.py provider-preflight PATH --action search --action send`.
4. Set `NLVE_PROVIDER_APPROVAL_PATH` and only the needed `NLVE_*_ENABLED=1` flag.
5. Keep search pages, send batch, and daily limits conservative.
6. Log in through the application; do not put credentials in source or committed `.env` files.
7. Run one owner-approved test record and inspect the audit/send history before expanding.

Drive additionally requires newly rotated private OAuth credentials. Use the Operations action so local backup verification occurs before upload.

## Emergency Stop

Activate **Operations > Safety Stop**. It blocks new provider actions and asks active tasks to cancel. It cannot retract a request already accepted by a provider.

If a send has no confirmed result, run:

```powershell
python run.py reconcile-sends --minutes 15
```

Then inspect provider history. Do not retry until the external outcome is known.

## Backup and Recovery

Create and verify a backup before maintenance: `python run.py backup --name before-maintenance`. Restore only from a verified local archive. Restore first creates a rollback backup and aborts if that protection cannot be created.

## Incident Response

Disable all live flags, activate Safety Stop, preserve the database and audit log, create a privacy-safe support bundle, and rotate affected provider credentials. Never attach raw logs, databases, tokens, or message exports to a public issue.
