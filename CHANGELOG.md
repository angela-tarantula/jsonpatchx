# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- textlint-disable -->

## [Unreleased]

### Added

- `DEFAULT_POINTER_CLS` and `DEFAULT_SELECTOR_CLS` are now explicitly supported
  public API and can be imported directly when you want to bind JsonPatchX's
  built-in pointer and selector backends.
- `InvalidPatchTarget` is a new `PatchError` subclass raised when the document
  passed to the patch engine is not a valid JSON value. This is a server-side
  configuration error and maps to 500 Internal Server Error.

### Removed

- `OperationValidationError` has been removed from the public API. It was raised
  inside Pydantic model validators, where Pydantic always wraps it in its own
  `ValidationError` before callers can observe it, making it uncatchable as a
  standalone exception. Use `PydanticCustomError` from `pydantic_core` instead,
  which gives structured error codes and message templates and integrates
  cleanly with Pydantic's validation error surface. `MoveOp` has been updated
  accordingly.
- `STANDARD_OPS` has been removed from the public API. It was a redundant tuple
  of the six built-in operation classes with no behavior of its own. The
  individual op classes (`AddOp`, `RemoveOp`, etc.) and `StandardRegistry`
  remain fully supported.
- `PatchInputError` has been removed from the public API. Its subclasses
  (`InvalidJSONPointer`, `InvalidJSONSelector`) are now direct `PatchError`
  subclasses and remain available. `PatchValidationError` is also now a direct
  `PatchError` subclass with a corrected HTTP mapping (409 Conflict, not 422).
  Replace any `except PatchInputError` with the specific types you need.
- `OperationNotRecognized` has been removed. Passing an op instance that is not
  registered now raises `ValidationError` from Pydantic, consistent with all
  other invalid inputs to the parse methods.

### Changed

- `JSONPointer.is_parent_of` and `is_child_of` now raise `TypeError` instead of
  `InvalidJSONPointer` when called with a pointer that uses an incompatible
  backend. This is a programmer error, not a patch input error.
- `JSONSelector` methods (`get_pointers`, `getall`, `addall`, `removeall`,
  `is_gettable`, `is_addable`, `is_removable`) now raise `TypeError` instead of
  `InvalidJSONSelector` when the selector backend yields objects that do not
  implement `PointerBackend`. Same rationale: corrupted backend state is a
  programmer error, not a patch input error.
- Inputs that represent programmer misconfiguration (passing a wrong-type
  argument to `parse()`, or using an abstract class as a backend type parameter)
  now raise `TypeError` directly rather than surfacing as
  `InvalidJSONPointer`/`InvalidJSONSelector` or `ValidationError`. Both map to
  500, not 422.
- The patch engine now validates each operation's return value against
  `JSONValue` after every `apply()` call. If a custom op returns a non-JSON
  value (for example, a `datetime`), a `PatchInternalError` is raised with the
  op index and payload as context rather than the invalid value silently
  propagating.
- Simplified `SelectorBackend` so custom selector backends yield
  `PointerBackend` instances directly through `pointers(doc)`, removing the
  separate `SelectorMatch` wrapper protocol.
- Operations no longer delete documents. For example, `RemoveOp` now rejects the
  root pointer with `PatchConflictError`. Fundamentally, PATCH should represent
  document transformation, not creation/deletion.
- Tightened `JSONPointer.parse()` and `JSONSelector.parse()` type hints with
  overloads so omitted `type_param` defaults no longer require ignore comments
  and default/custom backend return types are preserved more accurately.

## [0.1.0] - 2026-04-24

### Added

- Initial public release of JsonPatchX as a PATCH framework for Python.
- RFC 6902 parsing, validation, and application, including compliance coverage
  against the upstream JSON Patch test suite.
- Typed `JSONPointer` and `JSONSelector` surfaces, including built-in backends,
  custom backend hooks, and standards-oriented coverage for RFC 6901 and RFC
  9535 behavior.
- Pydantic-first operation models, `JsonPatchFor[...]`, route-scoped registries,
  and schema generation for governed PATCH contracts.
- FastAPI integration helpers and OpenAPI generation for plain RFC 6902, custom
  operations, and selector-based patch APIs.
- User guide, developer reference, API reference, and runnable demo apps,
  including FastAPI examples and OpenAPI snapshots.

[unreleased]:
  https://github.com/angela-tarantula/jsonpatchx/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/angela-tarantula/jsonpatchx/releases/tag/v0.1.0

<!-- textlint-enable -->
