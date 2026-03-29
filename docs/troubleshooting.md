# Troubleshooting

## `TypeError` when creating `JsonPatchFor[...]`

Cause:

- Wrong generic shape, or plain-JSON target not using `Literal["Name"]`.

Fix:

```python
from typing import Literal

ConfigPatch = JsonPatchFor[Literal["ServiceConfig"], MyRegistry]
```

Not:

```python
ConfigPatch = JsonPatchFor["ServiceConfig", MyRegistry]  # rejected
```

## `PatchValidationError: Invalid JSON document ...`

Cause:

- `apply(...)` target is not a strict JSON value (`dict`/`list`/primitive JSON
  types).

Fix:

- Ensure patch targets are JSON-serializable, strict JSON shapes.

## `PatchConflictError`

Cause:

- Patch is syntactically valid, but impossible against current document state
  (missing path, failing `test`, invalid remove target, etc.).

Fix:

- Check target document state and pointer paths.
- If needed, add precondition ops (`test`, custom guard ops) before mutating
  ops.

## Custom op rejected as not recognized

Cause:

- Operation class not included in active registry.

Fix:

- Add op class to the registry union used by `JsonPatch(...)` or `JsonPatchFor`.

## FastAPI returns `415 Unsupported Media Type`

Cause:

- Endpoint is enforcing JSON Patch media type, but request sent with a different
  `Content-Type`.

Fix:

- Send `Content-Type: application/json-patch+json`, or configure non-strict mode
  if your endpoint should allow `application/json`.

## FastAPI returns `422` after patch application

Cause:

- For model-bound patches, patched payload fails revalidation into target model.

Fix:

- Inspect validation detail and ensure patch values match model field types and
  constraints.
