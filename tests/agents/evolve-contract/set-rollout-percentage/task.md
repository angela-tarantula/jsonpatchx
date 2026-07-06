# Evolve: `SetRolloutPercentageOp` (additive change, then field deprecation)

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide, including its "Evolving an
  Operation's Contract" section.
- `recipes.py`: the operation catalog, including the current
  `SetRolloutPercentageOp`.
- `schema.json`: the JSON Schema for every operation in `recipes.py`.

`SetRolloutPercentageOp` currently sets a named rollout variation to an absolute
percentage, adjusting the complementary variation so the two sum to 100.

Evolve its contract through its next two stages, in order, following
`AGENT_GUIDE.md`'s "Evolving an Operation's Contract" section:

1. **Additive change**: a caller now wants to increase a variation's percentage
   by a relative amount instead of setting it outright. Add this without
   reinterpreting what `percentage` itself means (its sign should never have to
   carry meaning), and without breaking any caller that has never heard of the
   new field.
2. **Field deprecation**: the field you just added can only increase a
   variation; it cannot express "decrease" without giving `percentage` a sign,
   which would reopen the exact problem you just avoided. Deprecate it in favor
   of a field that can express set, increase, and decrease explicitly, and treat
   the two as mutually exclusive. Decide deliberately whether either field
   should have a concrete default at this stage.

Return two Python definitions of `SetRolloutPercentageOp` in order, one per
stage, each a complete class ready to replace the previous one in `recipes.py`.
Before each definition, state in one sentence why that stage is a compatible
change under `AGENT_GUIDE.md`'s rules. Do not change the `op` literal at either
stage, and do not inspect any other files.
