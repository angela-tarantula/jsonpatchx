# Holdout: `AddMissingKeyOp`

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide.
- `recipes.py`: the operation catalog, with one operation removed.
- `schema.json`: the JSON Schema for the remaining operations, for style
  reference.

One operation is missing: `AddMissingKeyOp`. It behaves like `add`, but only
when `path` names a missing object key. If the key already exists, or the path
is otherwise invalid, distinguish why instead of collapsing every case into one
generic error.

Implement `AddMissingKeyOp` in the same style as the operations already in
`recipes.py`.

Return only the Python definition of `AddMissingKeyOp`, ready to add back into
`recipes.py`. Do not inspect any other files.
