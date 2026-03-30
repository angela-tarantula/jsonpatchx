# Contract Evolution and Deprecation

Operation schemas **are your API surface**. Treat them as versioned contracts
with clear, predictable evolution rules.

## Evolution Rules

Follow these principles when changing an operation:

1. **Prefer additive changes** Add new fields instead of changing existing
   behavior.

2. **Use backward-compatible defaults** New fields must default to existing
   behavior so current clients continue to work unchanged.

3. **Reserve new `op` values for breaking changes** If semantics change in a way
   that could break existing clients, introduce a new `op` literal instead of
   modifying the existing one.

4. **Deprecate before removing** Mark fields or behaviors as deprecated, give
   consumers time to migrate, then remove them on a defined schedule.

## Decision Guide

Use this table when evolving an operation:

| Change                       | What to do                                     |
| ---------------------------- | ---------------------------------------------- |
| Add optional behavior        | Add a new field with a safe default            |
| Allow opt-out of behavior    | Add a field (e.g. `strict=False`)              |
| Remove optional behavior     | Deprecate the opt-out, then remove the field   |
| Change core semantics        | Introduce a new `op`                           |
| Rename or restructure fields | Add new field -> deprecate old -> remove later |

## Example: Operation Lifecycle

### 1. Initial version

```python
class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            raise PatchConflictError(f"{self.old!r} is not in {current!r}")
        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
```

### 2. Additive evolution (non-breaking)

Introduce optional behavior via a new field:

```python
class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = True

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.strict and self.old not in current:
            raise PatchConflictError(
                f"strict mode is enabled and {self.old!r} is not in {current!r}"
            )
        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
```

- Existing clients are unaffected (`strict=True`)
- New clients can opt into relaxed behavior (`strict=False`)

### 3. Deprecation (behavior consolidation)

If non-strict behavior is no longer desired, deprecate it:

```python
class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = Field(
        default=True,
        deprecated=True,
        description=(
            "Deprecated. Non-strict mode (strict=False) will be removed. "
            "This operation will always behave as strict=True."
        ),
    )

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.strict and self.old not in current:
            raise PatchConflictError(
                f"strict mode is enabled and {self.old!r} is not in {current!r}"
            )
        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
```

At this stage:

- `strict=False` is discouraged
- Documentation and schema signal upcoming removal
- Runtime warnings may be added if needed

### 4. Removal (future state)

Once clients have migrated, remove the field entirely and make strict behavior
unconditional.

## Rollout Strategy

Schema evolution should be coordinated with runtime controls:

- Use **operation registries** to control which operations are accepted per
  endpoint
- Gate new fields or operations behind **feature flags**
- Roll out changes gradually across environments (dev -> staging -> production)

## Key Takeaways

- Prefer **extending** operations over replacing them
- Use **fields for optional behavior**, `op` for **semantic shifts**
- Treat deprecation as a **phase**, not a single step
- Roll out contract changes with explicit **registry and flag policy**
