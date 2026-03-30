# Error Catalog

This page is the operational failure map for JsonPatchX-powered APIs.

## Error Families

| HTTP / family                | Meaning                                          | Typical cause                                                       | Action                                            |
| ---------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- | ------------------------------------------------- |
| `415 unsupported_media_type` | request media type rejected                      | strict PATCH route expects `application/json-patch+json`            | send expected content type or disable strict mode |
| `422 patch_input`            | patch payload is invalid                         | malformed operation shape, wrong discriminator, invalid field types | fix operation payload                             |
| `422 patch_validation`       | patched output fails model validation            | operations produce values invalid for target schema                 | align patch values with model constraints         |
| `409 patch_conflict`         | patch is valid but cannot apply to current state | missing path, failed `test`, invalid index transition               | inspect current doc state and operation ordering  |
| `500 patch_internal`         | unexpected runtime failure                       | custom op/backend bug path or unexpected exception                  | inspect wrapped cause and operation context       |

## Practical Diagnosis

### `TypeError` during `JsonPatchFor[...]` declaration

Usually means generic misuse.

Correct:

```python
UserPatch = JsonPatchFor[User, MyRegistry]
```

Incorrect:

```python
UserPatch = JsonPatchFor[User]
UserPatch = JsonPatchFor[User(), MyRegistry]
```

### `PatchValidationError: Invalid JSON document ...`

The apply target is not strict JSON-compatible data.

### Registry parse failures ("operation not recognized")

The operation is not in the active registry union.

### Non-finite values (`Infinity`, `NaN`)

Raw request payloads with non-finite numbers can trigger downstream
serialization failures in some FastAPI validation/error paths.

Mitigation:

- reject non-finite values client-side
- use normal JSON encoders rather than hand-crafted raw payload strings
