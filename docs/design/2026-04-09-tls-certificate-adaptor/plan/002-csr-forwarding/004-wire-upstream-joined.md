# 004. Handle `certificates_upstream_relation_joined`

## What

Implement the `_on_certificates_upstream_relation_joined` handler in `src/charm.py`. When the upstream TLS provider (re-)joins the relation, re-initialise `TLSCertificatesRequiresV4` with all CSRs currently stored in the adaptor's Juju Secrets (i.e. all outstanding mapping secrets). This ensures pending certificate requests are re-sent after a provider replacement or charm restart.

## Why

Provides idempotent recovery when the upstream provider disconnects and reconnects — a common scenario during vault-k8s or lego-k8s upgrades (spec: Events Handled — `certificates_upstream_relation_joined`).

## Acceptance Criteria

- [x] After the upstream relation joins, all pending CSRs (those with an existing mapping secret) are present in the new-interface relation data.
- [x] No duplicate CSRs are created if a CSR was already present.
- [x] Unit tests cover: re-join with one pending CSR → CSR re-sent; re-join with no pending CSRs → no-op.

## Files

- `src/charm.py` — add `_on_certificates_upstream_relation_joined` handler
- `tests/unit/test_charm.py` — add corresponding tests

## Notes

- To enumerate all outstanding mapping secrets, use `charm.model.get_secrets(label_prefix=JUJU_SECRET_LABEL_PREFIX)` if the ops API supports prefix queries, or maintain a list of active CSR fingerprints in a separate unit-owned secret or peer data. Investigate the ops secrets API before implementing.
- An alternative: scan all unit-owned Juju Secrets whose labels start with `JUJU_SECRET_LABEL_PREFIX` using `charm.model.get_secret(label=...)` in a loop with the known fingerprints (since the state already tracks all active `CertificateRequest` objects).
- Call `reconcile()` at the end of the handler.
