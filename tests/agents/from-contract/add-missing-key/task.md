# Holdout: `AddMissingKeyOp` (from contract)

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide.
- `recipes.py`: the operation catalog, with one operation removed.
- `contract.json`: the exact JSON Schema the missing operation's request body
  must produce.

One operation is missing: `AddMissingKeyOp`. It behaves like `add`, but only
when `path` names a missing object key. If the key already exists, or the path
is otherwise invalid, distinguish why instead of collapsing every case into one
generic error.

Implement `AddMissingKeyOp` so its generated schema matches `contract.json`
exactly: same field names, types, and requiredness. Use `contract.json` as the
source of truth for the wire shape, and the description above as the source of
truth for behavior.

Return only the Python definition of `AddMissingKeyOp`, ready to add back into
`recipes.py`. Do not inspect any other files.
