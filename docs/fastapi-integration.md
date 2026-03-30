# FastAPI Integration

FastAPI integration in JsonPatchX follows a contract-first model:

1. define what a valid patch means
2. decide how much route wiring help you want

`JsonPatchFor[Model, Registry]` is the core contract type.

## Step 1: Define a PATCH Contract

```python
from pydantic import BaseModel

from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor


class User(BaseModel):
    id: int
    email: str
    active: bool


UserPatch = JsonPatchFor[User]


```

This binds:

- target model shape (`User`)
- allowed operation vocabulary (`StandardRegistry`)
- runtime patch execution

## Step 2: Use It Directly

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: UserPatch) -> User:
    user = load_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

This already gives you:

- request validation against your operation registry
- OpenAPI schemas generated from runtime operation models
- model-bound apply behavior with revalidation

## Step 3: Optional Wiring Assistance

If you want stricter content-type handling, reusable examples, and cleaner route
metadata, use `JsonPatchRoute`.

Install helper extras:

```sh
pip install "jsonpatchx[fastapi]"
```

```python
from typing import Annotated

from jsonpatchx.fastapi import JsonPatchRoute

user_patch = JsonPatchRoute(
    UserPatch,
    strict_content_type=True,
    examples={
        "deactivate": {
            "summary": "Deactivate user",
            "value": [{"op": "replace", "path": "/active", "value": False}],
        }
    },
)


@app.patch("/users/{user_id}", **user_patch.route_kwargs())
def patch_user_with_route(
    user_id: int,
    patch: Annotated[UserPatch, user_patch.Body()],
) -> User:
    ...
```

Use this when you want more guardrails in HTTP wiring without changing your
patch contract.
