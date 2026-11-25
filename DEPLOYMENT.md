# Deployment Information — Day 14

## Public URL

https://agent-production-fe2e5842.up.railway.app

## Platform and source

- Platform: Railway, environment `production`.
- Application source: `06-lab-complete/` (deployed with `--path-as-root`).
- Redis: separate `Redis` service in the same Railway project.
- The agent listens on the `PORT` supplied by Railway.

## Environment variables set on the agent

- `AGENT_API_KEY` — value kept only in Railway; never stored in this repo.
- `REDIS_URL` — reference to `${{Redis.REDIS_URL}}`.
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=10`

## Public endpoint checks

The four checks run from PowerShell on 25 November 2026 returned:

| Request | HTTP status |
| --- | ---: |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` without API key | 401 |
| `POST /ask` with the configured API key | 200 |

To repeat without printing the key:

```powershell
$base = 'https://agent-production-fe2e5842.up.railway.app'
$bodyFile = Join-Path $env:TEMP 'day14-cp6-body.json'
Set-Content -LiteralPath $bodyFile -Value '{"question":"Hello"}' -Encoding ASCII -NoNewline
$secureKey = Read-Host 'Nhap AGENT_API_KEY da dat tren Railway' -AsSecureString
$apiKey = [System.Net.NetworkCredential]::new('', $secureKey).Password

curl.exe -sS -o NUL -w '%{http_code}\n' "$base/health"
curl.exe -sS -o NUL -w '%{http_code}\n' "$base/ready"
curl.exe -sS -o NUL -w '%{http_code}\n' -X POST "$base/ask" -H 'Content-Type: application/json' --data-binary "@$bodyFile"
curl.exe -sS -o NUL -w '%{http_code}\n' -X POST "$base/ask" -H 'Content-Type: application/json' -H "X-API-Key: $apiKey" --data-binary "@$bodyFile"

Remove-Item -LiteralPath $bodyFile
Remove-Variable apiKey,secureKey
```

## Screenshots

- [Railway project dashboard](screenshots/dashboard.png)
- [Agent and Redis running](screenshots/running.png)
- [Four HTTP status codes](screenshots/test.png)
