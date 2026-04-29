# 002. Handle `certificates_relation_broken`

## What

Implement the `_on_certificates_relation_broken` handler in `src/charm.py`. When an old-interface requirer breaks the relation, the handler: iterates the `CertificateRequest` objects that were associated with that relation ID (from the now-departing relation), revokes any outstanding mapping secrets for those CSRs, and removes the corresponding CSRs from the upstream relation by reinitialising `TLSCertificatesRequiresV4` without the broken relation's requests.

## Why

Prevents orphaned mapping secrets and dangling CSRs at the upstream provider after an old-interface requirer is removed (spec: Events Handled — `certificates_relation_broken`).

## Acceptance Criteria

- [ ] All mapping secrets for the broken relation's CSRs are revoked.
- [ ] The upstream CSRs for those requests are no longer in the new-interface relation data.
- [ ] Other relations' CSRs are unaffected.
- [ ] If a mapping secret is not found for a given CSR (already cleaned up), the loop continues without error.
- [ ] Unit tests cover: one relation broken with two active CSRs → both secrets revoked, upstream CSRs removed; second relation unaffected.

## Files

- `src/charm.py` — update `_on_certificates_relation_broken` (already observed in PR 001) with full cleanup logic
- `tests/unit/test_charm.py` — add cleanup tests

## Notes

- During `relation_broken`, `event.relation` is still accessible but the remote units have already left. Use `event.relation.id` to identify which CSRs belong to this relation (from the mapping secret `relation-id` field).
- To enumerate all mapping secrets, collect all `CertificateRequest` objects from the state (excluding the broken relation's data, which may still be readable during the hook) and check which secrets reference the broken relation ID.
- After cleanup, call `reconcile()` to update unit status.

## Work items

- [ ] Code changes
- [ ] Local testing
- [ ] Commit changes
