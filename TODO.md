# Remaining External and Release Work

Implemented repository work is tracked in `docs/GOAL_COMPLETION_MATRIX.md`. The following items cannot be completed from source code alone:

- Revoke the historically exposed Google refresh token.
- Delete or rotate the historically exposed Google OAuth client secret.
- Review Google account and Drive activity for misuse.
- Obtain written NLvoorelkaar approval that satisfies the private provider-authorization record before live login, search, or sending.
- Run a controlled acceptance test against the current NLvoorelkaar login, search, message, and confirmation pages with an owner-approved test account.
- Run a controlled Google Drive OAuth, upload, readback, and restore test with newly rotated private credentials.
- Complete screen-reader and high-DPI manual UI review on supported Windows versions.
- Sign the provenance-attested Windows artifact with an owner-controlled code-signing certificate before broad distribution.
- Complete owner-approved Hetzner HTTPS, reverse-proxy, backup, restore, and rollback acceptance before public cutover.

Live flags must remain disabled until their corresponding provider acceptance work is complete.
