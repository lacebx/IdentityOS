# Public REST API

IdentityOS exposes the same persistent runtime used by the CLI through a
FastAPI service. Start it with:

```bash
uvicorn runtime.main:app --host 127.0.0.1 --port 8000
```

Swagger UI is available at `http://localhost:8000/docs`; the OpenAPI document
is available at `/openapi.json`.

## Security

Local development remains unauthenticated when no API key is configured. Any
network-accessible deployment should set an API key and a request limit:

```bash
export IDENTITY_API_KEY="replace-with-a-random-secret"
export IDENTITY_RATE_LIMIT_PER_MINUTE=120
uvicorn runtime.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Clients authenticate with either `X-API-Key: <key>` or
`Authorization: Bearer <key>`. For key rotation, set `IDENTITY_API_KEYS` to a
comma-separated list. `/health`, `/docs`, `/redoc`, and `/openapi.json` remain
available without credentials. The built-in limiter is process-local; use one
worker or enforce a shared limit at a reverse proxy when running multiple
workers. Terminate TLS at that proxy and do not expose an unencrypted service
to the public internet.

## Operations

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/chat` | Run the full identity interaction pipeline |
| `POST` | `/identity` | Create an identity |
| `GET` | `/identity` | List identities |
| `GET` | `/identity/{id}` | Inspect an identity |
| `POST` | `/memory` | Store a provenance-scoped memory |
| `POST` | `/goal` | Create and persist a goal |
| `POST` | `/relationship` | Record and persist a relationship |
| `POST` | `/timeline` | Record and persist a timeline event |
| `POST` | `/constitution` | Inspect the constitution and laws |
| `POST` | `/export` | Export a portable identity snapshot |
| `GET` | `/health` | Check service health |

Validation failures use FastAPI's structured `422` response. Domain errors use
an explanatory `detail`, authentication failures return `401`, missing
identities return `404`, and rate limiting returns `429` with `Retry-After`.

