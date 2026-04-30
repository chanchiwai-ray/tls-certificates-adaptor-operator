# 002. Create `certificate_provider.py` with old-interface read logic

## What

Create `src/certificate_provider.py` defining the `CertificateRequest` and `IssuedCertificate` Pydantic models, plus `get_certificate_requests()` and `write_certificate()` functions. The old interface stores requests in the requirer unit's databag under the key `cert_requests` as a JSON list; each entry has at minimum `common_name`, `sans`, and `cert_type` fields. Only `server` cert type requests are returned; others are logged and skipped. `IssuedCertificate` is also defined here to keep all old-interface data models in one place and avoid circular imports with `state.py`.

## Why

Isolates all old-interface relation data parsing in one module, keeping `charm.py` and `state.py` free of raw relation data access (spec: Module Structure; design-pattern instructions: separation of concerns).

## Acceptance Criteria

- [x] `certificate_provider.py` defines `CertificateRequest` and `IssuedCertificate` Pydantic models.
- [x] `certificate_provider.py` exports `get_certificate_requests(relation: ops.Relation) -> list[CertificateRequest]`.
- [x] `certificate_provider.py` exports `write_certificate(relation, charm_unit, requirer_unit_name, common_name, cert, key, ca)` that writes the signed certificate to the provider unit databag.
- [x] Requests with `cert_type != "server"` are logged at WARNING level and excluded from the result.
- [x] Malformed or missing `cert_requests` data is handled gracefully (returns an empty list, logs at DEBUG).
- [x] Unit tests cover: valid server request, non-server request filtered out, empty/missing data, write_certificate output.

## Files

- `src/certificate_provider.py` — new file (owns `CertificateRequest`, `IssuedCertificate`, `get_certificate_requests`, `write_certificate`)
- `tests/unit/test_certificate_provider.py` — new file

## Notes

- Reference implementation: `ca_client.py` in `charm-ops-interface-tls-certificates` (R5 in spec references) for the exact key names used by old OpenStack charms.
- The key is `cert_requests` in the **requirer** unit databag; the requirer unit name is available as `relation.units` (each `ops.Unit`).
- `CertificateRequest` and `IssuedCertificate` are **defined here** (not in `state.py`) to avoid circular imports: `state.py` imports from `certificate_provider.py`, not the other way around.
- `write_certificate` writes to `{munged_unit_name}.processed_requests` key in the adaptor's own unit databag.
- Use `logging.getLogger(__name__)` per coding-style instructions.
