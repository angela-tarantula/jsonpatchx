# Custom Pointers and Selectors

JsonPatchX is targeting-backend agnostic.

`JSONPointer` and `JSONSelector` both have default backends, but the library can
bind alternative implementations when a domain needs different parsing,
traversal, or query rules.

That flexibility is useful. It also needs guardrails.

## What a pointer backend is

A pointer backend is the object behind `JSONPointer[T, Backend]`.

JsonPatchX expects a backend to do a small number of things well:

- parse a pointer string
- expose unescaped path parts
- rebuild itself from parts
- resolve itself against a JSON document
- round-trip through a canonical string form

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

If you want to study an intentionally extended pointer implementation, see
[`python-jsonpath`'s `JSONPointer`](https://jg-rp.github.io/python-jsonpath/pointers/),
which documents non-standard features beyond strict RFC 6901, like
interoperability with relative pointers.

## What a selector backend is

A selector backend is the object behind `JSONSelector[T, Backend]`.

JsonPatchX expects it to do two things:

- parse a selector string
- yield exact matched pointers against a JSON document

## Minimal selector backend shape

```python
from collections.abc import Iterable

from jsonpatchx.backend import PointerBackend
from jsonpatchx.types import JSONValue


class MySelectorBackend:
    def __init__(self, selector: str) -> None:
        ...

    def pointers(self, doc: JSONValue) -> Iterable[PointerBackend]:
        ...

    def __str__(self) -> str:
        ...
```

## Selector Rules That Matter In Practice

`pointers(doc)` should yield zero or more concrete pointer objects, not abstract
query nodes or backend-specific match wrappers.

Each yielded pointer should identify the exact location selected by the query.
If the selector and the yielded pointers drift apart, selector-backed mutation
will target the wrong place.

Each yielded pointer should satisfy `PointerBackend`. JsonPatchX uses those
returned pointer objects directly when it wraps matches as typed `JSONPointer`
values.

Selector mutation is intentionally thin. JsonPatchX applies matched pointers
sequentially in the backend's iteration order and does not impose extra
overlap-resolution or ordering rules on top.

JsonPatchX is slightly more permissive at runtime than this protocol surface for
the built-in JSONPath backend. Upstream `python-jsonpath` exposes richer match
objects, but JsonPatchX only exports exact locations through `PointerBackend`
instances. Matched values are still revalidated through `JSONSelector[T]` and
`JSONPointer[T]` before typed operations use them.

The more important limitation is standards compliance, not upstream's `object`
annotation. Out of the box, JsonPatchX's built-in JSONPath backend follows the
RFC 9535 path. The exception is Python 3.14 and later, where the upstream
[`iregexp-check`](https://github.com/jg-rp/rust-iregexp) dependency behind
`python-jsonpath[strict]` is not yet compatible with free-threaded Python.

JsonPatchX still uses `JSONPathEnvironment(strict=True)` there, so this only
affects regular expression compliance: `match()` and `search()` fall back to
Python's built-in `re`, and regular expression patterns are not validated
against RFC 9485 I-Regexp.

Like pointer backends, selector backends should be immutable or otherwise safe
to reuse.

For a feature-first JSONPath implementation with deliberate non-standard query
operators, sorting, and `update()` support, see
[`jsonpath-python`](https://github.com/sean2077/jsonpath-python). It is useful
inspiration for custom selector backends, but JsonPatchX still needs concrete
`PointerBackend` values for each matched location.
