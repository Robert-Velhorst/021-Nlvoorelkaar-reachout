# Web and Hetzner Deployment

## Local web application

Use Python 3.15.1 and install `requirements.txt`. Python 3.11-3.15 are supported compatibility lines. Generate a private random bearer token with at least 32 characters, then start the loopback server:

```powershell
$env:NLVE_WEB_API_TOKEN = "private-random-value-with-at-least-32-characters"
.\scripts\start-web.ps1 -Port 8765
```

In a source checkout where `python` is not the supported interpreter, pass `-PythonExecutable C:\path\to\python.exe`. In the standalone release the scripts automatically use `NLVE-Operator.exe`.

Open `http://127.0.0.1:8765`. The API and static web assets run in one Uvicorn worker over the same SQLite database as the desktop application. Do not run multiple writers against a database copied to a network share.

## Public deployment

Public hosting targets Hetzner. Configure `NLVE_WEB_API_TOKEN` and the exact `NLVE_WEB_TRUSTED_HOSTS` for the owned HTTPS domain in the server environment. Terminate TLS at the reviewed reverse proxy and forward only to the loopback-bound app. Follow the repository-root `DEPLOYMENT_TARGET.md` for the migration and operator acceptance gates. The workstation tunnel launcher has been retired.

## Security notes

- Use a dedicated random token, not an NLvoorelkaar password or Google credential.
- Share credentials only through approved private secret handling and rotate them after an access incident.
- Browser tokens live only in session storage. Disconnect after use on a shared device.
- Public web access does not authorize provider automation. Live provider actions still require feature flags and the private written-approval record.
- The HAI bridge may read the feed from the approved hosted environment, but HAI has no approval, send, retention, or Safety Stop authority.
