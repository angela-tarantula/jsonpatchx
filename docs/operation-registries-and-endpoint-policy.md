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

Both routes patch the same model, but each can enforce a different mutation
vocabulary.

## Useful Patterns

- Least privilege by default: each client gets only the mutation surface it
  needs.
- Faster iteration during development: a permissive dev-only registry can
  support ad-hoc patching and experiments.
- Safer production administration: admin-only registries can expose high-impact
  operations behind stricter auth and audit controls.
- Cleaner client segmentation: web, internal services, and partner APIs can each
  use a different contract.

## Policy Outcome

Route-level registries make PATCH policy explicit:

- Allowed operations are visible in code and OpenAPI.
- Disallowed operations fail during parse/validation, before mutation.
- Public, admin, and dev endpoints can evolve independently without sharing one
  global mutation surface.
