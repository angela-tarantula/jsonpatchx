from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from jsonpatchx import apply_patch


def test_apply_patch_delegates_preserving_arguments_and_return() -> None:
    """apply_patch must be a strict pass-through to JsonPatch(...).apply(...)."""
    arbitrary_doc: Any = object()
    arbitrary_patch: Any = object()
    arbitrary_result: Any = object()

    mock_patch = MagicMock()
    mock_patch.apply.return_value = arbitrary_result

    with patch("jsonpatchx.standard.JsonPatch", return_value=mock_patch) as mock_class:
        result = apply_patch(arbitrary_doc, arbitrary_patch, inplace=True)

    mock_class.assert_called_once_with(arbitrary_patch)
    mock_patch.apply.assert_called_once_with(arbitrary_doc, inplace=True)
    assert result is arbitrary_result
