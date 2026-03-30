# JsonPatchFor Contracts

`JsonPatchFor[TargetModel, Registry]` is the contract type for FastAPI PATCH
request bodies.

## What It Produces

```python
from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor

UserPatch = JsonPatchFor[User, StandardRegistry]
```

`UserPatch` is a generated Pydantic model representing a validated list of
allowed operations.

## Contract Guarantees

1. Closed vocabulary only operations present in `Registry` are accepted.

2. Runtime and OpenAPI alignment request schema and runtime validation come from
   the same operation models.

3. Target-bound application `patch.apply(user)` enforces compatibility with the
   bound target model.

4. Revalidated output patched payload is validated as `User` before returning.

## Scope

`JsonPatchFor` exists to define PATCH API contracts.

For plain JSON runtime patching, use:

- `apply_patch(...)`
- `JsonPatch(...)`

## Common Misuse

- `JsonPatchFor[User]` (missing registry)
- `JsonPatchFor[User(), Registry]` (instance instead of model class)
