# Plan: TLS Certificate Adaptor Operator

ADR: [docs/specs/2026-04-09-tls-certificate-adaptor/decision.md](../../specs/2026-04-09-tls-certificate-adaptor/decision.md)
Spec: [docs/specs/2026-04-09-tls-certificate-adaptor/spec.md](../../specs/2026-04-09-tls-certificate-adaptor/spec.md)

## PRs

- [ ] PR 001 — Foundation and old-interface parsing: tasks 001, 002, 003, 004
- [ ] PR 002 — CSR generation and upstream forwarding: tasks 001, 002, 003, 004, 005
- [ ] PR 003 — Certificate delivery: tasks 001, 002, 003
- [ ] PR 004 — Renewal and cleanup: tasks 001, 002, 003

## Task checklist

- [ ] `001-foundation/001-project-setup` — Add dependency, create `constants.py`, rename charm class
- [ ] `001-foundation/002-certificate-provider-read` — Create `certificate_provider.py` with old-interface read logic
- [ ] `001-foundation/003-state-model` — Create `state.py` with `CertificateRequest`, `IssuedCertificate`, `CharmState`
- [ ] `001-foundation/004-wire-charm-events` — Observe old-interface relation events in `charm.py`, set unit status
- [ ] `002-csr-forwarding/001-crypto-helpers` — RSA key generation and CSR building utilities
- [ ] `002-csr-forwarding/002-secret-mapping` — Create, look up, and revoke per-CSR Juju Secrets
- [ ] `002-csr-forwarding/003-wire-relation-changed` — Handle `certificates_relation_changed`
- [ ] `002-csr-forwarding/004-wire-upstream-joined` — Handle `certificates_upstream_relation_joined`
- [ ] `002-csr-forwarding/005-unit-tests` — Unit tests for CSR forwarding
- [ ] `003-certificate-delivery/001-certificate-provider-write` — Write cert + key + CA to old-interface relation data
- [ ] `003-certificate-delivery/002-certificate-available-handler` — Handle `certificate_available` event
- [ ] `003-certificate-delivery/003-unit-tests` — Unit tests for end-to-end certificate delivery
- [ ] `004-renewal-and-cleanup/001-renewal-handlers` — Handle `certificate_expiring` and `certificate_invalidated`
- [ ] `004-renewal-and-cleanup/002-relation-broken` — Handle `certificates_relation_broken`
- [ ] `004-renewal-and-cleanup/003-unit-tests` — Unit tests for renewal and cleanup
