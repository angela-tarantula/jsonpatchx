# JsonPatchFor Contracts

`JsonPatchFor[Target, Registry]` is primarily a contract generator:

- typed request body validation
- generated OpenAPI schema for allowed operations
- target binding (for model targets)

Use this when you want API-level patch contracts. For plain runtime patching,
`apply_patch(...)` or `JsonPatch(...)` is usually enough.

This page covers:

- model-bound targets: `JsonPatchFor[Model, Registry]`
- schema-name targets: `JsonPatchFor[Literal["Config"], Registry]`
- when to choose `JsonPatchFor` vs `JsonPatch`/`apply_patch`
- how target binding prevents cross-model application mistakes
