# Registries and Endpoint Policy

`JsonPatchFor[Target]` is the friendly default.

`JsonPatchFor[Target, Registry]` is how you turn endpoint policy into part of
the contract.

A registry is the set of operation models a route is willing to accept. If an
operation is not in the registry, the request fails during validation before any
mutation runs.

## The default is the standard RFC set

By default:

```python
UserPatch = JsonPatchFor[User]
```

means the same thing as:

```python
from jsonpatchx import StandardRegistry

UserPatch = JsonPatchFor[User, StandardRegistry]
```

That is a good default. It is not always the right public contract.

## Different routes often need different mutation vocabularies

Even if you stay entirely inside RFC 6902, policy still matters.

```python
from jsonpatchx import AddOp, RemoveOp, ReplaceOp, TestOp, JsonPatchFor


PublicUserOps = AddOp | ReplaceOp
InternalUserOps = AddOp | RemoveOp | ReplaceOp | TestOp

PublicUserPatch = JsonPatchFor[User, PublicUserOps]
InternalUserPatch = JsonPatchFor[User, InternalUserOps]
```

Those two routes may patch the same target model.

They should not automatically advertise the same things.

A public profile-editing route may allow `add` and `replace`, but intentionally
reject `remove` and `test`. An internal repair endpoint may accept the wider
set.

## This is about route meaning, not only allow-lists

Registries are useful because they answer a design question that plain JSON
Patch leaves vague:

What does this endpoint actually support?

A few common reasons to narrow or widen a registry:

- a browser-facing route should stay small and stable
- an internal tool needs stronger repair operations
- a partner integration gets a slower-moving contract than your own admin UI
- a dev-only or superuser route needs extra operations behind stronger auth
- a new operation is being tried internally before it becomes public

That is route design, not just validation.

## `test` is a good example of why policy matters

Imagine a public route where your backend already protects sensitive fields and
rejects invalid state changes.

That still does not mean every RFC operation is harmless to expose.

`test` can let a client probe for values they should not be able to ask about
directly. A payload such as “is `/billing/plan` equal to `enterprise`?” may not
mutate anything, but it can still reveal something through PATCH that the route
never meant to reveal.

That is a good reason to exclude `test` from a public registry even if your data
model is otherwise safe.

## Least privilege applies to PATCH too

Registries are a practical way to apply least privilege to mutation surfaces.

Good patterns include:

- a narrow public registry
- a broader internal registry
- a dev-only registry for experiments
- a superuser route with elevated auth and a wider registry

Keep authentication and registry policy separate in your design.

Authentication answers “who can call this route?”

The registry answers “what does this route accept?”

You usually need both.

## Custom operations plug into the same mechanism

Once you define a custom operation, you still do not have to expose it
everywhere.

```python
BillingAdminOps = StandardRegistry | IncrementOp
BillingAdminPatch = JsonPatchFor[BillingAccount, BillingAdminOps]
```

That is the same mechanism as before. The route either advertises `increment` or
it does not.

The next page is about what makes a custom operation worth introducing in the
first place.
