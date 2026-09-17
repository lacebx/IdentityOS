# OpenAI-Compatible Provider Configuration

IdentityOS discovers OpenAI-compatible providers directly from the
environment. Configuration is side-effect-free: reading `.env` or an
environment mapping never makes a network request.

## Named providers: `OPENAI_<NAME>_API_KEY`

You may configure any number of named OpenAI-compatible providers:

| Variable                        | Meaning                          |
| ------------------------------- | -------------------------------- |
| `OPENAI_<NAME>_API_KEY`         | API key for provider `<NAME>`    |
| `OPENAI_<NAME>_BASE_URL`        | Optional base URL, e.g. a proxy  |
| `OPENAI_<NAME>_MODEL`           | Optional model name              |

Reserved suffixes (`API`, `KEY`, `BASE`, `URL`, `MODEL`, `ORGANIZATION`,
`TIMEOUT`) never become provider names themselves.

Example from `adapters/configuration.py`:

```dotenv
OPENAI_GEMINI_API_KEY=gam_...
OPENAI_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_GEMINI_MODEL=gemini-2.0-flash

OPENAI_NVIDIA_API_KEY=nvapi-...
OPENAI_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_NVIDIA_MODEL=nvidia/nemotron-3.5
```

Discovery preserves a deterministic provider order; every discovered provider
with valid credentials joins the fallback `ChainAdapter`. Base URLs pointing at
`localhost` or `127.0.0.1` select local (Ollama) semantics automatically.

## Legacy variables (keep working, superseded)

The historical single-provider variables remain supported and are treated as
named providers:

| Legacy variable   | Provider name |
| ----------------- | ------------- |
| `OPENAI_API_KEY`  | `openai`      |
| `OLLAMA_API_KEY`  | `ollama`      |

Use `IDENTITY_ADAPTER` to force a specific provider:

```dotenv
IDENTITY_ADAPTER=gemini
IDENTITY_ADAPTER_CONFIG={"model": "gemini-2.0-flash"}
```

## Verification

```bash
python -c "from adapters import describe_adapter, build_adapter_from_env; \
print(describe_adapter(build_adapter_from_env()))"
```

`describe_adapter` reports provider models without ever exposing credentials.