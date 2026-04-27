import json
from collections.abc import Mapping, Sequence
from typing import Self, overload, override

from typing_extensions import TypeForm

from jsonpatchx.exceptions import PatchValidationError
from jsonpatchx.registry import _STANDARD_REGISTRY_SPEC, _RegistrySpec
from jsonpatchx.schema import OperationSchema, _apply_ops
from jsonpatchx.types import JSONValue, _validate_JSONValue


class JsonPatch(Sequence[OperationSchema]):
    """
    A parsed JSON Patch document (RFC 6902-style) bound to a registry declaration.

    `JsonPatch` is a convenience wrapper that:

    - parses and validates an input patch document using a registry of `OperationSchema` models,
    - stores the resulting typed `OperationSchema` instances,
    - applies them to JSON documents via the shared patch engine.

    Notes:
        - `inplace=False` (default): deep-copies `doc` first; the original is not modified.
        - `inplace=True`: applies operations to `doc` directly; faster, but not transactional
          (no rollback on partial failure), and root-targeting operations may return a new
          object rather than `doc`.
        - `JsonPatch` is immutable with respect to its operation list after construction.
    """

    __slots__ = ("_ops", "_registry")

    def __init__(
        self,
        patch: Sequence[Mapping[str, JSONValue]] | Sequence[OperationSchema],
        *,
        registry: TypeForm[OperationSchema] | None = None,
    ):
        """
        Construct a JsonPatch from a sequence of operation dicts.

        Arguments:
            patch: A sequence of JSON Patch operations as dicts.
            registry: A union of concrete OperationSchemas used for parsing and
                validation (`OpA | OpB | ...`). If omitted, the standard RFC
                6902 operations are used.
        """
        if registry is None:
            self._registry = _STANDARD_REGISTRY_SPEC
        else:
            self._registry = _RegistrySpec.from_typeform(registry)
        self._ops = self._registry.parse_python_patch(patch)

    @classmethod
    def from_string(
        cls,
        text: str | bytes | bytearray,
        *,
        registry: TypeForm[OperationSchema] | None = None,
    ) -> Self:
        """
        Construct a JsonPatch from a JSON-formatted string.

        Arguments:
            text: JSON-formatted string, bytes, or bytearray containing a JSON
                Patch document.
            registry: A union of concrete OperationSchemas used for parsing and
                validation (`OpA | OpB | ...`). If omitted, the standard RFC
                6902 operations are used.

        Returns:
            A parsed `JsonPatch` instance.

        Notes:
            JSON decoding follows last-write-wins, just like `json.loads()`.
            If you need strict duplicate-key rejection, decode JSON yourself
            and pass the resulting Python value to `JsonPatch(...)`.
        """
        instance = cls.__new__(cls)
        if registry is None:
            resolved = _STANDARD_REGISTRY_SPEC
        else:
            resolved = _RegistrySpec.from_typeform(registry)
        instance._registry = resolved
        instance._ops = resolved.parse_json_patch(text)
        return instance

    @property
    def ops(self) -> Sequence[OperationSchema]:
        """The sequence of operations."""
        return self._ops

    def to_string(self) -> str:
        """Serialize this patch to a JSON string."""
        payload = [op.model_dump(mode="json", by_alias=True) for op in self._ops]
        return json.dumps(payload)

    def apply(
        self,
        doc: JSONValue,
        *,
        inplace: bool = False,
    ) -> JSONValue:
        """
        Apply this patch to `doc` and return the patched document.

        Arguments:
            doc: The target JSON document.
            inplace: If `False` (default), `doc` is deep-copied first; the original is not modified.
                If `True`, operations are applied to `doc` directly; root-targeting operations
                may return a new object rather than `doc`.

        Returns:
            patched: The patched JSON document.

        Raises:
            PatchValidationError: If `doc` is not a valid JSON document.
            PatchError: Any patch-domain error raised by operations, including conflicts.
                `PatchInternalError` is a `PatchError` raised for unexpected failures.
        """
        try:
            _validate_JSONValue(doc)
        except Exception as e:
            raise PatchValidationError(f"Invalid JSON document: {e}") from e
        return _apply_ops(self._ops, doc, inplace=inplace)

    @override
    def __len__(self) -> int:
        return len(self._ops)

    @overload
    def __getitem__(self, index: int) -> OperationSchema:
        pass

    @overload
    def __getitem__(self, index: slice) -> Sequence[OperationSchema]:
        pass

    @override
    def __getitem__(
        self, index: int | slice
    ) -> OperationSchema | Sequence[OperationSchema]:
        return self._ops[index]

    @override
    def __hash__(self) -> int:
        # Hashing is best-effort, user-defined ops may be unhashable.
        return hash((self.__class__, self._registry, tuple(self)))

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return tuple(self) == tuple(other) and self._registry == other._registry

    @override
    def __str__(self) -> str:
        return self.to_string()

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self})"

    def __add__(self, other: object) -> Self:
        if not isinstance(other, self.__class__):
            return NotImplemented
        if self._registry != other._registry:
            raise TypeError("Cannot add JsonPatch instances with different registries")
        instance = self.__class__.__new__(self.__class__)
        instance._registry = self._registry
        instance._ops = self._ops + other._ops
        return instance


def apply_patch(
    doc: JSONValue,
    patch: Sequence[Mapping[str, JSONValue]],
    *,
    registry: TypeForm[OperationSchema] | None = None,
    inplace: bool = False,
) -> JSONValue:
    """
    Apply a standard RFC 6902 JSON Patch document to `doc`.

    Arguments:
        doc: Target JSON document.
        patch: Patch document as a sequence of operation mappings.
        registry: A union of concrete OperationSchemas used for parsing and
            validation (`OpA | OpB | ...`). If omitted, the standard RFC
            6902 operations are used.
        inplace: If `False` (default), `doc` is deep-copied first; the original is not modified.
            If `True`, operations are applied to `doc` directly; faster, but not transactional
            (no rollback on partial failure), and root-targeting operations may return a new
            object rather than `doc`.

    Returns:
        The patched document.

    Raises:
        PatchValidationError: If `doc` is not a valid JSON document.
        PatchError: Any patch-domain error raised by patch parsing or
            application.

    Notes:
        This is a small convenience wrapper around `JsonPatch` using the
        standard registry.
    """
    return JsonPatch(patch, registry=registry).apply(doc, inplace=inplace)
