# 003. Simplify OldTLSCertificatesRelation

## What

Remove all CSR-fingerprint and mapping-secret logic from `OldTLSCertificatesRelation`, leaving
only the request-parsing and certificate-writing methods.

## How

**`src/old_tls_certificate.py`**:

- Remove `private_key_pem` parameter and `self._private_key_pem` attribute from `__init__`.
- Delete methods: `get_csr_fingerprints`, `process_relation`, `write_csr_fingerprints`,
  `revoke_csr_mappings`.
- Remove imports that are now unused: `build_csr`, `csr_sha256_hex` from `crypto`;
  `get_csr_mapping`, `revoke_csr_mapping_by_fingerprint`, `store_csr_mapping` from `secret`;
  `CSR_FINGERPRINTS_KEY` from `constants`.
- Keep all remaining methods unchanged: `get_certificate_requests`, `write_certificate`,
  `write_client_cert`, `write_ca`, `_parse_legacy_request`, `_parse_batch_requests`.

**`src/state.py`**:

- Remove `csr_fingerprints` field from `CharmState`.
- In `CharmState.from_charm`: remove the `get_csr_fingerprints(...)` call and the
  `csr_fingerprints=` keyword argument from the `cls(...)` call.

Run unit tests:

```bash
tox -e unit -- tests/unit/test_old_tls_certificate.py tests/unit/test_state.py -x
```

## Notes

- `write_certificate` and `write_client_cert` keep their `key` parameter unchanged — the caller
  will pass `str(self._tls.private_key)` (wired up in task 004).

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
