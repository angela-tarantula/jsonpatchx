# Demos

JsonPatchX includes seven FastAPI demos under `/examples/fastapi`.

## Run All Demo Servers

```sh
uv run python -m examples.run
```

Then open:

- Swagger UI: `http://127.0.0.1:PORT/docs`
- OpenAPI JSON: `http://127.0.0.1:PORT/openapi.json`

## Demo Overview

1. `demo1.py`: standard RFC 6902 patching against Pydantic models
2. `demo2.py`: custom operation registries per model type
3. `demo3.py`: plain JSON patching with `JsonPatchFor[Literal["..."], Registry]`
4. `demo4.py`: mixed pointer backends in one registry
5. `demo5.py`: explicit custom backend ops
6. `demo6.py`: generic backend-parameterized ops
7. `demo7.py`: schema/OpenAPI contract behavior

## Run One Demo

Example (Demo 1):

```sh
uv run uvicorn examples.fastapi.demo1:app --reload --port 8000
```

## Next

- For custom-op authoring patterns, inspect `/examples/recipes.py`.
- For API behavior verification, inspect integration tests under
  `/tests/integration/fastapi/runtime`.
