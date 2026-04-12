# Patch Targeting

Every PATCH contract needs a way to say where a mutation applies.

Most of the time that means one exact location. Sometimes it means a query over
the document. And sometimes the default pointer or selector implementation is
not the right fit for your domain.

This page covers all three.

## Exact and Query-Based Targeting

Use `JSONPointer[T]` when the operation is aimed at one concrete location.

Use `JSONSelector[T]` when the operation is aimed at one or more matches
described by a query.

```python
from jsonpatchx import JSONPointer, JSONSelector
from jsonpatchx.types import JSONNumber, JSONObject, JSONString, JSONValue

email_path: JSONPointer[JSONString]
balance_path: JSONPointer[JSONNumber]

open_invoices: JSONSelector[JSONObject[JSONValue]]
priority_orders: JSONSelector[JSONObject[JSONValue]]
```

By default, `JSONSelector` uses standardized
[RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535) JSONPath syntax.

A selector field can therefore accept expressions such as:

```json
"$.invoices[?(@.status == 'unpaid')].dueDate"
```

## Typed Pointers

`JSONPointer[T]` is the default targeting tool when an operation means "this
exact location."

It parses a JSON Pointer string up front. The target and its type are enforced
when you exercise it:

- `get(doc)` resolves the path and validates the result against `T`
- `add(doc, value)` validates the value before writing it
- `remove(doc)` validates the existing target before removing it

For preflight checks:

- `is_gettable()`, `is_addable()`, and `is_removable()` let you ask "would this
  succeed?" without the try-except ceremony

For pointer relationships:

- `is_parent_of()` and `is_child_of()` help validate pointer relationships

If you need to reason about path components directly, `parts` exposes the
unescaped path segments.

`JSONPointer` is also a subtype of `str`, so it still behaves like a pointer
string in the usual places.

## Selector Semantics

Selectors are more expressive than pointers. They also raise questions that
pointer-based operations do not.

If an operation can match many locations, the contract should say what happens
when:

- there are zero matches
- there are multiple matches
- match ordering is not meaningful
- one mutation succeeds and a later one fails

That is why selector-heavy behavior usually belongs in custom operations rather
than being hidden behind a payload that looks exactly like plain RFC 6902.

## Typed Selectors

`JSONSelector[T]` is intentionally small:

- `get(doc)` returns an iterable of validated matches
- `add(doc, value)` adds at all matching paths
- `remove(doc)` removes all matching paths

Two details matter in practice.

First, do not treat the ordering of matches as part of the contract unless your
operation explicitly says so.

Second, if an operation mutates in place and later hits an error, the document
may already be partially updated. If you allow that behavior, document it
plainly.

## Why Pointers Are Still the Default

Most PATCH contracts should still prefer pointers whenever one exact location is
the clearest thing to name.

Use a selector when it makes the request easier to say honestly:

- match items by stable IDs or attributes
- perform a batch mutation where multi-match behavior is part of the contract
- avoid brittle array-position targeting when the structure can move

Do not use a selector just because it feels more advanced. The point is better
targeting, not more clever targeting.

## JSONPath Is Opt-In

JsonPatchX does not treat JSONPath as a replacement for JSON Pointer.

The default PATCH story stays grounded in standard pointer semantics. `JSONPath`
enters the picture when query-style targeting is actually the better fit.

That is the right level of ambition here: richer targeting when it helps, not a
wholesale rewrite of the standard path model.

## Alternative Backends

You are not limited to the default implementations.

For either shape, you can provide your own implementation:

```python
CustomPointer = JSONPointer[JSONValue, MyPointerImplementation]
CustomSelector = JSONSelector[JSONValue, MySelectorImplementation]
```

As long as the custom type satisfies the `PointerBackend` or `SelectorBackend`
protocol, you can keep using the typed surface directly. There is no need to
drop down to raw `.ptr` strings just because your domain needs different
resolution rules.

For the backend protocol itself, see the developer-facing
[Pointer Backends](../developer-reference/pointer-backends.md) reference.
