# FastAPI Integration

For FastAPI PATCH endpoints, use `JsonPatchFor[Model, Registry]` as the request
contract type.

Install helpers if you plan to use `jsonpatchx.fastapi` utilities:

```sh
pip install "jsonpatchx[fastapi]"
```

## Baseline Integration with `JsonPatchFor`

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor


class User(BaseModel):
    id: int
    name: str


UserPatch = JsonPatchFor[User, StandardRegistry]
app = FastAPI()


@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: UserPatch) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

## Why `JsonPatchFor` in FastAPI

- request payload validation against your registry union
- generated OpenAPI schema for allowed operations
- model-bound patch application contract at runtime

For contract details and error modes, see
[JsonPatchFor Contracts](jsonpatchfor-contracts.md).
