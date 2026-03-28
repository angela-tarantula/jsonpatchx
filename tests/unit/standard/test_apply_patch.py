from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from jsonpatchx import apply_patch


def test_apply_patch_is_thin_wrapper_over_jsonpatch_apply() -> None:
    """Verify delegation contract only; JsonPatch.apply semantics are tested elsewhere."""
    arbitrary_doc: Any = object()
    arbitrary_patch: Any = object()
    arbitrary_result: Any = object()
    arbitrary_inplace: Any = object()

    mock_patch = MagicMock()
    mock_patch.apply.return_value = arbitrary_result

    with patch("jsonpatchx.standard.JsonPatch", return_value=mock_patch) as mock_class:
        result = apply_patch(arbitrary_doc, arbitrary_patch, inplace=arbitrary_inplace)

    mock_class.assert_called_once_with(arbitrary_patch)
    mock_patch.apply.assert_called_once_with(arbitrary_doc, inplace=arbitrary_inplace)
    assert result is arbitrary_result
