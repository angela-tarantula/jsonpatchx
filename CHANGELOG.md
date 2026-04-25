# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- textlint-disable -->

## [Unreleased]

### Added

- `DEFAULT_POINTER_CLS` and `DEFAULT_SELECTOR_CLS` are now documented as
  supported public API for binding JsonPatchX's built-in pointer and selector
  backends explicitly.
- Added `TargetState.MISSING` for the root-document `MISSING` sentinel case.

### Changed

- Simplified `SelectorBackend` so custom selector backends yield
  `PointerBackend` instances directly through `pointers(doc)`, removing the
  separate `SelectorMatch` wrapper protocol.
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
