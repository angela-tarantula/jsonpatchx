# Holdout: `LowercaseOp` (from contract)

You are extending JsonPatchX's custom operation catalog. You have been given:

- `AGENT_GUIDE.md`: the custom-operation agent guide.
- `recipes.py`: the operation catalog, with one operation removed.
- `contract.json`: the exact JSON Schema the missing operation's request body
  must produce.

One operation is missing: `LowercaseOp`. It lowercases a string value at `path`.

Implement `LowercaseOp` so its generated schema matches `contract.json` exactly:
same field names, types, and requiredness. Use `contract.json` as the source of
truth for the wire shape, and the description above as the source of truth for
behavior.

Return only the Python definition of `LowercaseOp`, ready to add back into
`recipes.py`. Do not inspect any other files.
