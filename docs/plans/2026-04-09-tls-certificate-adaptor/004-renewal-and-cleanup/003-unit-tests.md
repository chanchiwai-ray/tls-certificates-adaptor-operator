# 003. Unit tests for renewal and cleanup

## What

Write unit tests covering certificate renewal (expiry and invalidation) and old-interface relation cleanup. Tests simulate: `certificate_expiring` → new CSR submitted, old secret revoked; `certificate_invalidated` → same; `certificates_relation_broken` → mapping secrets revoked, upstream CSRs removed, other relations unaffected.

## Why

Renewal and cleanup paths involve the same helpers (crypto, secret) but in different sequences and edge-case branches. Dedicated tests confirm the full renewal flow and the absence of resource leaks (spec: Certificate Renewal Flow diagram; Events Handled table).

## Acceptance Criteria

- [x] Renewal test: simulate `certificate_available` (initial delivery) → `certificate_expiring` → new `certificate_available`; assert requirer's relation data is updated with the new cert.
- [x] Invalidation test: same as expiry test but via `certificate_invalidated`.
- [x] Cleanup test: two old-interface relations active → one broken → assert only that relation's secrets revoked and upstream CSRs removed.
- [x] `tox -e unit` passes; overall project coverage ≥ 90%.

## Files

- `tests/unit/test_charm.py` — add renewal and cleanup tests
- `tests/conftest.py` — shared fixtures if not already created

## Notes

- For the full renewal test, produce two distinct self-signed certs (initial + renewed) in fixtures to assert the relation data is actually updated.
- Coverage gate: `tox -e coverage-report` must not report below 90% on any source file in `src/`.
- After all PR 004 tests pass, run `tox` (all environments) to confirm no regressions across lint, unit, and static checks.

## Work items

- [ ] Code changes
- [ ] Local testing
- [ ] Commit changes
