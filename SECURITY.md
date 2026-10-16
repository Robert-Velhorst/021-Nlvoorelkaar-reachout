# Security Policy

## Supported versions

Security reports are welcome for the current `main` branch and published releases. This project does not promise a support window or guaranteed fixes for specific versions. Maintainers triage reports and prioritize fixes as capacity permits; no response, remediation, or backport deadline is guaranteed.

## Reporting a vulnerability

Use **Report a vulnerability** on the repository's [GitHub Security tab](https://github.com/Robert-Velhorst/021-Nlvoorelkaar-reachout/security). Private vulnerability reporting is enabled. Include the affected path or release, reproduction steps, and impact. Do not include credentials, tokens, personal data, or message content in public issues or reports.

If private reporting is unavailable, open a public issue with only the title **Request private security contact**. Do not include vulnerability details or proof-of-concept material until a private channel is available.

## Compromised Historical Credentials

Google OAuth material was committed in repository history. Removing it from the active tree and rewriting Git history reduces exposure but does not revoke it. The Google Cloud owner must revoke the refresh token, delete or rotate the OAuth client secret, review account activity, and issue new private credentials before Drive use.

GitHub secret scanning and push protection are enabled. Its historical alerts refer only to pre-rewrite commits that are no longer reachable; they remain open until the real Google credentials are revoked/rotated and must not be dismissed as false positives.

## Security Boundaries

- External search, send, and Drive features are disabled by default.
- Live NLvoorelkaar login, search, and send each require a valid private written-approval record that names the approved actions and current terms version.
- The web API requires a bearer token of at least 32 characters, applies trusted-host validation, bounded request rates, a restrictive CSP, no-store responses, and no CORS grant.
- The web server binds to loopback by default. Follow `DEPLOYMENT_TARGET.md` for production; Hetzner is the target, and new production deployments must not use Vercel or ngrok. Do not claim public or production readiness until the deployed ingress, TLS, host/origin rules, rate limits, backups, monitoring, and rollback have been verified.
- Message sending requires a persisted draft, an exact approved snapshot, a bounded explicit action, and a durable attempt/audit record.
- Manual sends require operator-entered evidence. The app never infers that a copied message was sent.
- Stale in-flight sends become `external_outcome_unknown`; no automatic retry occurs.
- Credentials are encrypted with an operator master password or stored in the OS credential vault. There is no service-name/default-password fallback.
- Google Drive uses `drive.file` and never authenticates or writes remotely during object construction.
- Backups reject traversal, symbolic links, excessive expansion, and credential/token/session files.
- Support bundles contain aggregate diagnostics only.

## Local Data

Protect `data/`, `logs/`, `backups/`, and exports with OS account controls and encrypted storage. They can contain personal data. Use Privacy Review for retention proposals, export, archival, and redaction. Deletion/redaction actions require explicit operator action and are audited.

## Coordinated disclosure

Allow maintainers reasonable time to investigate and coordinate a fix before public disclosure. No response-time or remediation-time guarantee is offered.

## Release Gate

Before release, run:

```powershell
python scripts\check_repository_safety.py --history
python -m pytest -q
python nlve_cli.py smoke
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
python -m pip_audit -r requirements-build.txt
cd web; npm.cmd ci; npm.cmd run build; npm.cmd audit --audit-level=high
.\scripts\build-release.ps1
```

Do not claim live-provider readiness until the provider/account acceptance items in `docs/FINAL_VERIFICATION_REPORT.md` are complete.
