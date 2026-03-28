"""
jsonpatch.standard

Core patch application engine + public convenience wrappers.

This module is the “behavioral center” of the library: it defines *copy semantics*,
*error semantics*, and the *operational contract* for applying a sequence of typed
operations to a JSON document.

### Copy & mutation semantics (single source of truth)

Operations are allowed to be *mutative* (i.e., they may modify the document object
they receive). The engine controls whether those mutations affect the caller's
original document:

- inplace=False (default): deep-copy the input document first, then apply ops to the copy.
  The caller's original object is not modified.

- inplace=True: apply ops directly to the input object (faster, avoids copy) but is NOT
  transactional. If an operation fails mid-patch, earlier operations may already have
  mutated the document (no rollback). This is a copy policy, not an object-identity
  guarantee: root-targeting operations (path "") may return a new root value.

### Typed pointer semantics (why some failures are “intentional”)

Operation schemas frequently carry typed pointers: JSONPointer[T].

Typing is not only static; it is a runtime contract:
- Pointer reads validate the resolved value against T.
- This implies “type-gated” behavior for composite semantics like remove/replace:
  remove can fail if the current value exists but does not conform to T, because
  the operation is explicitly scoped to “what is removable”.

This library prefers explicitness:
- widen T (e.g., JSONValue) to be permissive
- or define a more specific op if you want stricter behavior

### Error semantics

Expected patch failures (subclasses of PatchError) propagate unchanged.

Unexpected exceptions are wrapped with structured metadata (operation index + the full
operation payload) so API layers can report actionable failures.
"""

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

    ``JsonPatch`` is a convenience wrapper that:

    - parses and validates an input patch document using a registry of ``OperationSchema`` models,
    - stores the resulting typed ``OperationSchema`` instances,
    - applies them to JSON documents via the shared patch engine.

    Notes:
        - ``apply`` delegates to the core engine ``_apply_ops`` and follows the same copy and mutation
          semantics.
        - ``inplace=False`` (default): the engine deep-copies ``doc`` first; operations may mutate the copy.
        - ``inplace=True``: operations run against the provided ``doc`` object (no rollback on failure).
          This is a copy policy, not an object-identity guarantee for the returned value.
        - ``JsonPatch`` is immutable with respect to its operation list after construction, but the
          documents you apply it to may be mutated depending on ``inplace``.
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

        Args:
            patch: A sequence of JSON Patch operations as dicts.
            registry: A union of concrete OperationSchemas used for parsing and
                validation (``OpA | OpB | ...``). If omitted, the standard RFC
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

        JSON decoding follows last-write-wins just like ``json.loads()``
        If you want strict duplicate-key rejection, parse JSON yourself and pass the result to ``JsonPatch()``.

        Args:
            text: JSON-formatted string/bytes/bytearray for a JSON Patch document.
            registry: A union of concrete OperationSchemas used for parsing and
                validation (``OpA | OpB | ...``). If omitted, the standard RFC
                6902 operations are used.
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
        Apply this patch to ``doc`` and return the patched document.

        Args:
            doc: The target JSON document.
            inplace: Copy policy. ``False`` deep-copies ``doc`` before applying operations.
                ``True`` skips that copy and applies operations against ``doc``, but does not
                guarantee returned object identity for root-targeting operations.

        Return:
            patched: The patched JSON document.

        Raises:
            ValidationError: If the input is not a mutable ``JSONValue``.
            PatchError: Any patch-domain error raised by operations, including conflicts.
                ``PatchInternalError`` is a ``PatchError`` raised for unexpected failures.
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
    Apply a standard RFC 6902 JSON Patch document to ``doc``.

    This is a small convenience wrapper around ``JsonPatch`` using the standard registry.

    Args:
        doc: Target JSON document.
        patch: Patch document as a sequence of operation mappings.
        registry: A union of concrete OperationSchemas used for parsing and
            validation (``OpA | OpB | ...``). If omitted, the standard RFC
            6902 operations are used.
        inplace: Copy policy. ``False`` deep-copies ``doc`` first; ``True`` skips that copy.
            This is not a guarantee that the returned object is the exact same root object.
            See ``_apply_ops(..., inplace=...)`` for full semantics.

    Returns:
        The patched document.
    """
    return JsonPatch(patch, registry=registry).apply(doc, inplace=inplace)
