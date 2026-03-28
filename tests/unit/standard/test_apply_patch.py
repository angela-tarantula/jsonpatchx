from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from jsonpatchx import apply_patch
from jsonpatchx.exceptions import PatchValidationError


def test_apply_patch_is_thin_wrapper_over_jsonpatch_apply() -> None:
    """Verify delegation contract only; JsonPatch.apply behavior is tested in integration/compliance tests."""
    arbitrary_doc: Any = object()
    arbitrary_patch: Any = object()
    arbitrary_result: Any = object()
    arbitrary_registry: Any = object()
    arbitrary_inplace: Any = object()

    mock_patch = MagicMock()
    mock_patch.apply.return_value = arbitrary_result

    with patch("jsonpatchx.standard.JsonPatch", return_value=mock_patch) as mock_class:
        result = apply_patch(
            arbitrary_doc,
            arbitrary_patch,
            registry=arbitrary_registry,
            inplace=arbitrary_inplace,
        )

    mock_class.assert_called_once_with(arbitrary_patch, registry=arbitrary_registry)
    mock_patch.apply.assert_called_once_with(arbitrary_doc, inplace=arbitrary_inplace)
    assert result is arbitrary_result


def test_apply_patch_rejects_non_jsonvalue_doc() -> None:
    with pytest.raises(PatchValidationError, match="Invalid JSON document"):
        apply_patch(object(), [])
