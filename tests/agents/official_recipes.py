"""Canonical pool of custom JsonPatchX operations used to generate agent
regression fixtures.

This module is not a demo file and is not imported by anything under
``examples/``. It merges the operations from ``examples/recipes.py``,
``examples/recipes2.py``, and the operations shown in
``docs/custom-operation-agent-guide.md`` and
``docs/user-guide/custom-operations.md`` into one pool, so
``scripts/render_agent_fixture.py`` can hold out one operation at a time and
give a child agent the rest as surrounding examples.

``HOLDOUT_OPERATIONS`` maps each holdout slug used under
``tests/agents/from-examples/`` and ``tests/agents/from-contract/`` to the
class name the render script should remove. Every holdout class is wrapped in
matching ``# agent-example: <slug>:start`` / ``:end`` markers so removal is a
plain text operation instead of an AST rewrite.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Literal, Self, assert_never, cast, override

from pydantic import AliasChoices, ConfigDict, Field, model_validator
from pydantic_core import MISSING, PydanticCustomError

from jsonpatchx import (
    AddOp,
    JSONPointer,
    JSONValue,
    OperationSchema,
    PatchConflictError,
    RemoveOp,
    ReplaceOp,
    TestOp,
    TestOpFailed,
)
from jsonpatchx.backend import TargetState, classify_state
from jsonpatchx.types import JSONArray, JSONBoolean, JSONNumber, JSONObject, JSONString

HOLDOUT_OPERATIONS: dict[str, str] = {
    "lowercase": "LowercaseOp",
    "swap": "SwapOp",
    "replace-array-value": "ReplaceArrayValueOp",
    "bound-number": "ClampOp",
    "add-missing-key": "AddMissingKeyOp",
}

# Each list's first entry (v1) is already a normal pool member above; the
# rest (v2, v3, ...) are answer-key classes wrapped in
# `# agent-example: <slug>:vN:start` / `:end` markers, and are excluded from
# the live discriminated-union pool by scripts/render_agent_fixture.py so
# they never collide with v1's `op` literal or leak into schema.json.
# evolve-contract mode strips everything after v1; v1 stays as the starting
# point the agent evolves from. Note that "replace-substring"'s full
# evolution is already public in docs/user-guide/evolving-patch-contracts.md,
# so a blind test against it also measures training-data recall, not just
# generalization from the guide.
EVOLUTION_STAGES: dict[str, list[str]] = {
    "replace-substring": [
        "ReplaceSubstringOp",
        "ReplaceSubstringOpAdditive",
        "ReplaceSubstringOpDeprecated",
    ],
    "add-to-set": [
        "AddToSetOp",
        "AddToSetOpIgnoreCase",
        "AddToSetOpComparison",
    ],
    "set-rollout-percentage": [
        "SetRolloutPercentageOp",
        "SetRolloutPercentageOpRelative",
        "SetRolloutPercentageOpMode",
    ],
    "test-missing": [
        "TestMissingOp",
        "TestMissingOpRequireParent",
        "TestMissingOpParentRequired",
    ],
}


class ToggleOp(OperationSchema):
    """Invert a boolean value at the target path."""

    model_config = ConfigDict(title="Toggle operation")
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)


class EnableOp(OperationSchema):
    """Set a boolean value to true."""

    model_config = ConfigDict(title="Enable operation")
    op: Literal["enable"] = "enable"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=True).apply(doc)


class DisableOp(OperationSchema):
    """Set a boolean value to false."""

    model_config = ConfigDict(title="Disable operation")
    op: Literal["disable"] = "disable"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=False).apply(doc)


class IncrementOp(OperationSchema):
    """Increase a numeric value by an amount."""

    model_config = ConfigDict(title="Increment operation")
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(default=1, gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)


class DecrementOp(OperationSchema):
    """Decrease a numeric value by an amount."""

    model_config = ConfigDict(title="Decrement operation")
    op: Literal["decrement"] = "decrement"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(default=1, gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current - self.amount).apply(doc)


# agent-example: bound-number:start
class ClampOp(OperationSchema):
    """Clamp a numeric value to an inclusive range."""

    model_config = ConfigDict(
        title="Clamp operation",
        validate_default=False,
        json_schema_extra={
            "description": (
                "Clamp a numeric value into an inclusive range. "
                "Useful for capping, limiting, bounding, flooring, "
                "or applying a ceiling."
            ),
            "x-discovery-terms": [
                "cap",
                "limit",
                "bound",
                "ceiling",
                "floor",
                "maximum",
                "minimum",
            ],
            "examples": [{"op": "clamp", "path": "/score", "max": 100}],
            "anyOf": [{"required": ["min"]}, {"required": ["max"]}],
        },
    )
    op: Literal["clamp"] = "clamp"
    path: JSONPointer[JSONNumber] = Field(
        description="Pointer to the numeric value to clamp."
    )
    min: JSONNumber = Field(
        default=cast(JSONNumber, MISSING),
        description="Inclusive lower bound.",
    )
    max: JSONNumber = Field(
        default=cast(JSONNumber, MISSING),
        description="Inclusive upper bound.",
    )

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        has_min = "min" in self.model_fields_set
        has_max = "max" in self.model_fields_set

        if not has_min and not has_max:
            raise ValueError("clamp requires at least one of min or max")
        if has_min and has_max and self.min > self.max:
            raise ValueError("clamp requires min <= max")
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if "min" in self.model_fields_set:
            current = max(self.min, current)
        if "max" in self.model_fields_set:
            current = min(self.max, current)
        return ReplaceOp(path=self.path, value=current).apply(doc)


# agent-example: bound-number:end


class AppendOp(OperationSchema):
    """Append a value to an array."""

    model_config = ConfigDict(title="Append operation")
    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        current.append(self.value)
        return doc


class PrependOp(OperationSchema):
    """Prepend a value to an array."""

    model_config = ConfigDict(title="Prepend operation")
    op: Literal["prepend"] = "prepend"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        current.insert(0, self.value)
        return doc


class InsertAtOp(OperationSchema):
    """Insert a value into an array at a specific index."""

    model_config = ConfigDict(title="Insert-at operation")
    op: Literal["insert_at"] = "insert_at"
    path: JSONPointer[JSONArray[JSONValue]]
    index: int = Field(ge=0)
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.index > len(current):
            raise PatchConflictError("index out of range")
        current.insert(self.index, self.value)
        return doc


class RemoveWhereOp(OperationSchema):
    """Remove objects from an array where a field matches a value."""

    model_config = ConfigDict(title="Remove-where operation")
    op: Literal["remove_where"] = "remove_where"
    path: JSONPointer[JSONArray[JSONObject[JSONValue]]]
    field: str
    equals: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        original_len = len(current)
        current[:] = [item for item in current if item.get(self.field) != self.equals]
        if len(current) == original_len:
            raise PatchConflictError("no matching item found")
        return doc


class DeduplicateOp(OperationSchema):
    """Remove duplicate values from an array, preserving order."""

    model_config = ConfigDict(title="Deduplicate operation")
    op: Literal["deduplicate"] = "deduplicate"
    path: JSONPointer[JSONArray[JSONValue]]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        encoded = dict.fromkeys(
            # treat dict as ordered set
            json.dumps(item, sort_keys=True)
            for item in current
        )
        current[:] = [json.loads(item) for item in encoded]
        return doc


class ReplaceSubstringOp(OperationSchema):
    """Replace a substring within a string field."""

    model_config = ConfigDict(title="Replace-substring operation")
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(
            path=self.path, value=current.replace(self.old, self.new)
        ).apply(doc)


# agent-example: replace-substring:v2:start
class ReplaceSubstringOpAdditive(OperationSchema):
    """Replace a substring within a string field.

    Stage 2 of `ReplaceSubstringOp`'s evolution
    (see docs/user-guide/evolving-patch-contracts.md): adds `strict`,
    defaulting to the original always-raise behavior.
    """

    model_config = ConfigDict(title="Replace-substring operation")
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = Field(default=True)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.strict and self.old not in current:
            raise PatchConflictError(
                f"strict mode is enabled and {self.old!r} is not in {current!r}"
            )
        return ReplaceOp(
            path=self.path, value=current.replace(self.old, self.new)
        ).apply(doc)


# agent-example: replace-substring:v2:end


# agent-example: replace-substring:v3:start
class ReplaceSubstringOpDeprecated(OperationSchema):
    """Replace a substring within a string field.

    Stage 3 of `ReplaceSubstringOp`'s evolution: `strict` is now deprecated
    but still honored. `model_fields_set` distinguishes an explicit value
    from the default, so a future removal only affects callers who were
    actually relying on it.
    """

    model_config = ConfigDict(title="Replace-substring operation")
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = Field(default=True, deprecated=True)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            if "strict" not in self.model_fields_set or self.strict:
                raise PatchConflictError(
                    f"strict mode is enabled and {self.old!r} is not in {current!r}"
                )
        return ReplaceOp(
            path=self.path, value=current.replace(self.old, self.new)
        ).apply(doc)


# agent-example: replace-substring:v3:end


class MergeOp(OperationSchema):
    """Merge an object into a target object."""

    model_config = ConfigDict(title="Merge operation")
    op: Literal["merge"] = "merge"
    path: JSONPointer[JSONObject[JSONValue]]
    value: JSONObject[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        current.update(self.value)
        return doc


class RenameKeyOp(OperationSchema):
    """Rename a key inside an object."""

    model_config = ConfigDict(title="Rename-key operation")
    op: Literal["rename"] = "rename"
    path: JSONPointer[JSONObject[JSONValue]]
    from_: JSONString = Field(alias="from")
    to: JSONString

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.from_ not in current:
            raise PatchConflictError("source key does not exist")
        if self.to in current:
            raise PatchConflictError("destination key already exists")
        current[self.to] = current.pop(self.from_)
        return doc


class MoveOnlyIfExistsOp(OperationSchema):
    """Move a value if the source path exists."""

    model_config = ConfigDict(title="Move-if-exists operation")
    op: Literal["moveonlyifexists"] = "moveonlyifexists"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if not self.from_.is_gettable(doc):
            return doc
        value = self.from_.get(doc)
        doc = AddOp(path=self.path, value=value).apply(doc)
        return RemoveOp(path=self.from_).apply(doc)


class SortNumbersOp(OperationSchema):
    """Sort a numeric array ascending or descending."""

    model_config = ConfigDict(title="Sort numbers operation")
    op: Literal["sort_numbers"] = "sort_numbers"
    path: JSONPointer[JSONArray[JSONNumber]]
    order: Literal["asc", "desc"] = "asc"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        new = sorted(current, reverse=self.order == "desc")
        return ReplaceOp(path=self.path, value=new).apply(doc)  # type: ignore[arg-type]


class BitSetOp(OperationSchema):
    """Set or clear a bit in a numeric bitfield."""

    model_config = ConfigDict(
        title="Bit operation",
        json_schema_extra={
            "description": "Set or clear a specific bit in a numeric bitfield.",
        },
    )
    op: Literal["bit_set"] = "bit_set"
    path: JSONPointer[JSONNumber]
    index: int = Field(ge=0)
    value: JSONBoolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = int(self.path.get(doc))
        mask = 1 << self.index
        next_val = (current | mask) if self.value else (current & ~mask)
        return ReplaceOp(path=self.path, value=next_val).apply(doc)


class MapOp(OperationSchema):
    """Replace a value based on a mapping table."""

    model_config = ConfigDict(title="Map operation")
    op: Literal["map"] = "map"
    path: JSONPointer[JSONString]
    mapping: JSONObject[JSONValue]
    strict: JSONBoolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current not in self.mapping:
            if self.strict:
                raise PatchConflictError(f"missing map entry for {current!r}")
            return doc
        return ReplaceOp(path=self.path, value=self.mapping[current]).apply(doc)


class TestMissingOp(OperationSchema):
    """Supports explicit non-existence preconditions for optimistic workflows.

    Example:
        doc={"users": {"42": {"name": "Ada"}}}
        op={"op": "test_missing", "path": "/users/99"}
        Useful before create flows to assert the target slot is free.
    """

    model_config = ConfigDict(
        title="Test-missing operation",
        json_schema_extra={
            "description": "Assert that a path does not resolve to an existing value."
        },
    )
    op: Literal["test_missing"] = "test_missing"
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if self.path.is_gettable(doc):
            raise TestOpFailed(f"expected missing path at {self.path!r}")
        return doc


# agent-example: test-missing:v2:start
class TestMissingOpRequireParent(OperationSchema):
    """Supports explicit non-existence preconditions for optimistic workflows.

    Stage 2 of `TestMissingOp`'s evolution: adds `require_parent`, defaulting
    to `False` so a caller who never sends it keeps the exact old behavior:
    `/a/b` still reads as vacuously missing whenever `/a` itself is missing.
    A caller can opt in to the stricter check, where the parent must exist
    and be a container, and where a negative array index is never accepted
    as evidence of anything missing (its target position is not stable
    enough to test against). The document root is never subject to this
    check: root is its own parent and always exists once a document exists
    to run a patch against.
    """

    model_config = ConfigDict(
        title="Test-missing operation",
        json_schema_extra={
            "description": "Assert that a path does not resolve to an existing value."
        },
    )
    op: Literal["test_missing"] = "test_missing"
    path: JSONPointer[JSONValue]
    require_parent: JSONBoolean = Field(
        default=False,
        description="Require the parent to exist and forbid negative array "
        "indices; violations are a conflict, not a passed test.",
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if not self.require_parent:
            if self.path.is_gettable(doc):
                raise TestOpFailed(f"expected missing path at {self.path!r}")
            return doc
        state = classify_state(self.path.ptr, doc)
        if state in {
            TargetState.PARENT_NOT_FOUND,
            TargetState.PARENT_NOT_CONTAINER,
            TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX,
        }:
            raise PatchConflictError(
                f"require_parent rejects the state of {self.path!r}"
            )
        if state in {TargetState.ROOT, TargetState.VALUE_PRESENT}:
            raise TestOpFailed(f"expected missing path at {self.path!r}")
        return doc


# agent-example: test-missing:v2:end


# agent-example: test-missing:v3:start
class TestMissingOpParentRequired(OperationSchema):
    """Supports explicit non-existence preconditions for optimistic workflows.

    Stage 3 of `TestMissingOp`'s evolution: `require_parent` is deprecated
    and its default flips to `True`. This is a deliberate, called-out
    breaking change bundled with the deprecation, not a routine one: the
    team wants every caller on the stricter behavior by default going
    forward, and plans to remove the field entirely in a future version once
    callers have migrated. Both `True` and `False` are still fully
    supported for now; only the default has changed.
    """

    model_config = ConfigDict(
        title="Test-missing operation",
        json_schema_extra={
            "description": "Assert that a path does not resolve to an existing value."
        },
    )
    op: Literal["test_missing"] = "test_missing"
    path: JSONPointer[JSONValue]
    require_parent: JSONBoolean = Field(
        default=True,
        deprecated=True,
        description="Deprecated; now defaults to true and will be removed "
        "in a future version.",
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if not self.require_parent:
            if self.path.is_gettable(doc):
                raise TestOpFailed(f"expected missing path at {self.path!r}")
            return doc
        state = classify_state(self.path.ptr, doc)
        if state in {
            TargetState.PARENT_NOT_FOUND,
            TargetState.PARENT_NOT_CONTAINER,
            TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX,
        }:
            raise PatchConflictError(
                f"require_parent rejects the state of {self.path!r}"
            )
        if state in {TargetState.ROOT, TargetState.VALUE_PRESENT}:
            raise TestOpFailed(f"expected missing path at {self.path!r}")
        return doc


# agent-example: test-missing:v3:end


# agent-example: add-missing-key:start
class AddMissingKeyOp(OperationSchema):
    """AddOp but only for objects missing the target key. Prevents silent overwrite.

    Example:
        doc={"profile": {}}
        op={"op": "add_missing_key", "path": "/profile/email", "value": "a@x.test"}
        If "/profile/email" already exists, this op fails instead of replacing it.
    """

    model_config = ConfigDict(
        title="Add Missing Key Operation",
        json_schema_extra={
            "description": "Add a key-value pair to an object, but only if the key is missing."
        },
    )
    op: Literal["add_missing_key"] = "add_missing_key"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        state = classify_state(self.path.ptr, doc)
        if state is TargetState.OBJECT_KEY_MISSING:
            return AddOp(path=self.path, value=self.value).apply(doc)
        if state is TargetState.VALUE_PRESENT:
            raise PatchConflictError(f"path {self.path!r} already exists")
        if state in {
            TargetState.ARRAY_INDEX_APPEND,
            TargetState.ARRAY_INDEX_AT_END,
            TargetState.ARRAY_INDEX_OUT_OF_RANGE,
            TargetState.ARRAY_KEY_INVALID,
            TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX,
        }:
            raise PatchConflictError(
                f"add_missing_key expects an object member path, got array path {self.path!r}"
            )
        if state is TargetState.PARENT_NOT_FOUND:
            raise PatchConflictError(
                f"cannot add key at {self.path!r} because parent does not exist"
            )
        if state is TargetState.PARENT_NOT_CONTAINER:
            raise PatchConflictError(
                f"cannot add key at {self.path!r} because parent is not a container"
            )
        if state is TargetState.ROOT:
            raise PatchConflictError("add_missing_key does not support root path")
        raise PatchConflictError(f"unsupported path state for {self.path!r}")


# agent-example: add-missing-key:end


def is_sensitive(path: JSONPointer[Any]) -> bool:
    """Check whether a password is sensitive; use to avoid leaking information."""
    markers = ("password", "passwd", "secret", "token", "api_key", "apikey")
    return any(path.parts[-1] == marker for marker in markers)


class SensitiveAwareTestOp(OperationSchema):
    """Blocks test on sensitive paths so probes cannot leak secret matches.

    Example:
        doc={"password": "p@ssw0rd"}
        op={"op": "test_sensitive_aware", "path": "/password", "value": "guess"}
        Always fails on sensitive paths, even if guessed value is correct.
    """

    model_config = ConfigDict(
        title="Sensitive-aware test operation",
        json_schema_extra={
            "description": "Run RFC test except on sensitive paths, where it always fails."
        },
    )
    op: Literal["test_sensitive_aware"] = "test_sensitive_aware"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if is_sensitive(self.path):
            raise TestOpFailed("test is not allowed on sensitive paths")
        return TestOp(path=self.path, value=self.value).apply(doc)


class ReplaceWithPriorOp(OperationSchema):
    """Captures previous value checks for auditable and reversible replace flows.

    Example:
        doc={"status": "draft"}
        op={
          "op": "replace_with_prior",
          "path": "/status",
          "priorValue": "draft",
          "value": "published"
        }
        The operation fails if current value is not "draft".
    """

    model_config = ConfigDict(
        title="Replace-with-prior operation",
        json_schema_extra={
            "description": "Replace only when the current value matches priorValue."
        },
    )
    op: Literal["replace_with_prior", "replace with prior"] = "replace_with_prior"
    path: JSONPointer[JSONValue]
    prior_value: JSONValue = Field(
        validation_alias=AliasChoices("prior value", "priorValue"),
        serialization_alias="priorValue",  # openapi requires ^[a-zA-Z0-9\.\-_]+$ but for parsing json 'prior value' is also accepted
    )
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current != self.prior_value:
            raise TestOpFailed(
                f"prior value mismatch at {self.path!r}: "
                f"expected {self.prior_value!r}, got {current!r}"
            )
        return ReplaceOp(path=self.path, value=self.value).apply(doc)


class RemoveWithOldValueOp(OperationSchema):
    """Makes remove invertible by carrying and validating old value.

    Example:
        doc={"nickname": "max"}
        op={"op": "remove_with_old", "path": "/nickname", "oldValue": "max"}
        The remove fails unless oldValue matches the current document value.
    """

    model_config = ConfigDict(
        title="Remove-with-old-value operation",
        json_schema_extra={
            "description": "Remove only when current value matches oldValue."
        },
    )
    op: Literal["remove_with_old"] = "remove_with_old"
    path: JSONPointer[JSONValue]
    old_value: JSONValue = Field(
        validation_alias=AliasChoices("old value", "oldValue"),
        serialization_alias="oldValue",
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current != self.old_value:
            raise TestOpFailed(
                f"old value mismatch at {self.path!r}: "
                f"expected {self.old_value!r}, got {current!r}"
            )
        return RemoveOp(path=self.path).apply(doc)


def _deep_merge_object(
    base: JSONObject[JSONValue], incoming: JSONObject[JSONValue]
) -> JSONObject[JSONValue]:
    """Recursively merge nested objects without dropping unrelated sibling keys.

    Example:
        base={"attributes": {"age": 15, "city": "Rome"}}
        incoming={"attributes": {"continent": "Europe"}}
        result={"attributes": {"age": 15, "city": "Rome", "continent": "Europe"}}
    """
    merged: JSONObject[JSONValue] = copy.deepcopy(base)
    for key, value in incoming.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_object(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class MergeObjectOp(OperationSchema):
    """Preserves sibling fields when independent patches target one object key.

    Example:
        doc={"attributes": {"age": 15}}
        op={"op": "merge_object", "path": "/attributes", "value": {"continent": "EU"}}
        Result keeps "age" and adds "continent".
    """

    model_config = ConfigDict(
        title="Merge-object operation",
        json_schema_extra={
            "description": "Merge object fields at path; optionally merge nested objects recursively."
        },
    )
    op: Literal["merge_object"] = "merge_object"
    path: JSONPointer[JSONObject[JSONValue]]
    value: JSONObject[JSONValue]
    deep: JSONBoolean = False

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        merged = (
            _deep_merge_object(current, self.value)
            if self.deep
            else {**current, **self.value}
        )
        return ReplaceOp(path=self.path, value=merged).apply(doc)


class IncrementByOp(OperationSchema):
    """Avoids read-modify-write races for simple counters.

    Example:
        doc={"votes": 10}
        op={"op": "increment_by", "path": "/votes", "amount": 1}
        Result is {"votes": 11} without a separate client read step.
    """

    model_config = ConfigDict(
        title="Increment-by operation",
        json_schema_extra={
            "description": "Increase a numeric value by amount in one patch step."
        },
    )
    op: Literal["increment_by"] = "increment_by"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)


class RemoveArrayValueOp(OperationSchema):
    """Removes by value so callers are not forced to discover unstable indexes.

    Example:
        doc={"roles": ["admin", "viewer", "editor"]}
        op={"op": "remove_array_value", "path": "/roles", "value": "viewer"}
        Removes "viewer" even if indexes shifted since the client last read.
    """

    model_config = ConfigDict(
        title="Remove-array-value operation",
        json_schema_extra={
            "description": "Remove matching array members by value (first or all)."
        },
    )
    op: Literal["remove_array_value"] = "remove_array_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value not in current:
            raise PatchConflictError("array value not found")
        match self.mode:
            case "first":
                current.remove(self.value)
            case "all":
                current[:] = [item for item in current if item != self.value]
            case _ as unreachable:
                assert_never(unreachable)
        return doc


# agent-example: replace-array-value:start
class ReplaceArrayValueOp(OperationSchema):
    """Replaces by value to support set-like arrays without index coupling.

    Example:
        doc={"tags": ["alpha", "beta", "beta"]}
        op={
          "op": "replace_array_value",
          "path": "/tags",
          "oldValue": "beta",
          "value": "stable",
          "mode": "first"
        }
        Replaces a matching value without requiring an index.
    """

    model_config = ConfigDict(
        title="Replace-array-value operation",
        json_schema_extra={
            "description": "Replace matching array members by value (first or all)."
        },
    )
    op: Literal["replace_array_value"] = "replace_array_value"
    path: JSONPointer[JSONArray[JSONValue]]
    old_value: JSONValue = Field(alias="oldValue")
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value not in current:
            raise PatchConflictError("array value to replace not found")
        match self.mode:
            case "first":
                for index, item in enumerate(current):
                    if item == self.old_value:
                        current[index] = self.value
                        break
            case "all":
                current[:] = [
                    item if item != self.old_value else self.value for item in current
                ]
            case _ as unreachable:
                assert_never(unreachable)
        return doc


# agent-example: replace-array-value:end


class SetUnionOp(OperationSchema):
    """Adds missing members only, matching set-style collection semantics.

    Example:
        doc={"features": ["chat"]}
        op={"op": "set_union", "path": "/features", "values": ["chat", "audit"]}
        Result is ["chat", "audit"] (no duplicate "chat").
    """

    model_config = ConfigDict(
        title="Set-union operation",
        json_schema_extra={
            "description": "Append only values that are not already present in an array."
        },
    )
    op: Literal["set_union"] = "set_union"
    path: JSONPointer[JSONArray[JSONValue]]
    values: JSONArray[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        for item in self.values:
            if item not in current:
                current.append(copy.deepcopy(item))
        return doc


class ReplaceTextSliceOp(OperationSchema):
    """Changes large strings surgically without replacing the full field value.

    Example:
        doc={"title": "Hello world"}
        op={
          "op": "replace_text_slice",
          "path": "/title",
          "start": 6,
          "end": 11,
          "text": "team"
        }
        Result is {"title": "Hello team"}.
    """

    model_config = ConfigDict(
        title="Replace-text-slice operation",
        json_schema_extra={
            "description": "Replace a substring by start/end offsets instead of replacing full text."
        },
    )
    op: Literal["replace_text_slice"] = "replace_text_slice"
    path: JSONPointer[JSONString]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: JSONString

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.start > self.end:
            raise PydanticCustomError(
                "replace_text_slice_range",
                "replace_text_slice requires start <= end",
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.end > len(current):
            raise PatchConflictError("text slice end is out of range")
        updated = current[: self.start] + self.text + current[self.end :]
        return ReplaceOp(path=self.path, value=updated).apply(doc)


class AddByValueOp(OperationSchema):
    """Insert relative to a matched value when index position is not reliable.

    Example:
        doc={"items": ["a", "c", "e", "z"]}
        op={"op": "add_by_value", "path": "/items", "value": "b", "before": "c"}
        Result is {"items": ["a", "b", "c", "e", "z"]}.
    """

    model_config = ConfigDict(
        title="Add-by-value operation",
        json_schema_extra={
            "description": "Insert array value before/after a matched anchor value."
        },
    )
    op: Literal["add_by_value"] = "add_by_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    before: JSONValue | None = None
    after: JSONValue | None = None

    @model_validator(mode="after")
    def _validate_anchor(self) -> Self:
        if (self.before is None) == (self.after is None):
            raise PydanticCustomError(
                "add_by_value_anchor",
                "add_by_value requires exactly one of 'before' or 'after'",
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        anchor = self.before if self.before is not None else self.after
        assert anchor is not None  # validated above
        for index, item in enumerate(current):
            if item == anchor:
                insert_at = index if self.before is not None else index + 1
                current.insert(insert_at, self.value)
                return doc
        raise PatchConflictError("anchor value not found")


class ReplaceByValueOp(OperationSchema):
    """Replace matched array values without depending on current index positions.

    Example:
        doc={"items": ["a", "c", "e", "z"]}
        op={"op": "replace_by_value", "path": "/items", "replace": "e", "value": "d"}
        Result is {"items": ["a", "c", "d", "z"]}.
    """

    model_config = ConfigDict(
        title="Replace-by-value operation",
        json_schema_extra={
            "description": "Replace first/all matched array values by value."
        },
    )
    op: Literal["replace_by_value"] = "replace_by_value"
    path: JSONPointer[JSONArray[JSONValue]]
    replace: JSONValue
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        replaced = False
        for index, item in enumerate(current):
            if item == self.replace:
                current[index] = self.value
                replaced = True
                if self.mode == "first":
                    return doc
        if not replaced:
            raise PatchConflictError("replace target value not found")
        return doc


class RemoveByValueOp(OperationSchema):
    """Remove first/all matched array values to avoid index-race removals.

    Example:
        doc={"items": ["a", "b", "c", "d"]}
        op={"op": "remove_by_value", "path": "/items", "value": "d"}
        Result is {"items": ["a", "b", "c"]}.
    """

    model_config = ConfigDict(
        title="Remove-by-value operation",
        json_schema_extra={
            "description": "Remove first/all matched array values by value."
        },
    )
    op: Literal["remove_by_value"] = "remove_by_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.mode == "first":
            for index, item in enumerate(current):
                if item == self.value:
                    del current[index]
                    return doc
            raise PatchConflictError("remove target value not found")

        filtered = [item for item in current if item != self.value]
        if len(filtered) == len(current):
            raise PatchConflictError("remove target value not found")
        current[:] = filtered
        return doc


# agent-example: lowercase:start
class LowercaseOp(OperationSchema):
    """Lowercase a string value."""

    model_config = ConfigDict(title="Lowercase operation")
    op: Literal["lowercase"] = "lowercase"
    path: JSONPointer[JSONString]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current.lower()).apply(doc)


# agent-example: lowercase:end


# agent-example: swap:start
class SwapOp(OperationSchema):
    """Swap the values at two pointers."""

    model_config = ConfigDict(
        title="Swap operation",
        json_schema_extra={
            "description": (
                "Swaps the values at paths a and b. "
                "Paths a and b may not be proper prefixes of each other."
            )
        },
    )
    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise PydanticCustomError(
                "swap_path_conflict",
                "pointer 'b' cannot be a child of pointer 'a'",
            )
        if self.b.is_parent_of(self.a):
            raise PydanticCustomError(
                "swap_path_conflict",
                "pointer 'a' cannot be a child of pointer 'b'",
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)


# agent-example: swap:end


class ReplaceNumberOp(OperationSchema):
    """Replace a numeric value at the target path."""

    model_config = ConfigDict(title="Replace-number operation")
    op: Literal["replace_number"] = "replace_number"
    path: JSONPointer[JSONNumber]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=self.value).apply(doc)


class AddToSetOp(OperationSchema):
    """Add a value to an array only if it is not already present.

    Example:
        doc={"tags": ["alpha", "beta"]}
        op={"op": "add_to_set", "path": "/tags", "value": "beta"}
        Result is unchanged; "beta" is already present.
    """

    model_config = ConfigDict(
        title="Add-to-set operation",
        json_schema_extra={
            "description": "Add a value to an array only if it is not already "
            "present, using whole-value equality. A duplicate is a no-op."
        },
    )
    op: Literal["add_to_set"] = "add_to_set"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value in current:
            return doc
        return ReplaceOp(path=self.path, value=[*current, self.value]).apply(doc)


# agent-example: add-to-set:v2:start
class AddToSetOpIgnoreCase(OperationSchema):
    """Add a value to an array only if it is not already present.

    Stage 2 of `AddToSetOp`'s evolution: adds `ignore_case` for
    case-insensitive comparison of string values, defaulting to the original
    exact-equality behavior.
    """

    model_config = ConfigDict(
        title="Add-to-set operation",
        json_schema_extra={
            "description": "Add a value to an array only if it is not already present."
        },
    )
    op: Literal["add_to_set"] = "add_to_set"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    ignore_case: JSONBoolean = Field(
        default=False,
        description="Compare string values case-insensitively.",
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.ignore_case and isinstance(self.value, str):
            needle = self.value.casefold()
            found = any(
                isinstance(item, str) and item.casefold() == needle for item in current
            )
        else:
            found = self.value in current
        if found:
            return doc
        return ReplaceOp(path=self.path, value=[*current, self.value]).apply(doc)


# agent-example: add-to-set:v2:end


# agent-example: add-to-set:v3:start
class AddToSetOpComparison(OperationSchema):
    """Add a value to an array only if it is not already present.

    Stage 3 of `AddToSetOp`'s evolution: `ignore_case` is deprecated in favor
    of `comparison`. The two are mutually exclusive, and neither has a
    concrete default: once split, "the default" no longer belongs to either
    field alone.
    """

    model_config = ConfigDict(
        title="Add-to-set operation",
        validate_default=False,
        json_schema_extra={
            "description": "Add a value to an array only if it is not already present."
        },
    )
    op: Literal["add_to_set"] = "add_to_set"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    ignore_case: JSONBoolean = Field(
        default=cast(JSONBoolean, MISSING),
        deprecated=True,
        description="Deprecated; use 'comparison' instead.",
    )
    comparison: Literal["exact", "case_insensitive"] = Field(
        default=cast(Literal["exact", "case_insensitive"], MISSING),
        description="Comparison mode. Mutually exclusive with the deprecated 'ignore_case'.",
    )

    @model_validator(mode="after")
    def _validate_mutually_exclusive(self) -> Self:
        if (
            "ignore_case" in self.model_fields_set
            and "comparison" in self.model_fields_set
        ):
            raise ValueError(
                "add_to_set accepts 'ignore_case' or 'comparison', not both"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if "comparison" in self.model_fields_set:
            case_insensitive = self.comparison == "case_insensitive"
        elif "ignore_case" in self.model_fields_set:
            case_insensitive = self.ignore_case
        else:
            case_insensitive = False
        if case_insensitive and isinstance(self.value, str):
            needle = self.value.casefold()
            found = any(
                isinstance(item, str) and item.casefold() == needle for item in current
            )
        else:
            found = self.value in current
        if found:
            return doc
        return ReplaceOp(path=self.path, value=[*current, self.value]).apply(doc)


# agent-example: add-to-set:v3:end


class SetRolloutPercentageOp(OperationSchema):
    """Set a named rollout variation's percentage.

    Example:
        doc={"rollout": {"enabled": 25, "disabled": 75}}
        op={
          "op": "set_rollout_percentage",
          "path": "/rollout",
          "variation": "enabled",
          "percentage": 40
        }
        Result is {"rollout": {"enabled": 40, "disabled": 60}}: the named
        variation is set directly, and its complementary variation is
        adjusted so the two continue to sum to 100.
    """

    model_config = ConfigDict(
        title="Set-rollout-percentage operation",
        json_schema_extra={
            "description": "Set a named variation's percentage in a "
            "two-variation rollout, adjusting the complementary variation "
            "so the two sum to 100."
        },
    )
    op: Literal["set_rollout_percentage"] = "set_rollout_percentage"
    path: JSONPointer[JSONObject[JSONNumber]]
    variation: JSONString
    percentage: JSONNumber = Field(ge=0, le=100)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if len(current) != 2:
            raise PatchConflictError(
                "set_rollout_percentage requires exactly two variations"
            )
        if self.variation not in current:
            raise PatchConflictError(f"unknown rollout variation {self.variation!r}")
        other = next(name for name in current if name != self.variation)
        updated = dict(current)
        updated[self.variation] = self.percentage
        updated[other] = 100 - self.percentage
        return ReplaceOp(path=self.path, value=updated).apply(doc)  # type: ignore[arg-type]


# agent-example: set-rollout-percentage:v2:start
class SetRolloutPercentageOpRelative(OperationSchema):
    """Set a named rollout variation's percentage.

    Stage 2 of `SetRolloutPercentageOp`'s evolution: adds `relative`, so a
    caller can increase a variation by a delta instead of setting an
    absolute value, defaulting to the original absolute-set behavior.
    `percentage` keeps its original non-negative range in both modes, so its
    sign never has to carry meaning.
    """

    model_config = ConfigDict(
        title="Set-rollout-percentage operation",
        json_schema_extra={
            "description": "Set a named variation's percentage in a two-variation rollout."
        },
    )
    op: Literal["set_rollout_percentage"] = "set_rollout_percentage"
    path: JSONPointer[JSONObject[JSONNumber]]
    variation: JSONString
    percentage: JSONNumber = Field(ge=0, le=100)
    relative: JSONBoolean = Field(
        default=False,
        description="If true, increase the variation by percentage instead "
        "of setting it outright.",
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if len(current) != 2:
            raise PatchConflictError(
                "set_rollout_percentage requires exactly two variations"
            )
        if self.variation not in current:
            raise PatchConflictError(f"unknown rollout variation {self.variation!r}")
        other = next(name for name in current if name != self.variation)
        target = (
            current[self.variation] + self.percentage
            if self.relative
            else self.percentage
        )
        target = max(0, min(100, target))
        updated = dict(current)
        updated[self.variation] = target
        updated[other] = 100 - target
        return ReplaceOp(path=self.path, value=updated).apply(doc)  # type: ignore[arg-type]


# agent-example: set-rollout-percentage:v2:end


# agent-example: set-rollout-percentage:v3:start
class SetRolloutPercentageOpMode(OperationSchema):
    """Set a named rollout variation's percentage.

    Stage 3 of `SetRolloutPercentageOp`'s evolution: `relative` is deprecated
    in favor of `mode`, which can also express "decrease" without ever
    letting `percentage`'s sign carry meaning. The two are mutually
    exclusive, and neither has a concrete default once split.
    """

    model_config = ConfigDict(
        title="Set-rollout-percentage operation",
        validate_default=False,
        json_schema_extra={
            "description": "Set a named variation's percentage in a two-variation rollout."
        },
    )
    op: Literal["set_rollout_percentage"] = "set_rollout_percentage"
    path: JSONPointer[JSONObject[JSONNumber]]
    variation: JSONString
    percentage: JSONNumber = Field(ge=0, le=100)
    relative: JSONBoolean = Field(
        default=cast(JSONBoolean, MISSING),
        deprecated=True,
        description="Deprecated; use 'mode' instead.",
    )
    mode: Literal["set", "increase", "decrease"] = Field(
        default=cast(Literal["set", "increase", "decrease"], MISSING),
        description="How to apply percentage. Mutually exclusive with the deprecated 'relative'.",
    )

    @model_validator(mode="after")
    def _validate_mutually_exclusive(self) -> Self:
        if "relative" in self.model_fields_set and "mode" in self.model_fields_set:
            raise ValueError(
                "set_rollout_percentage accepts 'relative' or 'mode', not both"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if len(current) != 2:
            raise PatchConflictError(
                "set_rollout_percentage requires exactly two variations"
            )
        if self.variation not in current:
            raise PatchConflictError(f"unknown rollout variation {self.variation!r}")
        other = next(name for name in current if name != self.variation)

        if "mode" in self.model_fields_set:
            effective_mode = self.mode
        elif "relative" in self.model_fields_set and self.relative:
            effective_mode = "increase"
        else:
            effective_mode = "set"

        match effective_mode:
            case "set":
                target = self.percentage
            case "increase":
                target = current[self.variation] + self.percentage
            case "decrease":
                target = current[self.variation] - self.percentage
            case _ as unreachable:
                assert_never(unreachable)
        target = max(0, min(100, target))
        updated = dict(current)
        updated[self.variation] = target
        updated[other] = 100 - target
        return ReplaceOp(path=self.path, value=updated).apply(doc)  # type: ignore[arg-type]


# agent-example: set-rollout-percentage:v3:end
