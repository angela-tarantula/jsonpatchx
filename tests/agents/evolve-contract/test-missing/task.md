# Evolve: `TestMissingOp` (additive change, then field deprecation)

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide, including its "Evolving an
  Operation's Contract" section.
- `recipes.py`: the operation catalog, including the current `TestMissingOp`.
- `schema.json`: the JSON Schema for every operation in `recipes.py`.

`TestMissingOp` currently succeeds whenever `path` does not resolve to an
existing value. That includes the case where `path`'s parent does not exist
either: for example, `/a/b` reads as "missing" (success) whenever `/a` itself is
missing, which hides a structural problem behind the same result as an ordinary
missing value.

Evolve its contract through its next two stages, in order, following
`AGENT_GUIDE.md`'s "Evolving an Operation's Contract" section:

1. **Additive change**: add a way to require that `path`'s parent actually
   exists, and to reject a negative array index outright, since its target
   position is not stable enough to test against. Default the new field so a
   caller who never sends it keeps the exact old behavior. When a caller opts
   in: a missing parent, or a negative array index, is a state conflict
   (`PatchConflictError`), not a passed test. The document root is a special
   case: it is its own parent and always exists once there is a document to
   patch, so targeting the root should never trigger the new field's conflict,
   regardless of whether the field is set.
2. **Field deprecation**: the team has judged the old vacuous-success default to
   be a latent correctness gap, not a feature worth preserving, and wants every
   caller on the stricter behavior by default going forward. Deprecate the field
   and flip its default at the same time. The field itself keeps working exactly
   as before for both values; the deprecation is only a signal that it will be
   removed entirely in a future version once callers have migrated off the old
   default. State plainly that this default flip is a deliberate, called-out
   breaking change bundled with the deprecation, not a routine one.

Return two Python definitions of `TestMissingOp` in order, one per stage, each a
complete class ready to replace the previous one in `recipes.py`. Before each
definition, state in one sentence why that stage is a compatible change under
`AGENT_GUIDE.md`'s rules (or, for stage 2, why its default flip is a deliberate,
called-out exception). Do not change the `op` literal at either stage, and do
not inspect any other files.
