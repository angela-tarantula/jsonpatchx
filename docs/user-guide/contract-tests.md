# Contract Tests

PATCH routes deserve contract tests, not only happy-path tests.

A good test suite should cover:

- media type enforcement
- disallowed-operation rejection
- apply-time conflicts
- target-model validation
- OpenAPI shape for the request body and standard error responses

## Media Type Enforcement

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

## Disallowed Operation Rejection

```python
def test_public_route_rejects_test_op(client):
    response = client.patch(
        "/public/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "test", "path": "/billing/plan", "value": "enterprise"}],
    )

    assert response.status_code == 422
```

## Current-State Conflict

```python
def test_missing_path_returns_conflict(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "remove", "path": "/missing"}],
    )

    assert response.status_code == 409
```

## Target-Model Validation

```python
def test_invalid_patched_model_returns_422(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "replace", "path": "/email", "value": None}],
    )

    assert response.status_code == 422
```

## OpenAPI Snapshot

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
