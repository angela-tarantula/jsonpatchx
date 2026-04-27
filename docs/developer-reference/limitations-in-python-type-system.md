# Type System Limitations

Two related limitations show up when working with JsonPatchX's JSON helper
types. Both come from the same root cause: Python's type system cannot express
recursive mutable container constraints the way we'd want.

This page explains both from first principles, with actionable guidance for
each.

---

## Limitation 1: `JSONArray[JSONNumber]` is not assignable to `JSONValue`

The most common practical surprise: you write a custom `apply` that returns a
narrowly typed JSON value, and your type checker flags it.

```python
class DoubleAllOp(OperationSchema):
    op: Literal["double_all"]
    path: JSONPointer[JSONValue]

    def apply(self, doc: JSONValue) -> JSONValue:
        numbers = self.path.get(doc)
        return [n * 2 for n in numbers]  # ← type error
        # list comprehension infers list[JSONValue], not narrower;
        # but if you annotate it as JSONArray[JSONNumber], the type
        # checker flags it as not assignable to JSONValue
```

To understand why, you need to understand invariance.

### Why `list` is invariant

Imagine Python treated `list` as covariant — so `list[int]` would be a subtype
of `list[object]`. Then this code would typecheck:

```python
ints: list[int] = [1, 2]
things: list[object] = ints   # pretend covariance
things.append("oops")         # now ints is [1, 2, "oops"] — broken!
```

This would allow inserting wrong-typed values through an alias. So Python
correctly makes `list` (and `dict`) **invariant**: `list[int]` is only a subtype
of `list[int]`, not `list[object]` or anything else.

### Why this blocks `JSONArray[JSONNumber]`

`JSONValue` is defined, for type checkers, as:

```python
type JSONValue = JSONScalar | JSONContainer[JSONValue]
# where JSONContainer[T] = JSONArray[T] | JSONObject[T]
```

So `JSONValue` includes `JSONArray[JSONValue]` — a list whose items are
themselves `JSONValue`. But `JSONArray[JSONNumber]` is a list whose items are
`JSONNumber`, which is a _narrower_ type than `JSONValue`.

Because `list` is invariant, `list[JSONNumber]` is **not** a subtype of
`list[JSONValue]`, even though `JSONNumber` is a subtype of `JSONValue`. So the
type checker rejects it.

This is not a bug in JsonPatchX — it's a correct consequence of invariance.

### What to do

**Option A — cast at the return site.** If you know your operation produces a
valid JSON document, cast:

```python
from typing import cast
from jsonpatchx import JSONValue

def apply(self, doc: JSONValue) -> JSONValue:
    result: list[int] = [n * 2 for n in ...]
    return cast(JSONValue, result)
```

This silences the type checker. It is safe here because `validate_return=True`
is set on `OperationSchema`: the patch engine validates every `apply` return
value against the JSON rules at runtime, so an invalid return raises an error
even if you cast. You are covered.

**Option B — widen the annotation.** Annotate intermediate variables as
`JSONValue` rather than narrower types. Less precise, but avoids the cast:

```python
def apply(self, doc: JSONValue) -> JSONValue:
    items: JSONValue = self.path.get(doc)
    ...
    return result
```

**Option C — accept the limitation and add a `# type: ignore`.** If the
operation is simple and correct, a targeted ignore comment is fine.

In all cases, the runtime is reliable: `validate_return=True` ensures
correctness regardless of what the type checker accepts or rejects.

---

## Limitation 2: Why `JSONBound` exists — the TypeVar bound problem

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
semantics — they accept `tuple` and custom mappings, which are not valid JSON
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

## Why not redesign around immutable containers?

Using immutable types (`tuple`, `frozendict`) would sidestep the invariance
problem. This was not chosen because JsonPatchX patch semantics intentionally
operate on standard Python JSON-like data (`list`/`dict`) and support in-place
mutation. Switching to immutable container primitives would add friction across
runtime behavior, interoperability, and user expectations.

---

## Want to help push this forward?

If you want to help draft a PEP (or related typing proposal) for recursive
existential constraints like this, reach out in JsonPatchX discussions. This
kind of typing support would help any mutable, recursively nested generic data
model — not just JSON.
