---
title: Remove private key management from upstream TLS certificates relation
status: In Progress
date: 2026-05-11
---

# Plan: Remove Private Key Management from Upstream TLS Certificates Relation

**Spec**: `docs/design/2026-05-11_remove-private-key-tls-relation/specification.md`

**ADRs**:
- `docs/design/2026-05-11_remove-private-key-tls-relation/01-decision.md`

## PRs

- [x] PR 001 — Simplify charm and update tests: tasks 001, 002, 003, 004, 005, 006 (reviewed)

## Task checklist

- [x] `001-simplify-charm/001-strip-constants-and-crypto` — Remove unused constants and crypto helpers (generate_private_key, build_csr, csr_sha256_hex)
- [x] `001-simplify-charm/002-delete-secret-py` — Delete secret.py and IssuedCertificate dataclass entirely
- [x] `001-simplify-charm/003-simplify-old-tls-relation` — Remove process_relation, write_csr_fingerprints, revoke_csr_mappings, get_csr_fingerprints and csr_fingerprints from CharmState
- [x] `001-simplify-charm/004-rewrite-new-tls-relation` — Add update_certificate_requests; rewrite handle_certificate_available to re-derive routing from live relation data; delete handle_certificate_denied and get_issued_certificates
- [x] `001-simplify-charm/005-simplify-charm-py` — Remove private key wiring, certificate_denied handler, process_relation loop; wire update_certificate_requests; simplify relation_broken handler
- [x] `001-simplify-charm/006-update-unit-tests` — Delete test_secret.py; remove deleted-function tests; rewrite test_new_tls_certificate.py and test_charm.py to match new stateless design
