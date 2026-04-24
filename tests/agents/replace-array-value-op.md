# Replace Array Value Operation Prompt

Write a JsonPatchX custom operation named `ReplaceArrayValueOp`.

It should replace the first exact occurrence of `old_value` in an array with
`new_value`.

Raise an error if `old_value` is not present.

Return only Python code.
