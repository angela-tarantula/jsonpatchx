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

## Demo 1: typed model patching

**File:** `examples/demo1.py`

**Run**

- `uv run uvicorn examples.demo1:app --reload --port 8000`

**Try these requests**

- `GET http://127.0.0.1:8000/users/1`
- `PATCH http://127.0.0.1:8000/users/1`
  - Body:
    ```json
    [{"op": "replace", "path": "/name", "value": "Morgan"}]
    ```
- `PATCH http://127.0.0.1:8000/users/1`
  - Body:
    ```json
    [{"op": "add", "path": "/tags/-", "value": "staff"}]
    ```

## Demo 2: model-bound custom ops

**File:** `examples/demo2.py`

**Run**

- `uv run uvicorn examples.demo2:app --reload --port 8001`

**Try these requests**

**Try these requests**

- `GET http://127.0.0.1:8001/users/1`
- `PATCH http://127.0.0.1:8001/users/1`
  - Body:
    ```json
    [{"op": "increment", "path": "/quota", "value": 10}]
    ```
- `PATCH http://127.0.0.1:8001/teams/1`
  - Body:
    ```json
    [{"op": "append", "path": "/tags", "value": "infra"}]
    ```

## Demo 3: custom ops on JSON documents

**File:** `examples/demo3.py`

**Run**

- `uv run uvicorn examples.demo3:app --reload --port 8002`

**Try these requests**

**Try these requests**

- `GET http://127.0.0.1:8002/configs/site`
- `PATCH http://127.0.0.1:8002/configs/limits`
  - Body:
    ```json
    [{"op": "increment", "path": "/max_users", "value": 10}]
    ```

## Demo 4: pointer backends with context injection

**File:** `examples/demo4.py`

**Run**

- `uv run uvicorn examples.demo4:app --reload --port 8003`

**Try these requests**

- `GET http://127.0.0.1:8003/configs/site`
- `PATCH http://127.0.0.1:8003/configs/site`
  - Body:
    ```json
    [{"op": "replace", "path": "features.chat", "value": false}]
    ```

This demo uses `make_json_patch_body_with_dep(...)` to inject Pydantic validation context,
which FastAPI does not currently provide for request bodies.
