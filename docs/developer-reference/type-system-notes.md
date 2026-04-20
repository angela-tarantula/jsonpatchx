# Type System Notes

This page explains the core JSON helper types in `jsonpatchx/types.py`.

The important idea is simple: JsonPatchX keeps its JSON types true to JSON, not
to Python convenience behavior.

## JSON Semantics

The helper family models JSON values with strict runtime behavior:

- strings stay strings
- booleans stay booleans
- numbers are `int` or finite `float`
- arrays are concrete `list` values
- objects are concrete `dict[str, ...]` values

That means JsonPatchX does not quietly accept Python conveniences that would
blur a PATCH contract.

Examples:

- `"2"` does not coerce to `2`
- `True` is not treated as a JSON number just because Python makes `bool` a
  subtype of `int`
- `float("nan")` and `float("inf")` are rejected
- tuple-like containers are not accepted as runtime JSON arrays

Those constraints are deliberate. PATCH payloads are usually crossing trust
boundaries, so the library prefers explicit rejection over clever coercion.

## Helper Types

The core helper family is:

- `JSONBoolean`
- `JSONNumber`
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONScalar`
- `JSONContainer[T]`
- `JSONValue`

`JSONScalar` is the union of the four scalar helpers.

`JSONContainer[T]` is the union of `JSONArray[T]` and `JSONObject[T]`.

`JSONValue` is the full recursive JSON value type used when a field or API
surface wants an actual JSON document or subdocument.

## Type Aliases at Check Time, Pydantic Helpers at Runtime

The names in `types.py` are doing two jobs.

During static type checking, the scalar and container helpers are pleasant type
aliases such as:

```python
type JSONString = str
type JSONArray[T] = list[T]
```

At runtime, those same names become small Pydantic-aware helper classes with
custom validation and JSON Schema behavior.

That split exists because plain aliases were not enough to get all three goals
at once:

- strict runtime validation
- readable static types
- stable and minimal OpenAPI output

So when `types.py` looks more complicated than the JSON domain itself, that is
usually because the implementation is balancing those three requirements on
purpose.

## Published Schemas

The runtime helper classes are not there only for validation. They also shape
the published schema surface.

This matters because some obvious-looking alternatives produce poor OpenAPI:

- helper aliases can become noisy named schema components
- replacing generated schema wholesale can hide useful field keywords
- pushing strictness to the wrong level can make Pydantic accept values that a
  JSON contract should reject

One design goal here is that constraints layered on top of helper types should
survive into the published schema instead of disappearing.

For example, `Annotated[JSONNumber, Field(gt=4)]` should still advertise that
the value must be greater than `4`.

In the current stack, that lower bound is preserved, but not in the desired
OpenAPI form: it is emitted as Pydantic's `gt: 4` metadata rather than
normalized OpenAPI `exclusiveMinimum: 4`.

That is not unique to `JSONNumber`. Plain `Annotated[int | float, Field(gt=4)]`
currently behaves the same way under the project's OpenAPI 3.1 output.

`JSONValue` is the clearest example. At runtime it validates against the full
strict recursive JSON union, but its published JSON Schema is deliberately
inlined as `{}` so helper internals do not leak into OpenAPI as a named
component.

Contributors should treat that as part of the design, not an implementation
accident.

Likewise, `JSONBoolean | JSONNull` currently renders as:

```yaml
anyOf:
  - type: boolean
  - type: null
```

That is normal for OpenAPI 3.1. In older OpenAPI 3.0 tooling, the same concept
often appeared as `nullable: true` on a base type instead.

## JSONValue and JSONBound

`JSONValue` and `JSONBound` are related, but they are not interchangeable.

`JSONValue` is the actual Pydantic-aware JSON value model. Use it when runtime
validation should accept only genuine JSON values with the strict rules above.

`JSONBound` is a typing bound for generics. It means “JSON-shaped enough to be a
valid type parameter bound,” not “accepted as a runtime JSON payload.”

Examples:

- `JSONScalar` is assignable to both `JSONValue` and `JSONBound`
- `JSONArray[JSONValue]` is assignable to both `JSONValue` and `JSONBound`
- `JSONArray[JSONScalar]` is only assignable `JSONBound`

If `JSONPointer[T]` was bound by `JSONValue`,
`JSONPointer[JSONArray[JSONScalar]]` would be a type checker error. So `T` is
bound by `JSONBound` instead, with the compromise that it's overly permissive.
For example, `JSONPointer[tuple[int]]` is "type-safe."

For more about why it has to be this way, see
[Limitations in Python's Type System](limitations-in-python-type-system.md).

## Missing Document Sentinel

`MISSING` is the runtime sentinel for “the document no longer exists.”

A custom operation that intends to delete the whole document should return
`MISSING`, not `None`. `None` is JSON `null`. `MISSING` means document deletion.

That is allowed at the operation layer because it keeps composed operations
simple. `ReplaceOp`, for example, can implement root replacement as `RemoveOp`
followed by `AddOp` without a root-only special case.

For the purpose of runtime type compatibility with a missing document, `MISSING`
is accepted by the JSON helper family:

- `JSONBoolean`
- `JSONNumber`
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONValue`

So an individual operation is allowed to delete the document even if the
enclosing patch contract later rejects that final state. This is useful for
composability, but a completed patch is still usually expected to finish as a
real document at higher-level boundaries such as model revalidation or HTTP
response serialization.
