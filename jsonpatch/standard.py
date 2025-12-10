import json
from collections.abc import Collection, Mapping, Sequence
from typing import Hashable, Self, overload, override

from jsonpatch.builtins import STANDARD_OPS
from jsonpatch.exceptions import PatchApplicationError
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JsonTextType, JsonValueType


class JsonPatch(Sequence[OperationSchema], Hashable):
    __slots__ = ("_ops",)

    def __init__(
        self,
        patch: Sequence[Mapping[str, JsonValueType]],
        *,
        op_schemas: Collection[type[OperationSchema]] = STANDARD_OPS,
    ):
        """Construct a JsonPatch from a list of operations.

        Args:
            patch (Sequence[Mapping[str, JsonValueType]]): A list of JSON patch operations.
            ops (Collection[type[OperationSchema]], optional): OperationSchemas that the JsonPatch will recognize. Defaults to STANDARD_OPS.
        """
        registry = OperationRegistry(*op_schemas)
        self._ops: list[OperationSchema] = registry.parse_python_patch(patch)

    @classmethod
    def from_string(
        cls,
        text: JsonTextType,
        *,
        op_schemas: Collection[type[OperationSchema]] = STANDARD_OPS,
    ) -> Self:
        """Construct a JsonPatch from a JSON-formatted string.

        Args:
            text (JsonTextType): JSON-formatted string.
            ops (Collection[type[OperationSchema]], optional): OperationSchemas that the JsonPatch will recognize. Defaults to STANDARD_OPS.

        Returns:
            Self: A JsonPatch instance.
        """
        registry = OperationRegistry(*op_schemas)
        instance = cls.__new__(cls)
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
        for index, op in enumerate(self._ops):
            try:
                doc = op.apply(doc)
            except Exception as e:
                raise PatchApplicationError(
                    f"Failed to apply operation {op!r} at patch index {index}: {e}"
                ) from e
        return doc

    def __add__(self, other: object) -> Self:
        if not isinstance(other, JsonPatch):
            return NotImplemented
        instance = self.__new__(self.__class__)
        instance._ops = self._ops + other._ops
        return instance

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
