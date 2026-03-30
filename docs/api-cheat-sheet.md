# API Cheat Sheet

## Core Imports

```python
from jsonpatchx import (
    JsonPatch,
    JsonPatchFor,
    StandardRegistry,
    apply_patch,
)
```

## Entry Points

| Goal                           | API                             |
| ------------------------------ | ------------------------------- |
| Apply one patch quickly        | `apply_patch(doc, patch)`       |
| Parse once and reuse           | `JsonPatch(patch).apply(doc)`   |
| FastAPI PATCH request contract | `JsonPatchFor[Model, Registry]` |
| Optional strict FastAPI wiring | `JsonPatchRoute(...)`           |

## Standard Operations

```python
from jsonpatchx import AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp
```

## FastAPI Helpers

```python
from jsonpatchx.fastapi import (
    JsonPatchRoute,
    install_jsonpatch_error_handlers,
    patch_error_openapi_responses,
    patch_request_body,
    patch_route_kwargs,
)
```

## Common Exceptions

```python
from jsonpatchx import (
    PatchConflictError,
    PatchError,
    PatchInputError,
    PatchInternalError,
    PatchValidationError,
    TestOpFailed,
)
```

## Practical Notes

- default apply behavior is non-mutating (`inplace=False`)
- `inplace=True` is faster but non-transactional
- `JsonPatchFor` is for FastAPI PATCH contracts; plain JSON patching should use
  `apply_patch` / `JsonPatch`
