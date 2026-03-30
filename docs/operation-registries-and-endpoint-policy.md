# Operation Registries and Endpoint Policy

Registries are the policy boundary for PATCH contracts.

A registry is a union of operation models. If an operation is not in the active
registry, it is rejected during parse/validation, before apply-time.

## Per-Endpoint Allow-Lists

```python
from jsonpatchx import AddOp, RemoveOp, ReplaceOp, StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor


type PublicUserRegistry = AddOp | RemoveOp | ReplaceOp
type InternalUserRegistry = StandardRegistry | IncrementQuotaOp

PublicUserPatch = JsonPatchFor[User, PublicUserRegistry]
InternalUserPatch = JsonPatchFor[User, InternalUserRegistry]
```

```python
@app.patch("/public/users/{user_id}")
def patch_public_user(user_id: int, patch: PublicUserPatch) -> User:
    ...


@app.patch("/internal/users/{user_id}")
def patch_internal_user(user_id: int, patch: InternalUserPatch) -> User:
    ...
```

Both routes patch the same model, but with different mutation vocabularies.

## Failure Boundary

If a client sends an operation that is not in the active registry, request
parsing fails immediately. That is the intended governance boundary.

## Continue

Next: [JSONPath Selection](jsonpath-selection.md)
