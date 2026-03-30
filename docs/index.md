# JsonPatchX

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) (JSON Patch) is
intentionally minimal and transport-focused. That minimalism is great for
interoperability, but modern PATCH traffic crosses trust boundaries: browser
clients, internal services, third-party integrations, and increasingly
LLM-generated patch payloads.

## JsonPatchX provides the RFC core and adds an API contract layer

- **Input safety**: patch operations are Pydantic models, so malformed payloads
  fail fast with clear, structured errors.
- **Surface control**: operations can be allow-listed per route to limit what
  clients can do.

## It also provides extensibilty beyond the RFC

- **API Meaning**: define custom patch operations (`toggle`, `increment`, etc.)
  so updates target intent, not brittle positional assumptions.
- **Typed Targeting**: operations are explicit, so pointers can participate in
  typed contracts with clear failure modes when a resolved path violates
  expected structure or type.
- **Advanced Path Selection**: choose your path strategy
  ([JSON Pointer](https://datatracker.ietf.org/doc/html/rfc6901),
  [JSONPath](https://datatracker.ietf.org/doc/html/rfc9535), or your custom
  resolver) so you can enable non-positional selection such as filtering,
  matching, or multi-target updates.

## And it treats the patch layer as a first-class contract

- **Contract Drift**: OpenAPI is generated from the same runtime patch models,
  so documentation stays aligned automatically.
- **Versioning**: evolve operation contracts over time with additive schema
  changes and deprecations.
- **FastAPI Integration**: set up PATCH routes quickly with minimal boilerplate.

## Now is the Time to Experiment

JsonPatchX is intentionally designed as a safe experimentation surface: teams
can introduce richer operations, compare patterns in production, and **let the
best designs win**. With JSONPath now standardized in
[RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535), now is the time to
explore more expressive targeting and contract models that fit your domain.

To shape what comes next, join the broader forum at
[json-patch2](https://github.com/json-patch/json-patch2) and project-specific
discussions at
[JsonPatchX Discussions](https://github.com/angela-tarantula/jsonpatchx/discussions).
