# HAI Connector

NLvoorelkaar Reachout exposes a read-only, privacy-minimized HAI Generic JSON Feed at `GET /api/v1/hai/feed`. It contains review work and stable record references, not message bodies, volunteer names, contact details, credentials, approvals, or execution authority.

## Local HAI Feed

Run the authenticated bridge beside HAI and write into HAI's configured feed directory:

```powershell
$env:NLVE_API_URL = "http://127.0.0.1:8765"
$env:NLVE_API_TOKEN = $env:NLVE_WEB_API_TOKEN
python -m connectors.hai_bridge C:\private\hai-feeds\nlve.json
```

Register that file in HAI as:

```json
{
  "name": "NLvoorelkaar Reachout",
  "provider": "generic_json_feed",
  "accountLabel": "nlvoorelkaar-reachout",
  "sourceType": "local_json_file",
  "path": "nlve.json",
  "projectKey": "021-Nlvoorelkaar-reachout",
  "operationType": "review_source_item",
  "enabled": true
}
```

For separate hosts, point `NLVE_API_URL` at the verified Hetzner HTTPS origin behind the approved reverse proxy. The bearer token remains in an HTTP header and is never placed in a feed URL or HAI source URI. Schedule the bridge at a conservative interval; HAI deduplicates stable item revisions during sync.

HAI remains read-only. It can propose or organize review work, but it cannot approve drafts, send messages, clear Safety Stop, or mutate NLvoorelkaar Reachout.

`NLVE_API_URL` is an origin only: HTTPS plus hostname and optional port, or HTTP on `127.0.0.1`, `localhost`, or `[::1]`. URL usernames/passwords, paths beyond `/`, query strings, fragments, whitespace, control characters and encoded authorities are rejected before a request. The bridge constructs the fixed feed path itself and rejects redirects. Explicit bearer authentication prevents ambient `.netrc` entries from replacing the selected API token. The operator remains responsible for choosing the verified destination; this is not a public-host allowlist or a complete SSRF closure claim.
