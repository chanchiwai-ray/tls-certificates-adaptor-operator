---
title: Fix old-interface (v1) relation data protocol
status: In Progress
date: 2026-05-04
---

# Plan: Fix old-interface (v1) relation data protocol

**Spec**: `docs/design/2026-05-04-old-interface-protocol-fix/specification.md`

**ADRs**:

- `docs/design/2026-05-04-old-interface-protocol-fix/001-decision.md`

## PRs

- [ ] PR 001 — Fix old-interface protocol: tasks 001, 002, 003, 004, 005

## Task checklist

- [ ] `001-protocol-fix/001-extend-certificate-request-model` — Add `is_legacy: bool` field to `CertificateRequest`
- [ ] `001-protocol-fix/002-fix-get-certificate-requests` — Parse batch (dict) and legacy (direct-key) request formats
- [ ] `001-protocol-fix/003-fix-write-certificate-and-add-write-ca` — Write correct response keys per format; add `write_ca()`
- [ ] `001-protocol-fix/004-wire-is-legacy-through-charm` — Store `is-legacy` in mapping secret; call `write_ca()` on cert available
- [ ] `001-protocol-fix/005-unit-tests` — Unit tests for all new and fixed behaviour
