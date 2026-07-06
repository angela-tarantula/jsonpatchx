# Type System Limitations

Two related limitations show up when working with JsonPatchX's JSON helper
types. Both come from the same root cause: Python's type system cannot express
recursive mutable container constraints the way we'd want.

This page explains both from first principles, with actionable guidance for
each.

---

## Limitation 1: Narrowly-typed JSON containers are not assignable to `JSONValue`

The most common practical surprise: you narrow a pointer's type parameter to get
a typed resolved value, build a result from it, and the type checker flags the
return.

The limitation surfaces whenever the pointer's type parameter is a narrower
container, for example `JSONPointer[JSONArray[JSONNumber]]`, and the result is
returned directly from `apply`.

```python
from typing import Literal
from jsonpatchx import JSONPointer, JSONArray, JSONNumber, JSONValue
from jsonpatchx.schema import OperationSchema

class DoubleAllOp(OperationSchema):
    op: Literal["double_all"]
    path: JSONPointer[JSONArray[JSONNumber]]

    def apply(self, doc: JSONValue) -> JSONValue:
        numbers = self.path.get(doc)  # type: JSONArray[JSONNumber] = list[int | float]
        return [n * 2 for n in numbers]  # type error: list[int | float] not assignable to JSONValue
        # JSONValue requires list[JSONValue] and list is invariant
```

The same issue applies to any narrowly-typed container:
`JSONObject[JSONString]`, `JSONArray[JSONBoolean]`, and so on; anything where
the element type is not exactly `JSONValue`.

To understand why, you need to understand invariance.

### Why `list` is invariant

Imagine Python treated `list` as covariant, so `list[int]` would be a subtype of
`list[object]`. Then this code would typecheck:

```python
ints: list[int] = [1, 2]
things: list[object] = ints   # pretend covariance
things.append("oops")         # now ints is [1, 2, "oops"]  # broken
```

This would allow inserting wrong-typed values through an alias. So Python
correctly makes `list` (and `dict`) **invariant**: `list[int]` is only a subtype
of `list[int]`, not `list[object]` or anything else.

### Why this blocks narrowly-typed containers

`JSONValue` is defined, for type checkers, as:

```python
type JSONValue = JSONScalar | JSONContainer[JSONValue]
# where JSONContainer[T] = JSONArray[T] | JSONObject[T]
```

So `JSONValue` includes `JSONArray[JSONValue]`, a list whose items are
themselves `JSONValue`. But `JSONArray[JSONNumber]` is a list whose items are
`JSONNumber`, which is a _narrower_ type than `JSONValue`.

Because `list` is invariant, `list[JSONNumber]` is **not** a subtype of
`list[JSONValue]`, even though `JSONNumber` is a subtype of `JSONValue`. The
same holds for any other narrowing: `list[JSONString]`,
`dict[str, JSONBoolean]`, and so on. The type checker rejects them all.

This is not a bug in JsonPatchX; it is a correct consequence of invariance.

### What to do: cast at the return site

Cast the return value to `JSONValue`. The limitation is in Python's type system,
not in the code: you know the value is `JSONNumber`, you are treating it as
`JSONValue`, and that is correct. `cast` is honest about that reasoning in a way
that `# type: ignore` is not.

```python
from typing import cast
from jsonpatchx import JSONValue

def apply(self, doc: JSONValue) -> JSONValue:
    numbers = self.path.get(doc)             # JSONArray[JSONNumber]
    result: list[int | float] = [n * 2 for n in numbers]
    return cast(JSONValue, result)
```

The `cast` is safe: it tells the type checker the value is `JSONValue` without
changing the runtime object. The patch engine validates the result of each
`apply()` call against `JSONValue` automatically. If your op returns something
that is not valid JSON (for example, a `datetime` or a plain Python object), a
`PatchInternalError` is raised with the op index and payload as context, and the
original `ValidationError` as `__cause__`. For `JsonPatchFor[Model]`, the
patched document is additionally validated against the target model schema after
all ops have run.

---

## Limitation 2: Why `JSONBound` exists: the TypeVar bound problem

`JSONPointer[T]` is a typed pointer parameterized by the type of value it
resolves to. To constrain `T` to JSON-shaped types, we need a TypeVar bound.

The intuitive recursive bound would be:

```python
type JSONBound = JSONScalar | JSONContainer[JSONBound]
```

But this runs into the same invariance problem. For a nested type like
`JSONObject[JSONArray[JSONBoolean]]`:

- matching against `JSONContainer[JSONBound]` under invariance requires inner
  types to be _exactly_ `JSONBound`
- but the inner types are `JSONArray[JSONBoolean]`, which is a concrete
  narrowing, not `JSONBound` itself

What we actually want to express is an existential constraint:

```text
JSONContainer[T] where T <: JSONBound   (recursively)
```

Python's type system cannot express this today.

### The workaround

Instead of mutable container types (invariant), the bound uses read-only
interface types (covariant):

```python
type JSONBound = JSONScalar | Sequence[JSONBound] | Mapping[str, JSONBound]
```

`Sequence` and `Mapping` are covariant in their value parameters, so
`Sequence[JSONNumber]` _is_ a subtype of `Sequence[JSONBound]`. This lets nested
types like `JSONObject[JSONArray[JSONBoolean]]` satisfy the bound.

The trade-off: `Sequence` and `Mapping` are broader than the JSON container
semantics; they accept `tuple` and custom mappings, which are not valid JSON
containers. The static type system is permissive here; runtime validation
enforces the actual rules (`list` for arrays, `dict[str, ...]` for objects).

### `JSONValue` vs `JSONBound`

|            | `JSONValue`                          | `JSONBound`                         |
| ---------- | ------------------------------------ | ----------------------------------- |
| Purpose    | Data model for patch contracts       | TypeVar bound for generics          |
| Runtime    | Full Pydantic validation, strict     | No runtime behavior                 |
| Containers | `list` and `dict[str, ...]` only     | Any `Sequence` or `Mapping`         |
| Use when   | Annotating fields, method signatures | `T = TypeVar("T", bound=JSONBound)` |

---

## Why not use `Sequence`/`Mapping` in `JSONValue` and `apply` signatures?

`JSONBound` uses `Sequence` and `Mapping` because they are covariant, which
dissolves the invariance problem. A natural follow-up question is: why not use
the same covariant types in `JSONValue` and in `apply` return signatures?

The reason is precision. `Sequence` accepts `tuple`, `str`, and any custom
sequence; `Mapping` accepts any mapping. Neither constrains you to actual JSON
containers. `JSONValue` uses `list` and `dict[str, ...]` precisely because those
are the only valid JSON containers, and that precision is enforced by Pydantic
at validation time.

Patch operations also mutate documents in place. `Sequence` and `Mapping` are
read-only interfaces; expressing mutation through them would require casting
back to concrete types at every operation site.

`JSONBound` exists only as a TypeVar bound for static generics, where the
permissiveness is acceptable because runtime validation still enforces the real
rules. It is not the right type for method signatures or field annotations,
which is exactly what `JSONValue` is for.

---

## Want to help push this forward?

If you want to help draft a PEP (or related typing proposal) for recursive
existential constraints like this, reach out in JsonPatchX discussions. This
kind of typing support would help any mutable, recursively nested generic data
model, not just JSON.

<!--
TODO: create a GitHub discussion where readers can upvote support for this PEP.
      The goal is to gather public signal (upvotes/comments) that demonstrates demand
      when the PEP is formally proposed. Once the discussion exists, replace this
      section with a link to it and a call to action: "upvote if you'd like to see
      this in Python."
-->
