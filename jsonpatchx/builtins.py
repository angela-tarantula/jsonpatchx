import copy
from typing import Literal, Self, override

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from jsonpatchx.exceptions import (
    PatchConflictError,
    TestOpFailed,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


class AddOp(OperationSchema):
    """RFC 6902 add operation."""

    model_config = ConfigDict(
        title="Add operation",
        json_schema_extra={"description": "RFC 6902 add operation."},
    )

    op: Literal["add"] = "add"
    path: JSONPointer[JSONValue] = Field(
        description='Location to add the value. Use `"-"` as the final token to append to an array.'
    )
    value: JSONValue = Field(description="Value to add.")

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        """Add `value` at `path` according to RFC 6902 semantics.

        Raises:
            PatchConflictError: If the parent location does not exist, is not an array or
                object, or the array index is out of range or invalid.
        """
        return self.path.add(doc, self.value)


class RemoveOp(OperationSchema):
    """RFC 6902 remove operation."""

    model_config = ConfigDict(
        title="Remove operation",
        json_schema_extra={"description": "RFC 6902 remove operation."},
    )

    op: Literal["remove"] = "remove"
    path: JSONPointer[JSONValue] = Field(description="Location of the value to remove.")

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        """Remove the value at `path` according to RFC 6902 semantics.

        Raises:
            PatchConflictError: If `path` targets the document root, the target does not
                exist, the parent is not an array or object, the array index is out of
                range, or the final token is `"-"` (`"-"` is append-only and does not
                address an existing element).
        """
        if self.path.is_root(doc):
            raise PatchConflictError("cannot delete the document")
        return self.path.remove(doc)


class ReplaceOp(OperationSchema):
    """RFC 6902 replace operation."""

    model_config = ConfigDict(
        title="Replace operation",
        json_schema_extra={"description": "RFC 6902 replace operation."},
    )

    op: Literal["replace"] = "replace"
    path: JSONPointer[JSONValue] = Field(
        description="Location of the value to replace."
    )
    value: JSONValue = Field(description="Replacement value.")

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        """Replace the value at `path` with `value` according to RFC 6902 semantics.

        Raises:
            PatchConflictError: If the target does not exist, the parent is not an array
                or object, the array index is out of range, or the final token is `"-"`
                (which does not address an existing element).
        """
        if self.path.is_root(doc):
            return AddOp(path=self.path, value=self.value).apply(doc)
        doc = RemoveOp(path=self.path).apply(doc)
        return AddOp(path=self.path, value=self.value).apply(doc)


class MoveOp(OperationSchema):
    """RFC 6902 move operation.

    Raises:
        ValidationError: If `path` is a descendant of `from` (enforced at parse time).

    Notes:
        When constructing directly in Python, use `from_=...`; in JSON, use `"from"` as the key.
    """

    model_config = ConfigDict(
        title="Move operation",
        json_schema_extra={"description": "RFC 6902 move operation."},
    )

    op: Literal["move"] = "move"
    from_: JSONPointer[JSONValue] = Field(
        alias="from", description="Location of the value to move."
    )
    path: JSONPointer[JSONValue] = Field(
        description="Destination for the moved value. Must not be a descendant of `from`."
    )

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.from_.is_parent_of(self.path):
            raise PydanticCustomError(
                "move_path_conflict",
                "pointer 'path' cannot be a child of pointer 'from'",
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        """Move the value at `from_` to `path` according to RFC 6902 semantics.

        Raises:
            PatchConflictError: If the `from_` target does not exist, or `path` is not a valid destination.
        """
        value = self.from_.get(doc)
        doc = RemoveOp(path=self.from_).apply(doc)
        return AddOp(path=self.path, value=value).apply(doc)


class CopyOp(OperationSchema):
    """RFC 6902 copy operation.

    Notes:
        When constructing directly in Python, use `from_=...`; in JSON, use `"from"` as the key.
    """

    model_config = ConfigDict(
        title="Copy operation",
        json_schema_extra={"description": "RFC 6902 copy operation."},
    )

    op: Literal["copy"] = "copy"
    from_: JSONPointer[JSONValue] = Field(
        alias="from", description="Location of the value to copy."
    )
    path: JSONPointer[JSONValue] = Field(
        description="Destination for the copied value."
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        """Copy the value at `from_` to `path` according to RFC 6902 semantics.

        Raises:
            PatchConflictError: If the `from_` target does not exist, or `path` is not a valid destination.
        """
        value = self.from_.get(doc)
        duplicate = copy.deepcopy(value)
        return AddOp(path=self.path, value=duplicate).apply(doc)


class TestOp(OperationSchema):
    """RFC 6902 test operation."""

    __test__ = False  # Suppress pytest warning

    model_config = ConfigDict(
        title="Test operation",
        json_schema_extra={"description": "RFC 6902 test operation."},
    )

    op: Literal["test"] = "test"
    path: JSONPointer[JSONValue] = Field(description="Location of the value to test.")
    value: JSONValue = Field(description="Expected value.")

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        """Test that `path` resolves to `value` according to RFC 6902 semantics.

        Raises:
            PatchConflictError: If the target does not exist or the final token is `"-"`
                (which does not address an existing element).
            TestOpFailed: If the value at `path` does not equal `value`.
        """
        actual = self.path.get(doc)
        if actual != self.value:
            raise TestOpFailed(
                f"test at path {self.path!r} failed, got {actual!r} but expected {self.value!r}"
            )
        return doc
