import json
from collections.abc import Mapping, Sequence
from typing import Hashable, Self, overload, override

from jsonpatch.exceptions import PatchApplicationError, PatchError
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JsonTextType, JsonValueType


def _apply_ops(
    ops: Sequence[OperationSchema],
    doc: JsonValueType,
) -> JsonValueType:
    """
    Core operation application loop shared by JsonPatch and model-aware patches.

    Error semantics:
    - PatchError subclasses from op.apply() are propagated.
    - Unexpected exceptions are wrapped in PatchApplicationError.
    """
    for index, op in enumerate(ops):
        try:
            doc = op.apply(doc)
        except PatchError:
            # Domain-specific patch errors (e.g. TestOpFailed) should propagate unchanged.
            raise
        except Exception as e:
            raise PatchApplicationError(
                f"Error applying {op!r} at index {index}: {e}"
            ) from e
    return doc


class JsonPatch(Sequence[OperationSchema], Hashable):
    __slots__ = ("_ops", "_registry")

    def __init__(
        self,
        python: Sequence[Mapping[str, JsonValueType]],
        *,
        registry: OperationRegistry | None = None,
    ):
        """
        Construct a JsonPatch from a list of operations.

        If no registry is provided, the standard RFC 6902 registry is used.
        """
        self._registry = registry or OperationRegistry.standard()
        self._ops: list[OperationSchema] = self._registry.parse_python_patch(python)

    @classmethod
    def from_string(
        cls,
        text: JsonTextType,
        *,
        registry: OperationRegistry | None = None,
    ) -> Self:
        """Construct a JsonPatch from a JSON-formatted string.

        If no registry is provided, the standard RFC 6902 registry is used.
        """
        instance = cls.__new__(cls)
        registry = registry or OperationRegistry.standard()
        instance._registry = registry
        instance._ops = registry.parse_json_patch(text)
        return instance

    @property
    def ops(self) -> Sequence[OperationSchema]:
        """The sequence of operations."""
        return self._ops

    def to_string(self) -> str:
        """Serialize this patch to a JSON string."""
        payload = [op.model_dump(mode="json", by_alias=True) for op in self._ops]
        return json.dumps(payload)

    def apply(self, doc: JsonValueType) -> JsonValueType:
        """Apply the JsonPatch to an object."""
        return _apply_ops(self._ops, doc)

    @override
    def __len__(self) -> int:
        return len(self._ops)

    @overload
    def __getitem__(self, index: int) -> OperationSchema: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[OperationSchema]: ...

    @override
    def __getitem__(
        self, index: int | slice
    ) -> OperationSchema | Sequence[OperationSchema]:
        return self._ops[index]

    @override
    def __hash__(self) -> int:
        return hash(tuple(self._ops))

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JsonPatch):
            return NotImplemented
        return self._ops == other._ops

    @override
    def __str__(self) -> str:
        return self.to_string()

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self})"

    def __add__(self, other: object) -> Self:
        if not isinstance(other, JsonPatch):
            return NotImplemented
        instance = self.__new__(self.__class__)
        instance._ops = self._ops + other._ops
        return instance


def apply_patch(
    doc: JsonValueType, patch: Sequence[Mapping[str, JsonValueType]]
) -> JsonValueType:
    """Apply standard JSON Patch to an object."""
    return JsonPatch(patch).apply(doc)


if __name__ == "__main__":
    raw: list[dict[str, JsonValueType]] = [
        {"op": "add", "path": "/foo", "value": "bar"},
        {"op": "add", "path": "/baz", "value": [1, 2, 3]},
        {"op": "remove", "path": "/baz/1"},
        {"op": "test", "path": "/baz", "value": [1, 3]},
        {"op": "replace", "path": "/baz/0", "value": 42},
        {"op": "remove", "path": "/baz/1"},
    ]
    patch = JsonPatch(raw)
    patch2 = JsonPatch.from_string(
        '[{"op": "add", "path": "/foo", "value": "bar"}, {"op": "add", "path": "/baz", "value": [1, 2, 3]}, {"op": "remove", "path": "/baz/1"}, {"op": "test", "path": "/baz", "value": [1, 3]}, {"op": "replace", "path": "/baz/0", "value": 42}, {"op": "remove", "path": "/baz/1"}]'
    )
    assert patch._ops == patch2._ops

    doc: dict[str, JsonValueType] = {}
    result = patch.apply(doc)
    assert result == apply_patch(doc, raw)
