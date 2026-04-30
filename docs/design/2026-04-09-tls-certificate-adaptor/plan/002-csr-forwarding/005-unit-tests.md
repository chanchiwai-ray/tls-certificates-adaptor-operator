# 005. Unit tests for CSR forwarding

## What

Write comprehensive unit tests covering the end-to-end CSR forwarding flow: an old-interface requirer fires `certificates_relation_changed` → the adaptor generates a key, builds a CSR, stores a mapping secret, and sends the CSR to the upstream provider via `TLSCertificatesRequiresV4`. Also test `certificates_upstream_relation_joined` recovery and the idempotency constraint.

## Why

The CSR forwarding path involves multiple interacting components (crypto, secret storage, charmlibs library). Unit tests verify each integration point in isolation and together (spec: all event handlers in the Events Handled table).

## Acceptance Criteria

- [x] Tests mock `TLSCertificatesRequiresV4` to verify it is initialised with the correct `CertificateRequestAttributes`.
- [x] Tests use `ops[testing]` (`Harness` or `Context`) to simulate relation events.
- [x] Tests for: first request → key + CSR + secret created; second identical request → idempotent (no duplicate secret); `certificates_upstream_relation_joined` with pending CSRs → CSRs re-sent.
- [x] `tox -e unit` passes; coverage ≥ 90% for all modules touched in PR 002.

## Files

- `tests/unit/test_charm.py` — additional tests (or separate file per module if preferred)
- `tests/unit/test_certificate_provider.py` — tests for crypto helpers

## Notes

- Use `pytest` fixtures to share a pre-configured `Harness` / `Context` instance across tests.
- For secret assertions, introspect the ops testing state rather than patching the ops API directly.
- Do not test the `cryptography` library itself — test that the adaptor calls it with the right inputs and handles the PEM output correctly.
