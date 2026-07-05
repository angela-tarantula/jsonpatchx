"""Render a disposable agent fixture bundle for the custom-operation agent guide.

This script backs the manual harness described in ``tests/agents/README.md``.
It is not part of the pytest suite. For the holdout modes (``from-examples``,
``from-contract``), it takes ``tests/agents/official_recipes.py``, removes
exactly one marked operation, and writes a bundle you paste into a child
agent: the guide, the reduced recipe source, a schema artifact, and the task
prompt. For ``evolve-contract``, it removes only the later evolution stages
of one operation (see ``EVOLUTION_STAGES`` in ``official_recipes.py``),
keeping the current (v1) shape in place, and asks the agent to produce the
next stages, using the "Evolving an Operation's Contract" section already in
the guide. Nothing this script writes is meant to be checked in.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Union

from pydantic import Field, TypeAdapter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # predictable absolute imports

# pylint: disable=wrong-import-position
from jsonpatchx import OperationSchema  # noqa: E402
from tests.agents import official_recipes as recipes  # noqa: E402

MODULE_PATH = ROOT / "tests" / "agents" / "official_recipes.py"
GUIDE_PATH = ROOT / "docs" / "custom-operation-agent-guide.md"
TASK_ROOT = ROOT / "tests" / "agents"
HOLDOUT_MODES = ("from-examples", "from-contract")
MODES = (*HOLDOUT_MODES, "evolve-contract")


def _evolved_class_names() -> set[str]:
    """Names of every operation class that represents a post-v1 stage.

    Returns:
        Every class name from `EVOLUTION_STAGES` values except each list's
        first (v1) entry, since v1 is already a normal pool member.
    """
    return {name for stages in recipes.EVOLUTION_STAGES.values() for name in stages[1:]}


def _all_classes() -> list[type[OperationSchema]]:
    """List every live operation class defined directly in ``official_recipes``.

    Returns:
        Every `OperationSchema` subclass defined in the module, in
        definition order, excluding re-exported built-in operations such as
        `AddOp` that the module only imports, and excluding post-v1
        evolution-stage classes (see `_evolved_class_names`), which would
        otherwise collide with v1's `op` literal in the discriminated union.
    """
    evolved = _evolved_class_names()
    return [
        value
        for value in vars(recipes).values()
        if (
            inspect.isclass(value)
            and issubclass(value, OperationSchema)
            and value is not OperationSchema
            and value.__module__ == recipes.__name__
            and value.__name__ not in evolved
        )
    ]


def _strip_holdout(source: str, slug: str) -> str:
    """Remove one marked operation block from the recipe source.

    Arguments:
        source: The full text of `official_recipes.py`.
        slug: A key from `HOLDOUT_OPERATIONS`.

    Returns:
        The source with the matching `# agent-example: <slug>:start` /
        `:end` block removed.

    Raises:
        SystemExit: If the markers for `slug` are not found exactly once.
    """
    start = f"# agent-example: {slug}:start"
    end = f"# agent-example: {slug}:end"
    pattern = re.compile(rf"\n?{re.escape(start)}\n.*?\n{re.escape(end)}\n", re.DOTALL)
    reduced, count = pattern.subn("\n", source)
    if count != 1:
        raise SystemExit(
            f"expected exactly one marker block for {slug!r} in {MODULE_PATH}, found {count}"
        )
    return re.sub(r"\n{3,}", "\n\n\n", reduced)


def _strip_evolution_stages(source: str, slug: str) -> str:
    """Remove every post-v1 evolution-stage block for `slug`, keeping v1.

    Arguments:
        source: The full text of `official_recipes.py`.
        slug: A key from `EVOLUTION_STAGES`.

    Returns:
        The source with every `# agent-example: <slug>:vN:start` / `:end`
        block removed, for N >= 2.

    Raises:
        SystemExit: If no stage marker blocks for `slug` are found.
    """
    pattern = re.compile(
        rf"\n?# agent-example: {re.escape(slug)}:v\d+:start\n.*?\n"
        rf"# agent-example: {re.escape(slug)}:v\d+:end\n",
        re.DOTALL,
    )
    reduced, count = pattern.subn("\n", source)
    if count < 1:
        raise SystemExit(
            f"expected at least one evolution-stage marker block for {slug!r} "
            f"in {MODULE_PATH}, found {count}"
        )
    return re.sub(r"\n{3,}", "\n\n\n", reduced)


def _registry_schema(classes: list[type[OperationSchema]]) -> dict[str, object]:
    """Build the discriminated-union JSON Schema for a set of operations.

    Arguments:
        classes: Operation classes to include.

    Returns:
        The JSON Schema for a patch document restricted to `classes`.
    """
    # Runtime-generated type; type checkers can't reason about it. See
    # "Environment-Specific Registries" in docs/user-guide/registries-and-routes.md.
    registry = Annotated[Union[tuple(classes)], Field(discriminator="op")]  # type: ignore[valid-type]
    return TypeAdapter(registry).json_schema()


def _render_holdout(slug: str, mode: str, out_dir: Path) -> None:
    """Write a from-examples or from-contract bundle to `out_dir`.

    Arguments:
        slug: A key from `HOLDOUT_OPERATIONS`, such as `"lowercase"`.
        mode: Either `"from-examples"` or `"from-contract"`.
        out_dir: Directory to write the bundle into; created if missing.

    Raises:
        SystemExit: If `slug` is unknown or the matching task file is missing.
    """
    if slug not in recipes.HOLDOUT_OPERATIONS:
        choices = ", ".join(sorted(recipes.HOLDOUT_OPERATIONS))
        raise SystemExit(f"unknown holdout {slug!r}; choices: {choices}")

    classes = _all_classes()
    by_name = {cls.__name__: cls for cls in classes}
    holdout_cls = by_name[recipes.HOLDOUT_OPERATIONS[slug]]
    remaining = [cls for cls in classes if cls is not holdout_cls]

    task_path = TASK_ROOT / mode / slug / "task.md"
    if not task_path.exists():
        raise SystemExit(f"missing task file: {task_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "AGENT_GUIDE.md").write_text(GUIDE_PATH.read_text())
    (out_dir / "recipes.py").write_text(_strip_holdout(MODULE_PATH.read_text(), slug))
    (out_dir / "task.md").write_text(task_path.read_text())

    if mode == "from-examples":
        schema = _registry_schema(remaining)
        (out_dir / "schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n"
        )
    else:
        schema = holdout_cls.model_json_schema()
        (out_dir / "contract.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n"
        )


def _render_evolve_contract(slug: str, out_dir: Path) -> None:
    """Write an evolve-contract bundle to `out_dir`.

    Only the post-v1 evolution stages of `slug` are removed; v1 stays as the
    agent's starting point. The agent gets the full remaining recipe pool,
    the full schema, and is asked to produce the missing stages, using the
    guide's "Evolving an Operation's Contract" section.

    Arguments:
        slug: A key in `EVOLUTION_STAGES`, and a task directory name under
            `tests/agents/evolve-contract/`.
        out_dir: Directory to write the bundle into; created if missing.

    Raises:
        SystemExit: If `slug` is unknown or the matching task file is missing.
    """
    if slug not in recipes.EVOLUTION_STAGES:
        choices = ", ".join(sorted(recipes.EVOLUTION_STAGES))
        raise SystemExit(f"unknown evolve-contract target {slug!r}; choices: {choices}")

    task_path = TASK_ROOT / "evolve-contract" / slug / "task.md"
    if not task_path.exists():
        raise SystemExit(f"missing task file: {task_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "AGENT_GUIDE.md").write_text(GUIDE_PATH.read_text())
    (out_dir / "recipes.py").write_text(
        _strip_evolution_stages(MODULE_PATH.read_text(), slug)
    )
    (out_dir / "task.md").write_text(task_path.read_text())

    schema = _registry_schema(_all_classes())
    (out_dir / "schema.json").write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n"
    )


def render(slug: str, mode: str, out_dir: Path) -> None:
    """Write one fixture bundle to `out_dir`.

    Arguments:
        slug: A task directory name under `tests/agents/<mode>/`. For the
            holdout modes, must also be a key in `HOLDOUT_OPERATIONS`.
        mode: One of `MODES`.
        out_dir: Directory to write the bundle into; created if missing.
    """
    if mode in HOLDOUT_MODES:
        _render_holdout(slug, mode, out_dir)
    else:
        _render_evolve_contract(slug, out_dir)
    print(f"wrote fixture bundle to {out_dir}")


def main() -> int:
    """Parse arguments and render one fixture bundle.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="For from-examples/from-contract: a key in HOLDOUT_OPERATIONS, "
        "e.g. 'lowercase'. For evolve-contract: a task directory name under "
        "tests/agents/evolve-contract/, e.g. 'replace-substring'.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=MODES,
        help="from-examples: reconstruct a removed op from surrounding code. "
        "from-contract: implement a removed op to match a given schema. "
        "evolve-contract: evolve one op's contract through its next stages, "
        "nothing removed.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory. Defaults to a directory under the system temp dir.",
    )
    args = parser.parse_args()

    out_dir = args.out or (
        Path(tempfile.gettempdir())
        / "jsonpatchx-agent-fixture"
        / f"{args.mode}-{args.target}"
    )
    render(args.target, args.mode, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
