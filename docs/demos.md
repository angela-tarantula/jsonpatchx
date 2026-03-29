# Demos

JsonPatchX demos are available both locally and as hosted preview services.

## Hosted Demo Links

- Standard RFC PATCH API demo: `https://example.com/jsonpatchx/rfc-demo`
- Governed custom-op PATCH API demo:
  `https://example.com/jsonpatchx/governed-demo`

Hosted demos are non-mutating by design. Requests are applied to an ephemeral or
reset snapshot and responses return the patched result only, so users do not
interfere with each other.

## Run Locally (Authoritative)

Run all local demo servers:

```sh
uv run python -m examples.run
```

Run one demo:

```sh
uv run uvicorn examples.fastapi.demo1:app --reload --port 8000
```

## Suggested Exploration Path

1. `demo1.py`: standard RFC patching against Pydantic models
2. `demo3.py`: plain JSON patching and custom operation behavior
3. `demo2.py`: custom operation registries and model-specific contracts
