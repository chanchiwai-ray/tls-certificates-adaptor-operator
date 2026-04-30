# 002. Handle `certificate_available` event

## What

Implement the `_on_certificate_available` handler in `src/charm.py`. When charmlibs fires `certificate_available` (carrying the signed certificate, CA, chain, and the original CSR), the handler: computes the CSR fingerprint, calls `get_csr_mapping()` to retrieve the private key, requirer unit, and relation ID, calls `write_certificate()` to deliver cert + key + CA to the old-interface requirer's relation databag, then calls `revoke_csr_mapping()` to clean up the mapping secret. Call `reconcile()` at the end.

## Why

This is the certificate delivery step — the observable end-to-end outcome of the adaptor: old-interface requesters receive their signed certificates and private keys (spec: Events Handled — `certificate_available`; ADR-2: Decision).

## Acceptance Criteria

- [x] After `certificate_available`, the old-interface requirer's unit databag contains `{unit}_0.processed_requests` with the correct cert and key.
- [x] The mapping Juju Secret is revoked after successful delivery.
- [x] If the mapping secret is not found (e.g. after unexpected restart), the event is logged at ERROR and skipped gracefully — the charm does not crash.
- [x] Unit tests cover: happy path → cert delivered + secret revoked; missing mapping secret → graceful error log.

## Files

- `src/charm.py` — add `_on_certificate_available` handler; observe `TLSCertificatesRequiresV4.on.certificate_available`
- `tests/unit/test_charm.py` — add tests for delivery handler

## Notes

- The charmlibs `certificate_available` event object exposes `.certificate` (PEM), `.ca` (PEM), `.chain` (list), and `.certificate_signing_request` (PEM).
- Map `certificate_signing_request` → fingerprint → look up mapping secret.
- The old-interface relation may have been broken between CSR submission and delivery. Check that `self.model.get_relation(OLD_INTERFACE_RELATION_NAME, relation_id)` is not `None` before writing; if gone, just revoke the secret and log at INFO.
- `TLSCertificatesRequiresV4.on.certificate_available` must be observed in `__init__`; use `self.certificates_requires.on.certificate_available` (where `certificates_requires` is the library instance stored on `self`).

## Work items

- [x] Code changes
- [x] Local testing
- [x] Commit changes
