# Holdout: `ReplaceArrayValueOp`

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide.
- `recipes.py`: the operation catalog, with one operation removed.
- `schema.json`: the JSON Schema for the remaining operations, for style
  reference.

One operation is missing: `ReplaceArrayValueOp`. It replaces matching array
members by value, first occurrence or all occurrences, and raises an error if
the value to replace is not present.

Implement `ReplaceArrayValueOp` in the same style as the operations already in
`recipes.py`.

Return only the Python definition of `ReplaceArrayValueOp`, ready to add back
into `recipes.py`. Do not inspect any other files.
