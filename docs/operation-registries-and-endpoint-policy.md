# Registries and Endpoint Policy

Once PATCH becomes a contract, the next question is governance:

Which operations should this route accept?

That is what registries are for.

A registry is a union of operation models. If an operation is not part of the
registry bound to the route, the request is rejected before apply-time.

## The same resource can expose different mutation vocabularies

```python
from jsonpatchx import AddOp, JsonPatchFor, RemoveOp, ReplaceOp, StandardRegistry

type PublicUserOps = AddOp | RemoveOp | ReplaceOp
type InternalUserOps = StandardRegistry | IncrementQuotaOp

PublicUserPatch = JsonPatchFor[User, PublicUserOps]
InternalUserPatch = JsonPatchFor[User, InternalUserOps]
```

```python
@app.patch("/public/users/{user_id}")
def patch_public_user(user_id: int, patch: PublicUserPatch) -> User:
    ...


@app.patch("/internal/users/{user_id}")
def patch_internal_user(user_id: int, patch: InternalUserPatch) -> User:
    ...
```

Both routes patch the same target model.

They do not expose the same mutation vocabulary.

That distinction is one of the main reasons JsonPatchX exists.

## Why govern the mutation surface

Without registries, PATCH often turns into an all-or-nothing shape:

- either you accept free-form patch documents
- or you stop using PATCH for anything sensitive

Registries give you a middle ground.

You can keep the PATCH transport model while still saying:

- browser clients may use a small RFC subset
- internal tools may use the full RFC plus admin-only operations
- partner APIs may get a different, slower-moving contract
- beta operations may exist on one route before they exist anywhere else

That is not just “control which mutations are allowed.” It is route design.

## Parse-time rejection matters

A disallowed operation fails during request parsing, before mutation runs.

That is important for two reasons.

First, policy failures should not depend on current resource state. Whether a
client is allowed to send `increment_quota` is an endpoint rule, not a property
of the document being patched.

Second, OpenAPI can stay honest. When the registry changes, the route’s request
schema changes with it. The docs do not have to hand-wave about “supported ops”
in prose.

## A practical way to think about registries

Treat a registry like an endpoint-specific mutation vocabulary.

It should be shaped by:

- trust boundary
- client type
- rollout stage
- audit and support burden
- the actual semantics you are prepared to own long-term

That framing keeps registries grounded. They are not abstract allow-lists. They
are part of the public meaning of the route.
