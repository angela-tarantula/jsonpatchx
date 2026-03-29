# JsonPatchX Documentation

JsonPatchX gives you RFC 6902 patching with strong typing, schema-backed
validation, and FastAPI-first tooling.

If this is your first time with the library, use this order:

1. [Getting Started](getting-started.md)
2. [Core Concepts](core-concepts.md)
3. [Patching Plain JSON](patching-plain-json.md)
4. [Patching Pydantic Models](patching-pydantic-models.md)
5. [Custom Operations](custom-operations.md)
6. [FastAPI Integration](fastapi-integration.md)
7. [JsonPatchFor Contracts](jsonpatchfor-contracts.md)

Then use:

- [Demos](demos.md) for runnable end-to-end examples
- [Troubleshooting](troubleshooting.md) for common failures
- [API Cheat Sheet](api-cheat-sheet.md) for quick lookup

## Documentation Structure

- Start Here: setup and conceptual model
- Apply Patches: plain JSON, Pydantic models, and FastAPI wiring
- Design & Contracts: registries, custom ops, pointer backend strategy, typing
  notes
- Demos: runnable examples and hosted/local entry points
- Reference: API summary and failure diagnostics

## Why JsonPatchX

- RFC 6902-compatible built-ins (`add`, `remove`, `replace`, `move`, `copy`,
  `test`)
- Typed patch operations with Pydantic models
- Registry allow-listing so each endpoint can permit only selected operations
- `JsonPatchFor[...]` factory for model-bound or plain-JSON patch contracts
- FastAPI helpers to keep request docs, content-type enforcement, and error
  responses aligned

## Local Docs Preview

```sh
uv sync
uv run zensical serve
```

Build static docs output:

```sh
uv run zensical build
```
