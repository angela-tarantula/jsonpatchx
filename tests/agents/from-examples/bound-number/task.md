# Holdout: `ClampOp`

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide.
- `recipes.py`: the operation catalog, with one operation removed.
- `schema.json`: the JSON Schema for the remaining operations, for style
  reference.

One operation is missing: `ClampOp`. It clamps a numeric value at `path` into an
inclusive range. Make it schema-rich: the wire contract must clearly require at
least one of `min` or `max`.

Implement `ClampOp` in the same style as the operations already in `recipes.py`.

Return only the Python definition of `ClampOp`, ready to add back into
`recipes.py`. Do not inspect any other files.
