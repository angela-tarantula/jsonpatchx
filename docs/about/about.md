# About

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) JSON Patch was
designed to be primitive and transport-focused. That is great for
interoperability, but modern patching often needs more structure.

JsonPatchX builds that structure on top of standard JSON Patch with
[Pydantic](https://pydantic.dev/docs/validation/latest/get-started/)-backed
operation models. The same models can validate patch documents, power
[FastAPI](https://fastapi.tiangolo.com/) PATCH routes, generate
[OpenAPI](https://www.openapis.org/), and serve as typed patch toolkits for
PATCH clients and coding agents.

## Standard JSON Patch in Python

Use JsonPatchX as a standards-compliant RFC 6902 implementation for parsing,
validating, and applying ordinary JSON Patch documents in Python.

## Governed PATCH APIs

When PATCH becomes a real API contract, you often need richer operations,
accurate OpenAPI, per-endpoint control over what updates are allowed, and a
deliberate way to evolve over time.

JsonPatchX gives you:

- Payload validation
- Custom operations
- Typed JSON Pointer and JSONPath targeting
- OpenAPI generated from the same models
- Endpoint controls over accepted operations

## Agentic Patching

Coding agents want to write Python, not raw RFC 6902 payloads. Use JsonPatchX to
publish reviewed patch operations as typed Python models and OpenAPI schemas so
agents can discover and compose higher-level mutations.

## Why Not Merge Patch

[JSON Merge Patch](https://datatracker.ietf.org/doc/html/rfc7386) is simpler and
is often the right choice for coarse object updates. JsonPatchX is for cases
where named operation semantics, array handling, richer targeting, or explicit
mutation policy matter.

## Now Is the Time to Experiment

JsonPatchX is designed as a safe experimentation surface: teams can introduce
richer operations, compare patterns in production, and let the best designs win.

With JSONPath now standardized in
[RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535), this is a good moment
to explore more expressive targeting and contract models that fit real domains.

To shape what comes next, join the broader
[json-patch2](https://github.com/json-patch/json-patch2) forum and
[JsonPatchX Discussions](https://github.com/angela-tarantula/jsonpatchx/discussions).
