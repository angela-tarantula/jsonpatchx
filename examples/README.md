# Examples: jsonpatchx demo suite

Four focused FastAPI demos. Each demo is a standalone file that reads cleanly in Swagger UI.

## Setup (once)

- Install demo deps: `uv sync --group fastapi`
- Run commands from the repo root.

## Quick links

- Swagger: `http://127.0.0.1:PORT/docs`
- OpenAPI JSON: `http://127.0.0.1:PORT/openapi.json`
- ReDoc: `http://127.0.0.1:PORT/redoc`

## Demo launcher

```bash
uv run python -m examples.demo
```

FastAPI docs already include example requests and payloads.

## Demo 1: Customer profile patching

Standard JSON Patch on customer profiles using `JsonPatchFor[Model]`.

**File:** `examples/demo1.py`

**Run**

- `uv run uvicorn examples.demo1:app --reload --port 8000`

## Demo 2: Billing and team ops

Custom registries for billing-style ops on users and teams using `JsonPatchFor[Model, CustomRegistry]`.

**File:** `examples/demo2.py`

**Run**

- `uv run uvicorn examples.demo2:app --reload --port 8001`

## Demo 3: Feature flags and limits

Non-pydantic JSON patching for config docs using `JsonPatchFor[Name, Registry]`.

**File:** `examples/demo3.py`

**Run**

- `uv run uvicorn examples.demo3:app --reload --port 8002`

## Demo 4: Dot-pointer settings

Registry-scoped dot-pointer backends for config and user settings.
Uses `PatchDependency(...)` with explicit request body configuration.

**File:** `examples/demo4.py`

**Run**

- `uv run uvicorn examples.demo4:app --reload --port 8003`

This demo uses `PatchDependency(...)` to inject Pydantic validation context, which FastAPI
does not currently provide for request bodies.
