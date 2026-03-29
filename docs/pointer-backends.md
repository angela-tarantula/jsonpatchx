# Pointer Backends

JsonPatchX uses a pointer backend to resolve and mutate paths. The default
backend is RFC 6901 JSON Pointer syntax.

This page covers:

- the default backend behavior and what operations assume
- how to bind a custom pointer backend to `JSONPointer[T, Backend]`
- backend-specific operation design guidelines
- current scope (`PointerBackend`) and future direction (selector backends)
