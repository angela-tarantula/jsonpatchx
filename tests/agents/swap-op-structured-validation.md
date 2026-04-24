# Swap Operation Structured Validation Prompt

Write a JsonPatchX custom operation named `SwapOp`.

It should swap the values at pointers `a` and `b`.

Reject cases where one pointer is an ancestor of the other.

Make the validation choice deliberately rather than mechanically.

Return only Python code.
