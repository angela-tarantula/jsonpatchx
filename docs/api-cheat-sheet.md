# API Cheat Sheet

## Core Imports

```python
from jsonpatchx import (
    JsonPatch,
    apply_patch,
    JsonPatchFor,
    StandardRegistry,
    OperationSchema,
    JSONPointer,
    JSONValue,
    AddOp,
    RemoveOp,
    ReplaceOp,
    MoveOp,
    CopyOp,
    TestOp,
)
```

## Choose the Right Entry Point

| Use case                                  | API                                       |
| ----------------------------------------- | ----------------------------------------- |
| Quick one-off patch on JSON doc           | `apply_patch(doc, patch)`                 |
| Parse once, apply many                    | `JsonPatch(...).apply(doc)`               |
| Typed request model for Pydantic target   | `JsonPatchFor[Model, Registry]`           |
| Typed request model for plain JSON target | `JsonPatchFor[Literal["Name"], Registry]` |
| Route helper for FastAPI PATCH endpoints  | `JsonPatchRoute(...)`                     |

## FastAPI Helpers

```python
from jsonpatchx.fastapi import (
    JsonPatchRoute,
    install_jsonpatch_error_handlers,
    patch_route_kwargs,
    patch_request_body,
    patch_error_openapi_responses,
)
```

## Common Exceptions

```python
from jsonpatchx import (
    PatchError,
    PatchValidationError,
    PatchConflictError,
    PatchInputError,
    PatchInternalError,
    TestOpFailed,
)
```

## Notes

- `apply(..., inplace=False)` is default and deep-copies input.
- `inplace=True` is faster but non-transactional.
- Model-bound `JsonPatchFor` returns revalidated model instances.
