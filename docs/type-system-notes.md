# Type System Notes

JsonPatchX focuses on typing patch operations, not only patched data. That lets
you enforce operational constraints that your data model alone cannot express.

This page covers:

- JSON helper types and strict JSON semantics (`JSONNumber`, `JSONValue`, etc.)
- why `bool` is excluded from `JSONNumber`
- finite-number enforcement (`NaN` and `Infinity` rejected)
- typing limitations in Python and practical workarounds (for example runtime
  unions and bounded recursive JSON type approximations)
