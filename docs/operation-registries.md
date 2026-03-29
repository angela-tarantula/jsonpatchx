# Operation Registries

Registries are the operational allow-list for JsonPatchX. A registry is a union
of operation models, and only operations in that union are accepted.

```python
from jsonpatchx import StandardRegistry

type Registry = StandardRegistry | IncrementByOp | ToggleOp
```

This page covers:

- static registries (`StandardRegistry | CustomOp`)
- runtime-derived registries (feature flags, config files, env-driven)
- validation and failure behavior when an op is not in the registry
- practical patterns for per-route and per-domain registries
