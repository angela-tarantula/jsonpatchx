Baseline disclaimer (intentional): These demos are not fully correct JSON Patch implementations.
They are representative of what teams commonly build (or a best-effort manual approach). We list
known correctness gaps so comparisons stay honest.

Known gaps

- incorrect swap constraints
- incomplete pointer semantics (missing escapes, edge cases, and full RFC behavior)
- weaker typing and weaker OpenAPI
- no registry-scoped pointer backend context injection
- error reporting lacks structured op index / payload
