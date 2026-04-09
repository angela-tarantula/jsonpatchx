# Why JsonPatchX

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) is good at what it set
out to do. It gives you a standard document format for a sequence of patch
operations and a media type for sending them over HTTP.

That still leaves a lot of practical API design questions open.

Many teams react by avoiding PATCH, or by using
[JSON Merge Patch](https://datatracker.ietf.org/doc/html/rfc7386) when updates
are simple enough that "just send the new object shape" feels easier. That is a
reasonable trade-off a lot of the time. Merge Patch is a good fit for coarse
object updates where array handling, explicit deletions, and per-operation
semantics do not matter much.

JsonPatchX is for the cases where they do.

Those cases show up quickly in real systems. Browser clients, internal tools,
third-party integrations, and increasingly LLM-generated patches all cross trust
boundaries. At that point, a route usually needs more than "send me a list of
patch dicts and I'll try to apply them."

## Why not just use Merge Patch

Merge Patch stays attractive because it is simple to explain and simple to
generate. For some APIs, that simplicity wins.

But it comes with different trade-offs. It is much less explicit about mutation
intent. It gets awkward once arrays matter. It is not a good fit when you want
operation-level policy, extension, or stable error semantics around specific
kinds of mutations.

JsonPatchX is not trying to replace Merge Patch everywhere. It is for APIs that
want the precision of patch operations, plus a cleaner way to govern them.
