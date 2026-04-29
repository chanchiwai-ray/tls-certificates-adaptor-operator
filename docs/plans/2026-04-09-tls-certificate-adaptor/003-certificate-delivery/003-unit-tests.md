# 003. Unit tests for end-to-end certificate delivery

## What

Write unit tests that simulate the complete happy-path flow: old requirer fires `certificates_relation_changed` → adaptor generates key + CSR + mapping secret → upstream fires `certificate_available` → adaptor delivers cert + key to old requirer's relation data + revokes mapping secret. Also test the edge case where the mapping secret is missing at delivery time.

## Why

The certificate delivery path spans the most modules (state, crypto, secret, charm, certificate_provider write). A dedicated test PR task ensures full coverage of the integration points and confirms the observable end-user outcome (spec: end-to-end happy path).

## Acceptance Criteria

- [ ] End-to-end test: simulate `certificates_relation_changed` followed by `certificate_available`; assert old-interface unit databag contains expected cert and key.
- [ ] Secret cleanup test: after delivery, assert the mapping secret no longer exists.
- [ ] Missing-secret test: assert charm does not raise; ERROR is logged.
- [ ] Stale-relation test: delivery arrives after old-interface relation is broken; assert INFO logged, secret revoked, no error.
- [ ] `tox -e unit` passes; coverage ≥ 90% for all modules touched in PR 003.

## Files

- `tests/unit/test_charm.py` — add end-to-end delivery tests
- `tests/unit/test_certificate_provider.py` — add write-path integration tests if not already present

## Notes

- Use `ops[testing]` `Context` / `Harness` to drive both events in sequence within a single test.
- Produce a self-signed cert in the test fixture using the `cryptography` library so assertions can be made on the actual PEM content.
- Keep test fixtures in a shared `conftest.py` if multiple test files reuse them.

## Work items

- [ ] Code changes
- [ ] Local testing
- [ ] Commit changes
