# Error Semantics

A governed PATCH API is defined just as much by how it fails as by how it
mutates.

If the route has stable success behavior but fuzzy failure behavior, the
contract is still incomplete.

## Install the Error Handlers Once

```python
from fastapi import FastAPI
from jsonpatchx.fastapi import install_jsonpatch_error_handlers

app = FastAPI()
install_jsonpatch_error_handlers(app)
```

## Default Status Mapping

The goal is to keep three failure modes separate:

- request contract failures
- current-state conflicts
- server mistakes

If you use the optional FastAPI helpers, the default mapping is:

| Status | Default meaning                                                                                                                                                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `415`  | `JsonPatchRoute` rejects the wrong media type when the route requires JSON Patch content, and includes an `Accept-Patch` header naming the expected media type.                                                                                           |
| `422`  | FastAPI request validation and `InvalidPatchResult` cover invalid patch documents, invalid pointer/selector syntax, and patched results that fail the target model schema.                                                                                |
| `409`  | `PatchConflictError` means the patch cannot be applied to the current resource state.                                                                                                                                                                     |
| `500`  | `PatchInternalError` is the fallback for unexpected execution failures. `InvalidPatchTarget` signals an invalid patch target or document (not valid JSON, or, for model-aware patching, the wrong model instance or a model that produces non-JSON data). |

If you do not use the helper layer, choose an equivalent mapping and keep it
stable.

<!-- TODO: Cover non-HTTP exceptions -->
<!-- TODO: Display error shapes -->
