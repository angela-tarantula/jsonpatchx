# Holdout: `SwapOp`

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide.
- `recipes.py`: the operation catalog, with one operation removed.
- `schema.json`: the JSON Schema for the remaining operations, for style
  reference.

One operation is missing: `SwapOp`. It swaps the values at pointers `a` and `b`.
Reject cases where one pointer is an ancestor of the other, and make that
validation choice deliberately rather than mechanically.

Implement `SwapOp` in the same style as the operations already in `recipes.py`.

Return only the Python definition of `SwapOp`, ready to add back into
`recipes.py`. Do not inspect any other files.
