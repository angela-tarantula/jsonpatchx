# Agent Guide Tests

These fixtures are manual regression checks for
[`examples/AGENTS.md`](../../examples/AGENTS.md).

They are meant to answer a narrow question: if a child agent is given only the
inline text of [`examples/AGENTS.md`](../../examples/AGENTS.md) plus one prompt
fixture, does it generate a good custom operation?

They are not a CI harness and they are not proof of workspace isolation.

## Run a Prompt-Only Check

Use this procedure in Codex when you want a reproducible evaluation:

1. Pick one fixture from [`tests/agents/`](./).
2. Read [`examples/AGENTS.md`](../../examples/AGENTS.md).
3. Spawn a child agent with `fork_context:false`.
4. Paste the full contents of [`examples/AGENTS.md`](../../examples/AGENTS.md)
   into the child prompt.
5. Paste exactly one fixture into the same child prompt.
6. Add this instruction:

   ```text
   Treat the AGENTS text below as the repository instruction source for this
   task. Do not inspect workspace files. Use only the AGENTS text and the
   prompt. Return only Python code.
   ```

7. Save or paste the returned Python with the fixture name.
8. Review the returned code against the rubric below.

Use one fixture per child agent. Do not bundle multiple fixtures into one run.

## Use the Standard Prompt Shape

Keep the harness wording stable so changes in output are more likely to reflect
changes in [`examples/AGENTS.md`](../../examples/AGENTS.md) rather than
evaluator drift.

```text
Treat the AGENTS text below as the repository instruction source for this task.
Do not inspect workspace files. Use only the AGENTS text and the prompt.
Return only Python code.

=== AGENTS TEXT BEGIN ===
<paste examples/AGENTS.md here>
=== AGENTS TEXT END ===

=== PROMPT BEGIN ===
<paste one tests/agents/*.md fixture here>
=== PROMPT END ===
```

## Judge the Result

Check the output against the prompt and against the local authoring patterns in
[`examples/AGENTS.md`](../../examples/AGENTS.md).

- The code should be complete Python, not pseudocode.
- It should subclass `OperationSchema` and implement `apply()`.
- It should import from public JsonPatchX modules rather than internal ones.
- It should not invent unsupported hooks such as `patch()`, `expand()`, or
  `to_builtin_ops()`.
- It should choose error types and schema techniques that fit the operation,
  rather than blindly using one pattern everywhere.

When reporting the run, include the full generated Python for each fixture. Do
not ask the human reviewer to rely only on a summary.

For specific fixture families, also check:

- State-aware object-key prompts: use `classify_state()` and the real
  `TargetState` members when the behavior depends on why the path is invalid.
- Schema-rich prompts: make the richness visible in generated schema, not only
  in runtime validation. Titles, descriptions, `Field(...)` metadata, aliases,
  and `json_schema_extra` are all fair game when they honestly express the
  contract.
- Deliberate-error prompts: infer repo-appropriate errors such as
  `PatchConflictError` or `PydanticCustomError` from the guide rather than from
  the fixture wording.

## Know the Limits

This harness is intentionally modest.

- It does show whether the child agent can work from the pasted instruction text
  plus the fixture.
- It does not prove that the child agent never inspected the workspace.
- `fork_context:false` prevents thread-history leakage, but it does not itself
  remove file access.

If you need the stronger claim that the child agent only used the pasted text,
you need more than this harness:

- inspect the child tool logs, or
- run the evaluation in a more isolated environment

## Current Fixtures

- [`lowercase-op.md`](lowercase-op.md): minimal happy-path operation
- [`replace-array-value-op.md`](replace-array-value-op.md): runtime conflict
  inference
- [`swap-op-structured-validation.md`](swap-op-structured-validation.md):
  deliberate validation-style choice
- [`bound-number-op.md`](bound-number-op.md): schema-rich contract design
- [`add-missing-key-op.md`](add-missing-key-op.md): state-aware object-key
  behavior
