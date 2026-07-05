# Evolve: `AddToSetOp` (additive change, then field deprecation)

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide, including its "Evolving an
  Operation's Contract" section.
- `recipes.py`: the operation catalog, including the current `AddToSetOp`.
- `schema.json`: the JSON Schema for every operation in `recipes.py`.

`AddToSetOp` currently adds a value to an array only if it is not already
present, using whole-JSON-value equality.

Evolve its contract through its next two stages, in order, following
`AGENT_GUIDE.md`'s "Evolving an Operation's Contract" section:

1. **Additive change**: string values in the array should optionally be compared
   case-insensitively. Add this without breaking any caller that has never heard
   of the new field.
2. **Field deprecation**: some time later, that field needs to become one of
   several comparison modes instead of a single on/off switch (for example,
   exact vs. case-insensitive). Deprecate the original field in favor of a new
   one, and treat the two as mutually exclusive. Decide deliberately whether
   either field should have a concrete default at this stage.

Return two Python definitions of `AddToSetOp` in order, one per stage, each a
complete class ready to replace the previous one in `recipes.py`. Before each
definition, state in one sentence why that stage is a compatible change under
`AGENT_GUIDE.md`'s rules. Do not change the `op` literal at either stage, and do
not inspect any other files.
