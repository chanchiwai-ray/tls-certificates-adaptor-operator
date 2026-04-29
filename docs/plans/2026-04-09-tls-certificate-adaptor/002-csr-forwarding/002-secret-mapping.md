# 002. Create, look up, and revoke per-CSR Juju Secrets

## What

Add three functions to `src/certificate_provider.py` (or a new `src/secret.py` per design-pattern instructions) for managing the CSR→requirer mapping secrets: `store_csr_mapping(charm, csr_pem, private_key_pem, requirer_unit, relation_id)` creates a unit-owned Juju Secret with label `tls-adaptor-{csr_sha256_hex}`; `get_csr_mapping(charm, csr_pem) -> dict` retrieves the secret payload by label; `revoke_csr_mapping(charm, csr_pem)` removes the secret.

## Why

Provides the durable, Juju-restart-safe CSR→requirer mapping described in ADR-2. These helpers keep the secret lifecycle logic isolated and reusable across event handlers.

## Acceptance Criteria

- [ ] `store_csr_mapping()` creates a Juju Secret with the correct label, content keys (`private-key`, `requirer-unit`, `relation-id`), and no grants to other applications.
- [ ] `get_csr_mapping()` returns the correct payload dict for a stored secret; raises a clear exception if not found.
- [ ] `revoke_csr_mapping()` removes the secret without error; is a no-op if the secret does not exist (idempotent).
- [ ] Unit tests use `ops.testing.Harness` (or `ops[testing]`) to verify secret creation, retrieval, and removal.

## Files

- `src/secret.py` — new file (or `src/certificate_provider.py` extended)
- `tests/unit/test_secret.py` — new file

## Notes

- Use `charm.unit.add_secret(content, label=label)` to create the secret (ops >= 3.0 API).
- Use `charm.model.get_secret(label=label)` to retrieve it.
- Secret label format: `f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}"` where `JUJU_SECRET_LABEL_PREFIX = "tls-adaptor-"`.
- The secret must **not** be granted to any other application — do not call `secret.grant()`.
- `relation-id` must be stored as a string (Juju Secret content values are strings only).
