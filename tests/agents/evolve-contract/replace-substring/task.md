# Evolve: `ReplaceSubstringOp` (additive change, then field deprecation)

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide, including its "Evolving an
  Operation's Contract" section.
- `recipes.py`: the operation catalog, including the current
  `ReplaceSubstringOp`.
- `schema.json`: the JSON Schema for every operation in `recipes.py`.

`ReplaceSubstringOp` currently replaces a substring within a string field, and
always raises a conflict error when the target substring is missing.

Evolve its contract through its next two stages, in order, following
`AGENT_GUIDE.md`'s "Evolving an Operation's Contract" section:

1. **Additive change**: clients now need a non-strict mode, where replacing a
   substring that is not present is a no-op instead of an error. Add this
   without breaking any existing caller that has never heard of the new field.
2. **Field deprecation**: some time later, that same field needs to go away.
   Deprecate it before removal, in a way that still tells you whether a caller
   is relying on the old default.

Return two Python definitions of `ReplaceSubstringOp` in order, one per stage,
each a complete class ready to replace the previous one in `recipes.py`. Before
each definition, state in one sentence why that stage is a compatible change
under `AGENT_GUIDE.md`'s rules. Do not change the `op` literal at either stage,
and do not inspect any other files.
