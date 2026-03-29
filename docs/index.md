# JsonPatchX

Typed JSON Patch for governed APIs.

JsonPatchX supports three common adoption paths without forcing one style:

## Choose Your Path

### Plain JSON Patching

- Use `apply_patch(...)` or `JsonPatch(...)`
- No FastAPI dependency
- Best for scripts, services, and internal patch workflows

Start here: [Patching Plain JSON](patching-plain-json.md)

### RFC-First FastAPI Integration

- Keep RFC 6902 operations
- Use `JsonPatchFor[Model, Registry]` request contracts
- Generate OpenAPI patch schemas from runtime models

Start here: [FastAPI Integration](fastapi-integration.md)

### Governed Expressive PATCH APIs

- Route-level allow-lists with registries
- Custom operations and pointer-aware constraints
- Strongly typed operation contracts

Start here: [Operation Registries](operation-registries.md)

## Docs Tracks

- User Guide: practical usage and API construction
- Developer Reference: internals, architecture, constraints
- API Reference: generated source-level reference
