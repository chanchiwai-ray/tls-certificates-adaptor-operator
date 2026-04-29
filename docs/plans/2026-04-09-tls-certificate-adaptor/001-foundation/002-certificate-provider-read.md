# 002. Create `certificate_provider.py` with old-interface read logic

## What

Create `src/certificate_provider.py` with a function (or class) that reads unit relation data from the old reactive `tls-certificates` relation and returns a list of `CertificateRequest` objects. The old interface stores requests in the requirer unit's databag under the key `cert_requests` as a JSON list; each entry has at minimum `common_name`, `sans`, and `cert_type` fields. Only `server` cert type requests are returned; others are logged and skipped.

## Why

Isolates all old-interface relation data parsing in one module, keeping `charm.py` and `state.py` free of raw relation data access (spec: Module Structure; design-pattern instructions: separation of concerns).

## Acceptance Criteria

- [ ] `certificate_provider.py` exports a `get_certificate_requests(relation: ops.Relation) -> list[CertificateRequest]` function.
- [ ] Requests with `cert_type != "server"` are logged at WARNING level and excluded from the result.
- [ ] Malformed or missing `cert_requests` data is handled gracefully (returns an empty list, logs at DEBUG).
- [ ] Unit tests cover: valid server request, non-server request filtered out, empty/missing data.

## Files

- `src/certificate_provider.py` — new file
- `tests/unit/test_certificate_provider.py` — new file

## Notes

- Reference implementation: `ca_client.py` in `charm-ops-interface-tls-certificates` (R5 in spec references) for the exact key names used by old OpenStack charms.
- The key is `cert_requests` in the **requirer** unit databag; the requirer unit name is available as `relation.units` (each `ops.Unit`).
- `CertificateRequest` is imported from `state.py` (defined in task 003 — implement stub first or define the dataclass here and move it later).
- Use `logging.getLogger(__name__)` per coding-style instructions.
