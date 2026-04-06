# JSONSelector and Alternative Targeting

Pointers work well when the caller already knows the exact location to patch.

They get awkward as soon as the caller knows which item they mean but not where
it sits today. “The invoice with ID `inv_42`” is a stable idea. `"/invoices/3"`
often is not.

That is where selector-style targeting starts to matter.

## `JSONPointer[T]` and `JSONSelector[T]` are different tools

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

By default, `JSONSelector` uses standardized JSONPath syntax.

A selector field can therefore accept expressions such as:

```json
"$.invoices[?(@.status == 'open')]"
```

The important part is not that JSONPath is fashionable. The important part is
that query-style targeting now has a standard shape.

## Selector semantics need to be explicit

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

## The basic selector surface

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

## Pointers are still the default for a reason

Most PATCH contracts should still prefer pointers whenever one exact location is
the clearest thing to name.

Use a selector when it makes the request easier to say honestly:

- match items by stable IDs or attributes
- perform a batch mutation where multi-match behavior is part of the contract
- avoid brittle array-position targeting when the structure can move

Do not use a selector just because it feels more advanced. The point is better
targeting, not more clever targeting.

## JSONPath is opt-in, not a replacement story

JsonPatchX does not treat JSONPath as a replacement for JSON Pointer.

The default PATCH story stays grounded in standard pointer semantics. `JSONPath`
enters the picture when query-style targeting is actually the better fit.

That is the right level of ambition here: richer targeting when it helps, not a
wholesale rewrite of the standard path model.

## Custom pointer and selector implementations

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
