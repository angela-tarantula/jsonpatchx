# Custom Pointers and Selectors

JsonPatchX is targeting-backend agnostic.

`JSONPointer` and `JSONSelector` both have default backends, but the library can
bind alternative implementations when a domain needs different parsing,
traversal, or query rules.

The built-in defaults are `DEFAULT_POINTER_CLS` and `DEFAULT_SELECTOR_CLS` in
`jsonpatchx.backend`.

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

**Do not raise `TypeError` for invalid pointer strings.** `TypeError` from a
constructor is treated as a backend misconfiguration error, not as an invalid
pointer string, so it propagates raw rather than being wrapped in
`InvalidJSONPointer`. Any other exception is wrapped. In a FastAPI route, an
unhandled `TypeError` maps to a 500 rather than a 422.

Its string form should round-trip cleanly. Constructing a backend from a string,
converting it back to a string, and constructing it again should produce an
equivalent pointer.

`from_parts(parts)` should also round-trip. If a backend exposes parts, those
parts should be enough to rebuild an equivalent backend instance.

The backend should be immutable or safe to reuse. JsonPatchX may cache backend
instances.

The backend defines its own syntax. There is no universal root string across
every possible backend. This is why `JSONPointer.is_root(doc)` takes a document
argument rather than simply checking for `""`: the backend itself determines
what counts as root given the document, so the check must go through the
backend.

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

**Do not raise `TypeError` for invalid selector strings.** The same rule applies
as for pointer backends: `TypeError` from a constructor is treated as a backend
misconfiguration error and propagates raw, while any other exception is wrapped
in `InvalidJSONSelector` and surfaces as a Pydantic `ValidationError`. In a
FastAPI route, an unhandled `TypeError` maps to a 500 rather than a 422.

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
RFC 9535 path only if the optional `jsonpatchx[strict-jsonpath]` extra is
installed:

```sh
pip install jsonpatchx[strict-jsonpath]
```

> **Warning:** Do not install `jsonpatchx[strict-jsonpath]` on a free-threaded
> Python build (3.13t, 3.14t, and later free-threaded variants). Its upstream
> [`iregexp-check`](https://github.com/jg-rp/rust-iregexp) dependency segfaults
> on import there. There is no PEP 508 dependency marker that can select a
> standard build over a free-threaded build of the same Python version, so
> JsonPatchX cannot block this installation combination for you; only install
> `strict-jsonpath` on a standard (GIL) interpreter.

JsonPatchX still uses `JSONPathEnvironment(strict=True)` regardless of whether
`strict-jsonpath` is installed, so the effect of omitting it is limited to
regular expression compliance: `match()` and `search()` fall back to Python's
built-in `re`, and regular expression patterns are not validated against RFC
9485 I-Regexp.

Like pointer backends, selector backends should be immutable or otherwise safe
to reuse.

For a feature-first JSONPath implementation with deliberate non-standard query
operators, sorting, and `update()` support, see
[`jsonpath-python`](https://github.com/sean2077/jsonpath-python). It is useful
inspiration for custom selector backends, but JsonPatchX still needs concrete
`PointerBackend` values for each matched location.
