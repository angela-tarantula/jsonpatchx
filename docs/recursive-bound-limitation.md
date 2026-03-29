# Recursive Bound Limitation

`JSONBound` uses `Any` in container branches as a pragmatic approximation for a
recursive existential bound that Python typing cannot express today.

Consequence: static checkers may miss some non-JSON element misuse inside
invariant containers.

Example of runtime-built typing pressure point:

```python
from typing import Union

ops = [AddOp, RemoveOp, ReplaceOp]  # loaded from config/env/feature flags
Registry = Union[tuple(ops)]  # type: ignore[misc]
```

In advanced runtime-type construction like this, local `# type: ignore` usage
may be necessary because static analysis cannot fully resolve dynamic typeforms.
