# RFC 6901 Compliance Notes

`JsonPatchX` tests `JSONPointer` here as a sanity check against RFC 6901.

Many pointer implementations are surprisingly incomplete in edge cases. One
example is this still-open fix in `python-json-pointer`:
[stefankoegl/python-json-pointer#76](https://github.com/stefankoegl/python-json-pointer/pull/76).
Some implementations are intentionally loose. For example, they may permit
negative indices into arrays.

These tests show that `JsonPatchX` does its due diligence to provide an accurate
RFC 6901 implementation. Users can always swap the default RFC 6901 pointer with
their preferred implementation.
