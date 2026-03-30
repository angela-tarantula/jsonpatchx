# Demos

JsonPatchX demos are available as local runnable apps and optional hosted
previews.

## Local Demos (Recommended)

Run all demos:

```sh
uv run python -m examples.run
```

Run one demo:

```sh
uv run uvicorn examples.fastapi.demo1:app --reload --port 8000
```

## Hosted Demos (Preview)

- Standard RFC PATCH demo: `https://example.com/jsonpatchx/rfc-demo`
- Governed custom-op demo: `https://example.com/jsonpatchx/governed-demo`

Hosted demos are non-mutating by design (sandbox/reset behavior). They return
patched responses without persisting shared state.

## Recommended Walkthrough

1. `examples/fastapi/demo1.py`
   - RFC operations with model-bound FastAPI patch contracts
2. `examples/fastapi/demo2.py`
   - custom operation registries and domain-oriented verbs
3. `examples/fastapi/demo3.py`
   - plain JSON patching and custom operation behavior
4. `examples/fastapi/demo4.py`
   - alternate pointer behavior and advanced patch semantics
