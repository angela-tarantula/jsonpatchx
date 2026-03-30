# Error Semantics and Contract Tests

Governed PATCH APIs need stable failure semantics, not only successful mutation
paths.

## Error Semantics

| HTTP  | Code                     | Meaning                                          |
| ----- | ------------------------ | ------------------------------------------------ |
| `415` | `unsupported_media_type` | request content type is rejected                 |
| `422` | `patch_input`            | request patch payload is invalid                 |
| `422` | `patch_validation`       | patched output violates target model             |
| `409` | `patch_conflict`         | patch is valid but cannot apply to current state |
| `500` | `patch_internal`         | unexpected runtime failure                       |

Install FastAPI error mapping once:

```python
from jsonpatchx.fastapi import install_jsonpatch_error_handlers


app = FastAPI()
install_jsonpatch_error_handlers(app)
```

## Contract Tests

Test both runtime behavior and generated OpenAPI.

### Runtime Failure Contract

```python
def test_missing_path_returns_conflict(client):
    response = client.patch(
        "/users/1",
        headers={"content-type": "application/json-patch+json"},
        json=[{"op": "remove", "path": "/missing"}],
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "patch_conflict"
```

### OpenAPI Contract Snapshot

Use snapshot tests to lock generated PATCH schemas and response metadata. See:

- `tests/contract/openapi/test_demo_openapi_snapshots.py`
- `examples/openapi/*.json`

## Continue

- [API Reference](api-reference.md)
- [Legacy User Guide](legacy-user-guide.md)
