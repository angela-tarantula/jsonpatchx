# JSONPath and Alternative Selectors

JSON Pointer and JSONPath solve different problems.

A JSON Pointer is an address.

A JSONPath expression is a query.

Modern PATCH APIs eventually want both.

## Why JSONPath matters here

Plain JSON Patch inherits the strengths and limits of pointer-based targeting.
It is good when the caller knows the exact location to mutate. It is awkward
when the caller wants to say “the line item whose `sku` is `A42`” or “all open
invoices for this customer.”

That is one of the reasons JsonPatchX treats richer targeting as part of the
project vision instead of a side note.

[JSONPath](https://datatracker.ietf.org/doc/html/rfc9535) is now standardized.
That makes it easier to discuss selector-style PATCH contracts as a serious
design direction rather than a collection of one-off experiments.

## Current scope in JsonPatchX

JsonPatchX is honest about where support stands today.

The core library is still centered on single-target pointer semantics. The
default path type is an
[RFC 6901](https://datatracker.ietf.org/doc/html/rfc6901) JSON Pointer.

What you can do today is bind a different backend to `JSONPointer[T, Backend]`:

```python
from jsonpath import JSONPointer as JsonPathPointer

from jsonpatchx import JSONPointer
from jsonpatchx.types import JSONValue


class URIJsonPathPointer(JsonPathPointer):
    def __init__(self, pointer: str) -> None:
        super().__init__(pointer, uri_decode=True, unicode_escape=False)


path: JSONPointer[JSONValue, URIJsonPathPointer]
```

That keeps alternative path syntax opt-in. If you want plain RFC 6901 behavior,
keep the default backend and nothing changes.

## Where selector behavior should live

The important design choice is this:

Multi-match behavior should be explicit in the operation, not smuggled in
through an otherwise familiar RFC operation.

If an operation can target multiple matches, it needs to define things such as:

- what happens when there are zero matches
- whether multiple matches are applied in deterministic order
- how overlapping writes are handled
- whether partial success is possible or forbidden

That is why selector-heavy mutation patterns usually belong in custom
operations. The operation contract should own the fan-out semantics.

## A good use of JSONPath in JsonPatchX

The good use of JSONPath here is not “replace JSON Pointer everywhere.”

The good use is:

- keep RFC pointer semantics as the default
- introduce query-like targeting only where the domain needs it
- make selector semantics explicit and testable
- keep it opt-in

That is exactly the kind of safer experimentation JsonPatchX is trying to create
room for.
