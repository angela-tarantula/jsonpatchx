# JsonPatchFor Contracts

`JsonPatchFor[TargetModel, Registry]` is the PATCH contract type for FastAPI
endpoints in JsonPatchX.

## What It Gives You

- typed request body validation
- OpenAPI schema generation from the active operation union
- runtime model-bound patch application (`patch.apply(model_instance)`)

## Contract Shape

```python
from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor

UserPatch = JsonPatchFor[User, StandardRegistry]
```

Use this directly as your FastAPI request model type.

## Why Not Use It for Plain JSON Runtime Work

For plain JSON patching that is not a FastAPI request contract, prefer:

- `apply_patch(...)`
- `JsonPatch(...)`
