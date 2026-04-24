# Bound Number Operation Prompt

Write a JsonPatchX custom operation named `BoundNumberOp`.

It should clamp a numeric value into an inclusive range.

Make it schema-rich. Make that richness visible in the generated schema, not
only in runtime validation.

The wire contract must clearly require at least one of `floor` or `ceiling`.

Return only Python code.
