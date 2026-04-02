# Pointer Backends

JsonPatchX is pointer-backend agnostic.

The default backend is standard RFC 6901 JSON Pointer behavior, but the library
can bind alternative pointer implementations when a domain needs different
parsing or traversal rules.

That flexibility is useful. It also needs guardrails.

## What a pointer backend is

A pointer backend is the object behind `JSONPointer[T, Backend]`.

JsonPatchX expects a backend to do a small number of things well:

- parse a pointer string
- expose unescaped path parts
- rebuild itself from parts
- resolve itself against a JSON document
- round-trip through a canonical string form

That is it.

The backend does not need to implement your whole mutation story. In fact, it
should not.

## Minimal backend shape

```python
from collections.abc import Iterable, Sequence
from typing import Self

from jsonpatchx.types import JSONValue


class MyPointerBackend:
    def __init__(self, pointer: str) -> None:
        ...

    @classmethod
    def from_parts(cls, parts: Iterable[str]) -> Self:
        ...

    def resolve(self, doc: JSONValue) -> JSONValue:
        ...

    def __str__(self) -> str:
        ...

    @property
    def parts(self) -> Sequence[str]:
        ...
```

If your backend can satisfy that contract, JsonPatchX can use it.

## Rules that matter in practice

A good pointer backend should satisfy a few operational rules.

Its string form should round-trip cleanly. Constructing a backend from a string,
converting it back to a string, and constructing it again should produce an
equivalent pointer.

`from_parts(parts)` should also round-trip. If a backend exposes parts, those
parts should be enough to rebuild an equivalent backend instance.

The backend should be immutable or safe to reuse. JsonPatchX may cache backend
instances.

The backend defines its own syntax. There is no universal root string across
every possible backend.

## Keep single-target semantics in the backend

This is the most important design rule.

Backends are a good place to change syntax or traversal semantics.

They are not a good place to hide multi-target fan-out behavior behind a
familiar-looking pointer type.

If a PATCH operation can affect many matches, that should be part of the
operation contract itself, where ordering, conflict handling, and zero-match
behavior can be documented and tested directly.

## When to use a backend, and when not to

Use a custom backend when you need:

- different pointer syntax
- different escaping rules
- a different single-target traversal model

Do not use a backend when you really need:

- selector fan-out
- batch mutation semantics
- query-specific conflict rules

Those belong in custom operations.
