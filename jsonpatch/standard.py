import copy
import json
from collections.abc import Mapping, Sequence
from typing import Hashable, Self, overload, override

from jsonpatch.exceptions import PatchApplicationError, PatchError
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.types import _JSON_VALUE_ADAPTER, JSONValue


def _apply_ops(
    ops: Sequence[OperationSchema], doc: JSONValue, *, inplace: bool = False
) -> JSONValue:
    """
    Core operation application loop shared by JsonPatch and model-aware patches.

    Error semantics:
    - PatchError subclasses from op.apply() are propagated.
    - Unexpected exceptions are wrapped in PatchApplicationError.
    """
    if not inplace:
        doc = copy.deepcopy(doc)
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
        patch: Sequence[Mapping[str, JSONValue]] | Sequence[OperationSchema],
        *,
        registry: OperationRegistry | None = None,
    ):
        """
        Construct a JsonPatch from a sequence of operation dicts.

        Args:
            patch: A sequence of JSON Patch operations as dicts.
            registry: OperationRegistry to use for parsing/validation. If omitted,
                      the standard RFC 6902 registry is used.
        """
        self._registry = registry or OperationRegistry.standard()
        self._ops: list[OperationSchema] = self._registry.parse_python_patch(patch)

    @classmethod
    def from_string(
        cls,
        text: str | bytes | bytearray,
        *,
        registry: OperationRegistry | None = None,
    ) -> Self:
        """
        Construct a JsonPatch from a JSON-formatted string.

        Args:
            text: JSON-formatted string/bytes/bytearray for a JSON Patch document.
            registry: OperationRegistry to use for parsing/validation. If omitted,
                      the standard RFC 6902 registry is used.
        """
        instance = cls.__new__(cls)
        registry = registry or OperationRegistry.standard()
        instance._registry = registry
        instance._ops = registry.parse_json_patch(text)
        return instance

    @classmethod
    def _from_operations(
        cls, ops: list[OperationSchema], *, registry: OperationRegistry | None = None
    ) -> Self:
        instance = cls.__new__(cls)
        registry = registry or OperationRegistry.standard()
        instance._registry = registry
        instance._ops = ops
        return instance

    @property
    def ops(self) -> Sequence[OperationSchema]:
        """The sequence of operations."""
        return self._ops

    def to_string(self) -> str:
        """Serialize this patch to a JSON string."""
        payload = [op.model_dump(mode="json", by_alias=True) for op in self._ops]
        return json.dumps(payload)

    def apply(self, doc: JSONValue, *, validate_doc: bool = False) -> JSONValue:
        """Apply the JsonPatch to an object."""
        if validate_doc:
            _JSON_VALUE_ADAPTER.validate_python(doc, strict=True)
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
        # Hashing is best-effort, user-defined ops may be unhashable.
        return hash((self.__class__, self._registry, tuple(self._ops)))

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
        if self._registry is not other._registry:
            raise TypeError("Cannot add JsonPatch instances with different registries")
        return self._from_operations(self._ops + other._ops, registry=self._registry)


def apply_patch(doc: JSONValue, patch: Sequence[Mapping[str, JSONValue]]) -> JSONValue:
    """Apply standard JSON Patch to an object."""
    return JsonPatch(patch).apply(doc)


if __name__ == "__main__":
    raw: list[dict[str, JSONValue]] = [
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

    doc: dict[str, JSONValue] = {}
    result = patch.apply(doc)
    assert result == apply_patch(doc, raw)
