# Error Semantics and Contract Tests

A governed PATCH API is defined just as much by how it fails as by how it
mutates.

Status codes, response shape, and contract tests should be part of the design
from the start.

## Recommended failure semantics

The default FastAPI helpers in JsonPatchX support a simple, production-friendly
mapping:

| HTTP  | When it happens                                                                                                |
| ----- | -------------------------------------------------------------------------------------------------------------- |
| `415` | the route enforces `application/json-patch+json` and the request uses the wrong media type                     |
| `422` | request validation fails, the patch document is malformed, or the patched result fails target-model validation |
| `409` | the patch is valid but cannot be applied to the current resource state                                         |
| `500` | server-side patch execution fails unexpectedly or the route is misconfigured                                   |

Install the exception handler once:

```python
from fastapi import FastAPI

from jsonpatchx.fastapi import install_jsonpatch_error_handlers


app = FastAPI()
install_jsonpatch_error_handlers(app)
```

## Default response shape

By default, the FastAPI helper layer returns:

```json
{ "detail": "..." }
```

For most client-visible failures, `detail` is a string.

For internal patch execution failures, `detail` can be structured so the failing
operation is visible to operators and test suites:

```json
{
  "detail": {
    "index": 2,
    "op": { "op": "replace", "path": "/email", "value": 42 },
    "message": "patched value failed validation",
    "cause_type": "ValidationError"
  }
}
```

That split is practical:

- client-facing contract failures stay simple
- server-side debugging can still point at the exact failing operation

## Test the contract, not only the happy path

A good PATCH test suite should lock down four things:

1. media-type enforcement
2. parse-time validation behavior
3. apply-time conflict behavior
4. generated OpenAPI for the route

### Media type contract

```python
def test_requires_json_patch_media_type(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json"},
        json=[{"op": "replace", "path": "/active", "value": False}],
    )

    assert response.status_code == 415
    assert "application/json-patch+json" in response.json()["detail"]
```

### Conflict contract

```python
def test_missing_path_returns_conflict(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "remove", "path": "/missing"}],
    )

    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
```

### Target-model validation contract

```python
def test_invalid_patched_model_returns_422(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "replace", "path": "/email", "value": None}],
    )

    assert response.status_code == 422
```

### OpenAPI contract

```python
def test_user_patch_schema_snapshot(app):
    openapi = app.openapi()

    user_patch_request = openapi["components"]["schemas"]["UserPatchRequest"]
    responses = openapi["paths"]["/users/{user_id}"]["patch"]["responses"]

    assert user_patch_request == EXPECTED_USER_PATCH_REQUEST
    assert responses == EXPECTED_PATCH_RESPONSES
```

## What to keep stable

The most important things to keep stable over time are:

- which status code a category of failure maps to
- whether `detail` is a string or structured object
- which operations the route advertises in OpenAPI

Exact human-readable error strings are usually less important unless clients
depend on them. Status and shape are the real API contract.
