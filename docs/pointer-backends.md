# Pointer Backends

JsonPatchX uses a pointer backend for path parsing and traversal.

Default behavior uses RFC 6901 JSON Pointer. Advanced users can bind a custom
backend when default semantics are not enough.

## What a Backend Must Provide

A backend implements the `PointerBackend` protocol:

- constructible from a path string
- `parts` (unescaped tokens)
- `from_parts(parts)` round-trip constructor
- `resolve(doc)` traversal method
- canonical string form via `__str__`

## When To Use a Custom Backend

Use a custom backend if you need:

- non-RFC pointer syntax (for example dot-path style)
- custom escaping/tokenization rules
- domain-specific traversal/resolution behavior

## Binding a Backend

Bind backend type at the pointer field level:

```python
from jsonpatchx import JSONPointer, JSONValue

class DotPointer(...):
    ...

path: JSONPointer[JSONValue, DotPointer]
```

Operations that depend on custom backend behavior should make their type-gating
guarantees explicit in `apply()`.

## Scope Today

JsonPatchX currently supports `PointerBackend` customization.

Selector-style multi-target backends are planned as a separate concern. This is
why backend docs stay focused on single-target pointer semantics for now.
