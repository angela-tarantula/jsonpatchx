# Developer Overview

This section is for contributors and advanced integrators.

The User Guide explains when to adopt JsonPatchX and how to build PATCH
endpoints with it. The pages here explain the constraints and extension points
that shape the library itself.

## What Matters in the Internals

JsonPatchX has a few design choices that are easy to miss if you only read the
user-facing examples:

- the RFC 6902 core is meant to stay easy to reach
- the contract layer is a first-class API surface, not decoration around a patch
  engine
- pointer semantics are intentionally extensible
- richer PATCH behavior should stay explicit, typed, and testable
- failure behavior matters as much as success behavior

Those choices are why the library is organized the way it is.

## How to read this section

Read these pages when you are:

- implementing a custom pointer backend
- debugging typing behavior around registries, pointers, or JSON helper types

If you are just trying to build a PATCH route, stay in the User Guide.
