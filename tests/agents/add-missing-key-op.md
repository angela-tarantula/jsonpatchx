# Create Object Member Operation Prompt

Write a JsonPatchX custom operation named `CreateObjectMemberOp`.

It should add an object member only when `path` names a missing object key.

If the key already exists, raise an error.

If behavior depends on why the path is invalid, distinguish those cases instead
of collapsing them into one generic error.

Return only Python code.
