# Troubleshooting

## `TypeError` when creating `JsonPatchFor[...]`

Cause:

- Wrong generic shape for the FastAPI request contract.

Fix:

```python
UserPatch = JsonPatchFor[User, MyRegistry]
```

Not:

```python
UserPatch = JsonPatchFor[User]  # missing registry
UserPatch = JsonPatchFor[User(), MyRegistry]  # instance, not model class
```

## `PatchValidationError: Invalid JSON document ...`

Cause:

- `apply(...)` target is not a strict JSON value.

Fix:

- Ensure patch targets are strict JSON-compatible values.

## `PatchConflictError`

Cause:

- Patch is valid, but impossible against current document state (missing path,
  failing `test`, invalid remove target, etc.).

Fix:

- Check document state and pointer paths.
- Add precondition operations (`test`, custom guards) before mutating ops.

## Custom op rejected as not recognized

Cause:

- Operation class is missing from the active registry.

Fix:

- Add the op class to the union passed to `JsonPatch(...)` or `JsonPatchFor`.

## FastAPI returns `415 Unsupported Media Type`

Cause:

- Endpoint expects `application/json-patch+json` but request used another
  content type.

Fix:

- Send `Content-Type: application/json-patch+json`, or use non-strict mode.

## FastAPI returns `500` for `Infinity` or `NaN` payloads

Observed behavior:

- If a client sends raw JSON containing `Infinity`/`NaN`, FastAPI validation can
  include `inf`/`nan` in error payload internals.
- Error response serialization may then fail
  (`Out of range float values are not JSON compliant`), producing
  `500 Internal Server Error`.

Related client behavior:

- Many HTTP clients already block this before sending JSON (`allow_nan=False`),
  which raises a client-side error instead.

Fix:

- Do not send non-finite numbers in patch payloads.
- Validate client payloads for finite numbers before sending.
- Prefer normal JSON encoders over raw request bodies for patch payloads.
