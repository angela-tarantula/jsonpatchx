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

## Demo 1: Standard JSON Patch

Standard JSON Patch with Pydantic models using `JsonPatchFor[Model]`.

**File:** `examples/demo1.py`

**Run**

- `uv run uvicorn examples.demo1:app --reload --port 8000`

## Demo 2: Custom PATCH endpoints

Custom registries bound to different Pydantic models using `patch_body_for_model(...)`.

**File:** `examples/demo2.py`

**Run**

- `uv run uvicorn examples.demo2:app --reload --port 8001`

## Demo 3: Custom PATCH endpoints for standard JSON documents

Non-pydantic JSON patching with custom registries using `patch_body_for_json(...)`.

**File:** `examples/demo3.py`

**Run**

- `uv run uvicorn examples.demo3:app --reload --port 8002`

## Demo 4: Custom JSON Pointer implementations

Registry-scoped pointer backends change parsing semantics without changing operation schemas.
Uses `patch_body_for_json_with_dep(...)` and `patch_body_for_model_with_dep(...)`.

**File:** `examples/demo4.py`

**Run**

- `uv run uvicorn examples.demo4:app --reload --port 8003`

This demo uses `patch_body_for_json_with_dep(...)` and `patch_body_for_model_with_dep(...)`
to inject Pydantic validation context, which FastAPI does not currently provide for request bodies.
