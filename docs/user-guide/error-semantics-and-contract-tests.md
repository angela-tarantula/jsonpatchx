# Error Semantics and Contract Tests

A governed PATCH API is defined just as much by how it fails as by how it
mutates.

If the route has stable success behavior but fuzzy failure behavior, the
contract is still incomplete.

## Decide your status mapping on purpose

With the optional FastAPI helper layer installed, a good default mapping looks
like this:

| HTTP status | Meaning                                                                                                                                      |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `415`       | the route requires `application/json-patch+json` and the request used the wrong media type                                                   |
| `422`       | the request body is not a valid patch document, uses a disallowed operation, or produces a patched result that fails target-model validation |
| `409`       | the patch is valid but cannot be applied to the current resource state                                                                       |
| `500`       | the server hit an unexpected patch execution failure or route misconfiguration                                                               |

That mapping works well because it keeps three different failure modes separate:

- request contract failures
- current-state conflicts
- server mistakes

If you do not use the helper layer, choose an equivalent mapping and keep it
stable.

## Install the helper layer once

```python
from fastapi import FastAPI

from jsonpatchx.fastapi import install_jsonpatch_error_handlers


app = FastAPI()
install_jsonpatch_error_handlers(app)
```

The point is not only convenience. It is keeping PATCH failures consistent
across routes.

## Disallowed operations should fail at parse time

When a route accepts a registry-limited contract, an unsupported operation
should fail before mutation runs.

That matters.

If a public route does not advertise `test` or `increment`, the client has not
sent a business-rule violation. It has sent a request body that does not match
the route contract.

Treat that as a request validation failure.

## Keep the error response shape stable

A good PATCH contract keeps the shape of failures predictable.

A small client-facing response can stay simple:

```json
{ "detail": "patched value failed validation" }
```

And a more operator-friendly failure can include structured detail when that is
useful:

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

The exact wording of the message can evolve more freely than the shape and
status mapping.

Clients usually care most about:

- which status code category they got
- whether `detail` is a string or an object
- whether the route keeps those choices stable over time

## Test the contract, not only the happy path

PATCH routes deserve contract tests, not only happy-path tests.

A good test suite should cover:

- media type enforcement
- disallowed-operation rejection
- apply-time conflicts
- target-model validation
- OpenAPI shape for the request body and standard error responses

### Media type enforcement

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

### Disallowed operation rejection

```python
def test_public_route_rejects_test_op(client):
    response = client.patch(
        "/public/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "test", "path": "/billing/plan", "value": "enterprise"}],
    )

    assert response.status_code == 422
```

### Current-state conflict

```python
def test_missing_path_returns_conflict(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "remove", "path": "/missing"}],
    )

    assert response.status_code == 409
```

### Target-model validation

```python
def test_invalid_patched_model_returns_422(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "replace", "path": "/email", "value": None}],
    )

    assert response.status_code == 422
```

### OpenAPI snapshot

```python
def test_user_patch_openapi_snapshot(app):
    openapi = app.openapi()

    patch_operation = openapi["paths"]["/users/{user_id}"]["patch"]
    request_body = patch_operation["requestBody"]
    responses = patch_operation["responses"]

    assert request_body == EXPECTED_REQUEST_BODY
    assert responses == EXPECTED_RESPONSES
```

That last one matters more than it first appears. A PATCH contract is partly
runtime behavior and partly published schema. Snapshot both.

## Stable failures make richer PATCH practical

This matters even more once you introduce custom operations and selector-style
targeting.

The more expressive the contract gets, the more important it is that failures
stay predictable.

That is how richer PATCH APIs stop feeling experimental and start feeling
dependable.
