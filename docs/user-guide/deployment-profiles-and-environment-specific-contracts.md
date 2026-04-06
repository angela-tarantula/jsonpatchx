# Deployment Profiles and Environment-Specific Contracts

Different environments rarely need the same PATCH contract on day one.

A public production route may need a very small mutation vocabulary. A dev
deployment may need extra repair operations. An internal admin service may need
a broader contract behind stronger authentication.

That is a real rollout story.

The safest place to make those choices is at startup, not as a hidden
per-request toggle.

## Pick a named profile at startup

A practical pattern is to define named profiles and build the route registry
from configuration.

```python
import os
from functools import reduce
from operator import or_

from jsonpatchx import AddOp, RemoveOp, ReplaceOp, TestOp, JsonPatchFor


AVAILABLE_OPS = {
    "add": AddOp,
    "remove": RemoveOp,
    "replace": ReplaceOp,
    "test": TestOp,
    "swap": SwapOp,
    "increment": IncrementOp,
}

PATCH_PROFILES = {
    "public": ["add", "replace"],
    "internal": ["add", "remove", "replace", "test"],
    "dev": ["add", "remove", "replace", "test", "swap"],
    "billing_admin": ["add", "remove", "replace", "increment"],
    "alpha_partner": ["add", "replace", "increment"],
}


def build_registry(names: list[str]):
    ops = [AVAILABLE_OPS[name] for name in names]
    if not ops:
        raise ValueError("registry cannot be empty")
    return reduce(or_, ops[1:], ops[0])


profile_name = os.environ.get("USER_PATCH_PROFILE", "public")
UserPatchRegistry = build_registry(PATCH_PROFILES[profile_name])

UserPatch = JsonPatchFor[User, UserPatchRegistry]
```

The source of the profile can be an environment variable, a settings file, a
deployment manifest, or another startup-time configuration source. The important
part is that the route contract is chosen before the app starts serving traffic.

## This is what rollout means here

“Rollout” is a reasonable term for this.

In practice it means exposing a contract gradually: first in dev, then in an
internal deployment, then maybe to an alpha partner, and only later on a public
route.

That is a much better fit for PATCH contracts than changing accepted operations
mid-flight on a live route.

## Why startup-time selection is the sane default

OpenAPI should describe what a route actually accepts.

If the allowed operation set changes behind a runtime flag after the app is
already running, the docs and the actual request model can drift apart. That is
a bad place to be for PATCH.

Choose the profile at startup. Then the route model, the OpenAPI schema, and the
actual accepted operations all line up.

If different environments need different contracts, ship different startup
profiles or separate deployments.

## Least privilege belongs here too

Named profiles make least privilege easy to apply.

Typical examples:

- `public` for browser-facing routes
- `internal` for staff tooling
- `dev` for experiments and repair operations
- `billing_admin` or `superuser` for elevated routes
- `alpha_partner` for narrow early rollouts

A wider registry should usually come with stronger auth and tighter operational
ownership.

Keep those ideas separate, but let them reinforce each other.

## Avoid per-request mutation negotiation

Try not to let each request negotiate its own operation set.

That makes the contract hard to document, hard to test, and hard to support.

Named profiles are much easier to reason about:

- they can be documented
- they can be snapshot-tested
- they can be rolled out deliberately
- they can be mapped to real trust boundaries

That is the level where contract rollout belongs.

## Publish honest docs for materially different contracts

If `public` and `internal` deployments expose meaningfully different PATCH
contracts, do not pretend one OpenAPI document covers both.

Publish separate OpenAPI snapshots, separate deployments, or clearly separated
endpoints.

PATCH contracts are request models. They deserve the same honesty as any other
part of your API surface.
