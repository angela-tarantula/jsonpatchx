# FastAPI Integration

JsonPatchX ships helpers so request validation, OpenAPI docs, and runtime
behavior stay aligned.

## Minimal Route Setup

```python
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel

from jsonpatchx import StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute, install_jsonpatch_error_handlers
from jsonpatchx.pydantic import JsonPatchFor


class User(BaseModel):
    id: int
    name: str


store = {1: User(id=1, name="Ada")}

UserPatch = JsonPatchFor[User, StandardRegistry]
user_patch = JsonPatchRoute(
    UserPatch,
    examples={
        "rename": {
            "summary": "Rename user",
            "value": [{"op": "replace", "path": "/name", "value": "Ada Lovelace"}],
        }
    },
    strict_content_type=True,
)

app = FastAPI(title="Users API")
install_jsonpatch_error_handlers(app)


@app.patch("/users/{user_id}", response_model=User, **user_patch.route_kwargs())
def patch_user(
    user_id: Annotated[int, Path(...)],
    patch: Annotated[UserPatch, user_patch.Body()],
) -> User:
    user = store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    store[user_id] = updated
    return updated
```

## What the Helpers Add

- JSON Patch error response schemas (`409`, `422`, `415`, `500`)
- Content-type enforcement (`application/json-patch+json`) when strict mode is
  on
- Request body OpenAPI wiring for the generated patch model

## Content-Type Behavior

- `strict_content_type=True`: enforces `application/json-patch+json`
- `strict_content_type=False`: allows regular `application/json` compatibility

## Error Mapping

By default:

- `415`: wrong content type
- `422`: patch input/model validation errors
- `409`: valid patch that conflicts with current resource state
- `500`: unexpected internal patch failures

See [Demo Error Shapes](demo-error-shapes.md) for real payload examples.
