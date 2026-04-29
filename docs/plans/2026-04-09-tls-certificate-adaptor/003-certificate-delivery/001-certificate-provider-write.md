# 001. Write cert + key + CA to old-interface relation data

## What

Add a `write_certificate(relation, unit_name, cert, key, ca) -> None` function to `src/certificate_provider.py`. It writes the signed certificate, private key, and CA certificate into the adaptor's **unit** databag for the given relation using the old reactive `tls-certificates` format: key `{munged_unit_name}.processed_requests` with a JSON-serialised list of certificate objects as specified in the spec.

## Why

Separates old-interface relation data serialisation from the event handler, keeping `charm.py` free of raw relation data writes and making the format testable in isolation (spec: Old-Interface Relation Data Format; design-pattern instructions: separation of concerns).

## Acceptance Criteria

- [ ] `write_certificate()` writes the correct key (`{unit_name_with_slashes_replaced}.processed_requests`) to the unit databag.
- [ ] The value is a JSON list containing a single object with keys `cert_type`, `common_name`, `cert`, and `key`.
- [ ] Calling `write_certificate()` twice for the same unit overwrites (not appends) the entry.
- [ ] Unit tests verify the databag content using `ops[testing]`.

## Files

- `src/certificate_provider.py` — add `write_certificate()` function
- `tests/unit/test_certificate_provider.py` — add write-path tests

## Notes

- Unit name munging: `unit_name.replace("/", "_")` (e.g. `keystone/0` → `keystone_0`).
- The `cert_type` field in the output must be `"server"` (only server certs are in scope for this version).
- `common_name` in the output should match what the requirer originally requested.
- CA chain is not part of the old interface format per the reference implementation (R4, R5 in spec) — omit `chain` from the output unless confirmed otherwise.

## Work items

- [ ] Code changes
- [ ] Local testing
- [ ] Commit changes
