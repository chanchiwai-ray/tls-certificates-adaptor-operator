# 001. Handle `certificate_expiring` and `certificate_invalidated`

## What

Implement `_on_certificate_expiring` and `_on_certificate_invalidated` handlers in `src/charm.py`. Both handlers follow the same logic: look up the existing mapping secret for the expiring/invalidated CSR fingerprint to retrieve the original requirer unit and relation ID; generate a new RSA private key and CSR; store a new mapping secret for the new CSR fingerprint; re-submit the CSR to the upstream provider by reinitialising `TLSCertificatesRequiresV4`; revoke the old mapping secret.

## Why

Ensures certificates are automatically renewed when the upstream provider signals expiry or invalidation, without requiring operator intervention (spec: Events Handled — `certificate_expiring` / `certificate_invalidated`; Certificate Renewal Flow diagram).

## Acceptance Criteria

- [x] On `certificate_expiring`: a new key + CSR is generated, a new mapping secret is stored, the CSR is re-submitted to upstream, and the old mapping secret is revoked.
- [x] On `certificate_invalidated`: same behaviour as `certificate_expiring`.
- [x] If the old mapping secret is not found (e.g. already revoked), log at WARNING and skip — do not crash.
- [x] Unit tests cover: expiry → new CSR submitted + old secret revoked; invalidation → same; missing old secret → warning logged.

## Files

- `src/charm.py` — add `_on_certificate_expiring` and `_on_certificate_invalidated`; observe the corresponding charmlibs events in `__init__`
- `tests/unit/test_charm.py` — add renewal tests

## Notes

- The charmlibs `certificate_expiring` event object exposes the expiring `certificate_signing_request` (PEM) — use it to look up the existing mapping.
- `certificate_invalidated` similarly exposes the invalidated CSR.
- Both events are available on `self.certificates_requires.on.certificate_expiring` and `.certificate_invalidated`.
- After re-submitting the CSR, the charm must wait for a new `certificate_available` event before updating the old-interface requirer — do not clear the requirer's relation data during renewal.

## Work items

- [ ] Code changes
- [ ] Local testing
- [ ] Commit changes
