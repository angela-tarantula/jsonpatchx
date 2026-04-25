# Patch Targeting

JsonPatchX supports three ways to target a mutation:

- exact locations with `JSONPointer[T]` (default:
  [RFC 6901](https://datatracker.ietf.org/doc/html/rfc6901) JSON Pointer, as
  used by RFC 6902)
- query-based targeting with `JSONSelector[T]` (default:
  [RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535) JSON Path)
- custom backends when the defaults are not the right fit

## The `JSONPointer` Surface

`JSONPointer[T]` is the default targeting tool when an operation means "this
exact location."

It parses the pointer string up front. The target and its type are enforced when
you exercise it.

- `get(doc)` resolves the path and validates the result against `T`
- `add(doc, value)` validates the value before writing it
- `remove(doc)` validates the existing target before removing it
- `is_gettable()`, `is_addable()`, and `is_removable()` let you ask "would this
  succeed?" without the try-except ceremony.
- `is_valid_type(target)` checks whether an arbitrary value satisfies `T`
- `is_parent_of()` and `is_child_of()` help validate pointer relationships
- `parts` exposes the unescaped path segments
- As a subtype of `str`, it behaves like a pointer string when you want
  string-compatible comparison, hashing, and logging

Root-level deletion and recreation use a separate missing-document state rather
than treating “no document” as a JSON value. See
[Type System Notes](../developer-reference/type-system-notes.md#missing-document-sentinel)
for the precise `MISSING` semantics.

## The `JSONSelector` Surface

`JSONSelector[T]` is for query-based targeting. By default, it uses the JSON
Path syntax standardized in
[RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535):

```json
"$.invoices[?(@.status == 'unpaid')].dueDate"
```

> Note: The
> [built-in JSONPath backend](https://github.com/jg-rp/python-jsonpath) is
> RFC-compliant out of the box, except on Python 3.14 and later, where
> [python-jsonpath](https://github.com/jg-rp/python-jsonpath)'s
> [`iregexp-check`](https://github.com/jg-rp/rust-iregexp) dependency is not yet
> compatible with free-threaded Python. On Python 3.14+, this only affects regex
> compliance: `match()` and `search()` fall back to Python's built-in `re`, and
> regex patterns are not validated against
> [RFC 9485](https://datatracker.ietf.org/doc/html/rfc9485) I-Regexp.

### Selector Semantics

Selectors are more expressive than pointers. They also raise questions that
pointer-based operations do not. JsonPatchX takes a simple default position:

- zero matches return `[]` from `getall()` and leave `addall()` or `removeall()`
  unchanged
- multiple matches are all returned without any ordering guarantee
- mutation helpers apply matches sequentially without any ordering guarantee

### Selector Methods

Similar to `JSONPointer[T]`, it parses the query expression string upfront, and
its target type is enforced when you exercise it:

- `getall(doc)`, `addall(doc, value)`, and `removeall(doc)`
- `get_pointers(doc)` when you want the matched exact pointers for case-by-case
  handling
- `is_gettable()`, `is_addable()`, and `is_removable()`
- `is_valid_type(target)`

It is also a subtype of `str`.

## Using Your Own Resolver

If you need your own implementation of RFC 6901 or RFC 9535, you can plug it
into `JSONPointer[T, CustomPointer]` or `JSONSelector[T, CustomSelector]`:

```python
path: JSONPointer[JSONValue, MyPointerImplementation]
matches: JSONSelector[JSONValue, MySelectorImplementation]
```

Your implementation must satisfy either the
[`PointerBackend`](../developer-reference/custom-pointers-and-selectors.md) or
[`SelectorBackend`](../developer-reference/custom-pointers-and-selectors.md)
protocol.

If you want to study deliberately extended alternatives, two useful references
are
[`python-jsonpath`'s `JSONPointer`](https://jg-rp.github.io/python-jsonpath/pointers/)
(among other things, it has interoperability with relative pointers) and
[`jsonpath-python`](https://github.com/sean2077/jsonpath-python) for
feature-first JSONPath querying and updating. They are not drop-in replacements
for JsonPatchX's default backends, but they can be good starting points when
designing a custom adapter.

If you do need the underlying pointer/selector instance, the `ptr` property
exposes it on both `JSONPointer` and `JSONSelector`.

> Note: `ptr` exposes the raw backend. If you use it directly, JsonPatchX will
> not enforce the `T` in `JSONPointer[T]` or `JSONSelector[T]`; use
> `is_valid_type()` when you need that check.
