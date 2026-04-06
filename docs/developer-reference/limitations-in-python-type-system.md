# Limitations in Python's Type System

This page explains one specific typing problem in JsonPatchX from first
principles.

The problem is: **how to choose a bound for `T` in `JSONPointer[T]`**.

## Why this exists at all

`JSONPointer[T]` is a typed pointer. The type parameter `T` describes what shape
of JSON value the pointer is expected to resolve to.

So we need a bound for `T` that accepts recursively JSON-shaped helper types.

For example, we want this to be valid:

```python
JSONPointer[JSONObject[JSONArray[JSONBoolean]]]
```

## The intuitive recursive bound

The intuitive recursive idea is:

```python
type JSONBound = JSONScalar | JSONContainer[JSONBound]
```

This expresses the recursive intent clearly.

## Why this is hard with mutable invariant containers

In JsonPatchX, `JSONContainer[T]` is built from mutable containers (`list` and
`dict`), and those are invariant.

Invariance means:

- `JSONContainer[X]` is not a subtype of `JSONContainer[Y]` unless `X` and `Y`
  are exactly the same type.

That is usually correct for type safety.

### Concrete safety example

If mutable containers were treated as covariant, this would be unsafe:

```python
ints: list[int] = [1, 2]
values: list[object] = ints  # pretend covariance for mutable list
values.append("oops")
# ints is now [1, 2, "oops"] -> violates list[int]
```

So invariance for mutable containers is good and normal.

### Why it hurts this bound

For a nested type like:

```python
JSONObject[JSONArray[JSONBoolean]]
```

matching `JSONContainer[JSONBound]` would require inner exact matches under
invariance, which is stricter than "recursively JSON-shaped".

Another way to say it:

- `JSONContainer[JSONBound]` behaves like "container of exactly `JSONBound`"
- what we need is "container of some subtype of the recursive JSON domain"

## What we actually want to express

We want an existential-style constraint:

```text
JSONContainer[T] where T <: JSONValue
```

Equivalent ideal recursive form:

```python
type JSONBound = JSONScalar | JSONContainer[T: JSONBound]
```

That is the intended shape.

Python typing cannot currently express this existential recursive constraint in
the alias/annotation shape we need for `JSONPointer[T]`.

## Workaround used in JsonPatchX

The workaround is to use covariant immutable interfaces in the bound:

```python
type JSONBound = (
    JSONScalar | Sequence[JSONBound] | Mapping[str, JSONBound]
)
# Use it like: T = TypeVar("T", default=JSONValue, bound=JSONBound)
```

Why this works better:

- `Sequence` and `Mapping` are read-only interface types and are covariant in
  their value parameters
- this allows recursive JSON-shaped nested types to pass the `JSONPointer[T]`
  bound more naturally than mutable invariant containers

This is a practical bound that works well today, but it's not the ideal form:

- `Sequence`/`Mapping` bounds are broader than JsonPatchX runtime JSON container
  semantics.
- So static typing may accept container shapes that are not concrete
  `list`/`dict` JSON containers.
- Runtime validation still enforces actual JsonPatchX JSON rules (`list` for
  arrays, `dict[str, ...]` for objects), so those broader static cases are
  rejected at runtime.

## Why not model `JSONArray` / `JSONObject` as immutable?

Another workaround would be to redesign JsonPatchX container modeling around
immutable structures.

That was not chosen because JsonPatchX patch semantics intentionally operate
with standard Python JSON-like data (`list`/`dict`) and support in-place
mutation modes. Switching to immutable container primitives would add
substantial complexity and friction across runtime behavior, interoperability,
and user expectations.

So the project keeps runtime container semantics practical, and applies the
typing workaround at the generic-bound layer.

## Why both `JSONValue` and `JSONBound` exist

They solve different problems:

- `JSONValue` is the semantic recursive JSON model used in runtime validation
  and API contracts.
- `JSONBound` is a typing-bound utility for generics like `JSONPointer[T]`.

So `JSONValue` is the data model; `JSONBound` is the bound used to make typed
pointer generics workable under current Python typing limits.

## Want to help push this forward?

Yes, seriously: if you want to help draft a PEP (or related typing proposal) for
recursive existential constraints like this, please reach out in JsonPatchX
discussions. I would love collaborators on it.

Impact beyond JSON: this kind of typing support would help represent any
mutable, recursively nested generic data model.

Most immutable/read-only models can sidestep this by using covariant interface
types; the gap is mainly for mutable recursive models.
