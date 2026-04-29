# 003. Handle `certificates_relation_changed`

## What

Implement the `_on_certificates_relation_changed` handler in `src/charm.py`. For each `CertificateRequest` in the updated state that does not yet have a corresponding CSR mapping secret, the handler: generates an RSA private key, builds a CSR, stores the CSR→requirer mapping secret, then initialises `TLSCertificatesRequiresV4` with all pending CSRs as `CertificateRequestAttributes` so the charmlibs library sends them to the upstream provider. Call `reconcile()` at the end to update unit status.

## Why

This is the core ingress path: translates old-interface cert requests into new-interface CSR submissions (spec: Events Handled — `certificates_relation_changed`).

## Acceptance Criteria

- [x] A new `CertificateRequest` from an old-interface requirer results in a Juju Secret being created with the correct label and content.
- [x] The CSR is sent to the upstream provider (the charmlibs library databag is updated).
- [x] Re-triggering the event for the same request is idempotent (no duplicate secrets or CSRs).
- [x] Requests with `cert_type != "server"` are silently skipped (logged at WARNING).
- [x] Unit tests cover: new request → secret created + CSR sent; repeated event → idempotent; non-server type → skipped.

## Files

- `src/charm.py` — add handler and `TLSCertificatesRequiresV4` initialisation
- `tests/unit/test_charm.py` — add tests for `_on_certificates_relation_changed`

## Notes

- `TLSCertificatesRequiresV4` is initialised once in `__init__` with the list of `CertificateRequestAttributes` generated from the current `CharmState`. Refer to the charmlibs API for the exact constructor signature.
- Idempotency check: before generating a new key+CSR, check whether `get_csr_mapping()` already returns a valid entry for the same `(common_name, sans)` tuple.
- `TLSCertificatesRequiresV4` requires the relation name passed as the first argument; use `UPSTREAM_RELATION_NAME`.
