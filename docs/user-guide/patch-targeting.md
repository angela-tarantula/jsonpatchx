# Patch Targeting

JsonPatchX supports three ways to target a mutation:

- exact locations with `JSONPointer[T]` (default:
  [RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) JSON Pointer)
- query-based targeting with `JSONSelector[T]` (default:
  [RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535) JSON Path)
- custom backends when the defaults are not the right fit

## The JSONPointer Surface

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
- as a subtype of `str`, it behaves like a pointer string when you want
  string-compatible comparison, hashing, and logging

## The JSONSelector Surface

`JSONSelector[T]` is for query-based targeting. By default, it uses the JSON
Path syntax standardized in
[RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535):

```json
"$.invoices[?(@.status == 'unpaid')].dueDate"
```

### Selector Semantics

Selectors are more expressive than pointers. They also raise questions that
pointer-based operations do not. JsonPatchX takes a simple default position:

- zero matches is a resolution error

- multiple matches are all returned

- stable match ordering is not guaranteed

### Selector Methods

Similar to `JSONPointer[T]`:

- `get(doc)`, `add(doc, value)`, and `remove(doc)`
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

If you do need the underlying pointer/selector instance, the `ptr` property
exposes it on both `JSONPointer` and `JSONSelector`.
