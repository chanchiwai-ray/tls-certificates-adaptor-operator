# 001. Update unit tests

## What

Update the full unit test suite to match the simplified charm: delete `test_secret.py`, remove
deleted-function tests from `test_crypto.py` and `test_old_tls_certificate.py`, and rewrite
`test_new_tls_certificate.py` and `test_charm.py` to reflect the new stateless routing logic.

## How

**`tests/unit/test_secret.py`** — delete entirely.

**`tests/unit/test_crypto.py`**:
- Delete tests for `generate_private_key`, `build_csr`, `csr_sha256_hex`.
- Keep tests for `classify_sans` and `build_ca_bundle`.

**`tests/unit/test_state.py`**:
- Remove any assertions on `csr_fingerprints`.

**`tests/unit/test_old_tls_certificate.py`**:
- Remove `private_key_pem` from all `OldTLSCertificatesRelation(...)` constructor calls.
- Delete tests for `get_csr_fingerprints`, `process_relation`, `write_csr_fingerprints`,
  `revoke_csr_mappings`.
- Keep all tests for `get_certificate_requests`, `write_certificate`, `write_client_cert`,
  `write_ca`.

**`tests/unit/test_new_tls_certificate.py`**:
- Remove `private_key_pem` and `certificate_requests` from constructor calls.
- Mock `_tls.private_key` where needed.
- Add tests for `update_certificate_requests`: assert `_tls.certificate_requests` is set and
  `_tls.sync()` is called.
- Rewrite `handle_certificate_available` tests: set up live old-interface relation data so
  `get_certificate_requests()` returns a matching `CertificateRequest`; assert
  `write_certificate` / `write_client_cert` is called with correct args.
- Delete tests for `handle_certificate_denied` and `get_issued_certificates`.

**`tests/unit/test_charm.py`**:
- Remove `_on_certificate_denied` tests.
- Remove secret-count assertions (no charm-owned secrets exist).
- Update `reconcile` CA-bundle tests to mock `get_provider_certificates()` directly.
- Assert `_on_certificate_available` sets `ActiveStatus` without calling `reconcile()`.
- Assert `_on_certificates_relation_broken` only calls `reconcile()` (no secret cleanup).

Run the full suite and verify all tests pass with no warnings:

```bash
tox -e unit
```

## Notes

- Use `ops.testing.Harness` throughout; the library's `private_key` property returns `None`
  in the harness — test `"key" in payload` rather than the PEM value.
- Aim to keep or exceed the existing 96% coverage.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
