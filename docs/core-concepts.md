# Core Concepts

JsonPatchX is easiest to use when you keep four objects in mind.

## 1) Operation Schemas

Every patch operation is a Pydantic model derived from `OperationSchema`.
Built-in RFC operations are provided (`AddOp`, `RemoveOp`, `ReplaceOp`,
`MoveOp`, `CopyOp`, `TestOp`), and you can define your own.

## 2) Operation Registries

A registry is a union of operation classes, for example:

```python
from jsonpatchx import StandardRegistry
```

or a custom union:

```python
type PlayerRegistry = StandardRegistry | IncrementByOp | ToggleOp
```

The registry is your allow-list. If an op is not in the registry, it is rejected
at parse/validation time.

## 3) Patch Objects

Two main entry points:

- `apply_patch(doc, patch, ...)`: convenience wrapper
- `JsonPatch(...)`: parse/validate once, then call `.apply(...)`

Both end up using the same patch engine and error semantics.

## 4) JsonPatchFor

`JsonPatchFor` creates typed patch request models:

- `JsonPatchFor[UserModel, Registry]` for Pydantic model targets
- `JsonPatchFor[Literal["Config"], Registry]` for plain JSON targets

Note: for plain JSON targets, you must use `Literal["Name"]` form.

## Copy & Mutation Semantics

- `inplace=False` (default): deep-copy input first
- `inplace=True`: apply directly to input object (faster, but no rollback on
  mid-patch failure)

`inplace=True` is not transactional.

## Error Model

Common categories:

- `PatchValidationError`: input document or model revalidation issues
- `PatchConflictError`: patch is valid, but cannot be applied to current state
- `PatchInputError`: malformed/invalid operation payloads
- `PatchInternalError`: unexpected operation runtime failure wrapped with
  operation index/context
