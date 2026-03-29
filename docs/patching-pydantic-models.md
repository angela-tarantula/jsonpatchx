# Patching Pydantic Models

Use model-bound patching when your API/service domain is already modeled with
Pydantic classes.

## Basic Pattern

```python
from pydantic import BaseModel

from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor


class User(BaseModel):
    id: int
    name: str
    premium: bool = False


UserPatch = JsonPatchFor[User, StandardRegistry]

patch = UserPatch.model_validate(
    [{"op": "replace", "path": "/name", "value": "Ada Lovelace"}]
)

original = User(id=1, name="Ada")
updated = patch.apply(original)

assert updated.name == "Ada Lovelace"
assert original.name == "Ada"  # original instance is unchanged
```

## What `apply` Does

For model-bound patches, `apply(...)`:

1. Calls `target.model_dump()`
2. Applies operations on that JSON-like payload
3. Revalidates into your target model with `model_validate(...)`

So you get a strongly validated model result, not an untyped `dict`.

## Type Safety Guard

`apply(...)` rejects non-target model instances:

```python
# raises TypeError because patch was bound to User, not Team
patch.apply(team_instance)
```

## Common Failures

- `PatchValidationError`: patched payload fails model validation
- `TypeError`: wrong model instance type passed to `apply(...)`

See [Troubleshooting](troubleshooting.md) for concrete examples.
