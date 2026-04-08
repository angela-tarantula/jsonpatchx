# Getting Started

This page gets you from plain RFC 6902 patching to a real FastAPI PATCH contract
with the fewest moving parts.

## Install

> JsonPatchX is not on PyPI yet. Install it from a local clone instead:

<!--
```sh
pip install jsonpatchx
```
-->

```sh
git clone https://github.com/angela-tarantula/jsonpatchx.git
cd jsonpatchx
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional FastAPI helpers come later:

<!--
```sh
pip install "jsonpatchx[fastapi]"
```
-->

```sh
pip install -e ".[fastapi]"
```

You do not need that extra just to use `JsonPatch` or `JsonPatchFor[...]`.

## 1. Apply a plain RFC 6902 patch

```python
from jsonpatchx import JsonPatch

doc = {
    "name": "Ada",
    "roles": ["engineer"],
    "active": True,
}

patch = JsonPatch(
    [
        {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
        {"op": "add", "path": "/roles/-", "value": "maintainer"},
    ]
)

updated = patch.apply(doc)
```

That is ordinary JSON Patch.

`JsonPatch` is Pydantic-backed, so the patch document is parsed and validated
before it is applied. If you already have JSON text, use
`JsonPatch.from_string(...)` and apply it the same way.

## 2. Turn the same RFC ops into a FastAPI contract

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

from jsonpatchx import JsonPatchFor


class User(BaseModel):
    id: int
    email: EmailStr
    active: bool


app = FastAPI()


@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: JsonPatchFor[User]) -> User:
    user = load_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

The request body on the wire is still standard JSON Patch:

```http
PATCH /users/1
Content-Type: application/json-patch+json

[
  {"op": "replace", "path": "/email", "value": "ada@example.com"},
  {"op": "replace", "path": "/active", "value": false}
]
```

What changed is the contract around it.

`JsonPatchFor[User]` means:

- the request body is parsed as a patch document, not a bare `list[dict]`
- the operations are validated before mutation
- the patched result is validated as `User`
- the route gets a real PATCH request schema instead of undocumented patch dicts

That is the smallest useful JsonPatchX route.

## What the first two examples are really showing

The first example proves that JsonPatchX is happy to be just an RFC 6902
library.

The second example proves that you do not need to buy into custom operations,
JSONPath, or helper classes just to get value from it. One type annotation is
enough to make PATCH part of a real FastAPI contract.

The next page stays with that idea and shows where the optional FastAPI helper
layer fits.
