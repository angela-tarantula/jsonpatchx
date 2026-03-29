# Developer Reference

This section is for maintainers and advanced adopters working on internals,
extension points, and implementation constraints.

## Architecture Overview

```mermaid
flowchart TD
    A["PATCH request"] --> B["JsonPatchFor[Model, Registry] validation"]
    B --> C["Registry discriminator (op) resolution"]
    C --> D["OperationSchema.apply loop (_apply_ops)"]
    D --> E["Pointer backend get/add/remove"]
    E --> F["Patched JSON document"]
    F --> G["Model revalidation / response serialization"]
```

Start with:

- [Local Docs Preview](developer-docs-preview.md)
- [Pointer Backends](pointer-backends.md)
- [Recursive Bound Limitation](recursive-bound-limitation.md)
