# Agent Guide Tests

These fixtures are manual regression checks for
[`docs/custom-operation-agent-guide.md`](../../docs/custom-operation-agent-guide.md).
They are manual fixtures, not automated tests, and are not part of the pytest
suite.

They are a leave-one-out reconstruction test:
[`official_recipes.py`](official_recipes.py) is a pool of real JsonPatchX custom
operations. For each holdout, one operation is removed and a child agent is
asked to write it back, given only the guide, the reduced pool, and one task
prompt.

- **`from-examples/<slug>/`**: the agent gets a natural-language task plus the
  JSON Schema of the remaining operations, and must infer the missing
  operation's wire contract and behavior together. This is the stronger test of
  the guide plus surrounding examples.
- **`from-contract/<slug>/`**: the agent gets the same task plus the exact JSON
  Schema the missing operation's request body must produce, and must implement
  code matching a known contract. This is the more realistic "extend an existing
  API to match a given schema" test.

Current holdouts: `lowercase`, `swap`, `replace-array-value`, `bound-number`,
`add-missing-key`. Each has a `task.md` under both `from-examples/` and
`from-contract/`.

There is also one non-holdout category:

- **`evolve-contract/<slug>/`**: only the _later_ evolution stages of one
  operation are removed; the current (v1) shape stays in the pool as the agent's
  starting point. `official_recipes.py`'s `EVOLUTION_STAGES` maps each slug to
  its v1/v2/v3 class names; v2+ are wrapped in
  `# agent-example: <slug>:vN:start` / `:end` markers, are real, tested code
  (not prose), and are excluded from `schema.json` so they never leak into the
  bundle. The agent is asked to produce the missing stages using the "Evolving
  an Operation's Contract" section of `AGENT_GUIDE.md`.

  Note that `ReplaceSubstringOp`'s full evolution is already public in
  [`evolving-patch-contracts.md`](../../docs/user-guide/evolving-patch-contracts.md).
  Testing on it also measures training-data recall, not just generalization from
  the guide; weigh that when interpreting its result.

  Current targets, each an additive change followed by a field deprecation:

  - `replace-substring`: adds `strict` (non-strict mode), then deprecates it.
  - `add-to-set`: adds `ignore_case`, then deprecates it in favor of a mutually
    exclusive `comparison` enum.
  - `set-rollout-percentage`: adds `relative`, then deprecates it in favor of a
    mutually exclusive `mode` enum (needed because `relative` alone cannot
    express "decrease" without giving `percentage` a sign).
  - `test-missing`: adds `require_parent` defaulting to `False` (backward
    compatible; a negative array index is also rejected when set, and the
    document root is exempt since it always exists), then deprecates it while
    flipping its default to `True` — a deliberate breaking change bundled with
    the deprecation, not a routine one.

## Render a Fixture Bundle

[`scripts/render_agent_fixture.py`](../../scripts/render_agent_fixture.py)
generates the disposable bundle you paste into a child agent. Nothing it writes
is checked in; only `official_recipes.py` and the `task.md` files are.

```sh
uv run python scripts/render_agent_fixture.py --target lowercase --mode from-examples
uv run python scripts/render_agent_fixture.py --target add-to-set --mode evolve-contract
```

For `from-examples`/`from-contract`, this writes `AGENT_GUIDE.md`, `recipes.py`
(with the holdout removed), `schema.json` (or `contract.json` for
`--mode from-contract`), and `task.md`. For `evolve-contract`, it writes
`AGENT_GUIDE.md`, `recipes.py` (with the target's v2+ stages removed, v1 kept),
`schema.json` (built from what remains, so no evolved field or class name
appears in it), and `task.md`. Bundles are written under your system temp
directory by default (or `--out DIR`).

## Run a Prompt-Only Check

Use this procedure when you want a reproducible evaluation:

1. Pick a target and a mode, then render its bundle as shown above.
2. Spawn a child agent that does not inherit this conversation.
3. Paste every file the bundle contains into the child prompt, each clearly
   labeled.
4. Add this instruction:

   ```text
   Treat the guide text as the repository instruction source for this task.
   Do not inspect workspace files. Use only the pasted text. Return only
   Python code.
   ```

5. Save or paste the returned Python with the target and mode in the name.
6. Review the returned code against the rubric below.

Use one target per child agent. Do not bundle multiple targets into one run.

## Judge the Result

Check the output against the task and against the local authoring patterns in
the guide and in `official_recipes.py`.

- The code should be complete Python, not pseudocode.
- It should subclass `OperationSchema` and implement `apply()`.
- It should import from public JsonPatchX modules rather than internal ones.
- It should not invent unsupported hooks such as `patch()`, `expand()`, or
  `to_builtin_ops()`.
- For `from-contract`, the generated schema (`ClassName.model_json_schema()`)
  should match `contract.json`: same field names, types, and requiredness.
- It should choose error types and schema techniques that fit the operation,
  rather than blindly using one pattern everywhere.

When reporting the run, include the full generated Python for each holdout. Do
not ask the human reviewer to rely only on a summary.

For specific holdouts, also check:

- `add-missing-key`: uses `classify_state()` and the real `TargetState` members
  to distinguish why a path is invalid, not one generic error.
- `bound-number`: makes the schema-richness visible in the generated schema (the
  `anyOf` requiring `min` or `max`), not only in runtime validation.
- `swap`: infers a repo-appropriate structured validation error
  (`PydanticCustomError`) rather than a generic `ValueError`.

For `evolve-contract`, also check:

- The `op` literal is unchanged at both stages.
- The additive stage's new field defaults to the current behavior, so a caller
  that never sends it sees no change, and `percentage`'s sign is never
  reinterpreted in `set-rollout-percentage`. `test-missing`'s additive stage
  (`require_parent`, default `False`) must also be fully backward compatible; it
  is the deprecation stage that is the deliberate exception here (see below),
  not the additive one.
- `replace-substring`, `add-to-set`, `set-rollout-percentage`: the deprecation
  stage's fields are mutually exclusive, and neither has a concrete default:
  check that omission is detected via `model_fields_set`
  (`"field" not in self.model_fields_set`), not a truthiness check on a
  `Field(default=...)` value.
- `test-missing`: the additive stage must also reject a negative array index as
  a conflict when `require_parent` is set, and must exempt the document root
  from the new field's conflict entirely (root is its own parent and always
  exists). The deprecation stage must deprecate the field and flip its default
  to `True`, but both `True` and `False` must still fully work when sent
  explicitly — the deprecation only signals a future removal, it does not itself
  narrow what the field accepts. Say plainly that the default flip is a
  deliberate breaking change bundled with the deprecation, not a routine one.

Compare each stage against the real answer in `official_recipes.py`
(`ReplaceSubstringOpAdditive`/`Deprecated`, `AddToSetOpIgnoreCase`/`Comparison`,
`SetRolloutPercentageOpRelative`/`Mode`,
`TestMissingOpRequireParent`/`ParentRequired`) — those are excluded from the
bundle, not secret from you as the reviewer.

## Know the Limits

This harness is intentionally modest.

- It does show whether the child agent can work from the pasted instruction text
  plus the fixture.
- It does not prove that the child agent never inspected the workspace.
- A non-inheriting child agent (`fork_context:false` in Codex) prevents
  thread-history leakage, but it does not itself remove file access.

If you need the stronger claim that the child agent only used the pasted text,
you need more than this harness:

- inspect the child tool logs, or
- run the evaluation in a more isolated environment
