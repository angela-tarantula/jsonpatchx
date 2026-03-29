# Error Catalog

| Status / Error family        | Typical cause                                             | Fix                                                         |
| ---------------------------- | --------------------------------------------------------- | ----------------------------------------------------------- |
| `415 unsupported_media_type` | Missing or wrong `Content-Type` for strict PATCH endpoint | Send `application/json-patch+json` or disable strict mode   |
| `422 patch_input`            | Invalid patch payload or operation fields                 | Validate operation schema and pointer fields                |
| `422 patch_validation`       | Patched model payload fails revalidation                  | Align patch values with target model constraints            |
| `409 patch_conflict`         | Patch is valid but conflicts with current document state  | Check path existence, sequence ordering, and preconditions  |
| `500 patch_internal`         | Unexpected runtime failure in operation execution         | Inspect operation implementation and wrapped cause metadata |

## Non-Finite Number Corner Case

Raw JSON payloads containing `Infinity` / `NaN` can produce `500` in some
FastAPI validation/serialization paths because the error payload may itself
contain non-finite values that are not JSON-serializable.
