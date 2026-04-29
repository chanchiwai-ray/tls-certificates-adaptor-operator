# 001. RSA key generation and CSR building utilities

## What

Add crypto utility functions to `src/certificate_provider.py` (or a new `src/crypto.py` if the file grows large): `generate_private_key() -> str` (returns PEM-encoded 2048-bit RSA key) and `build_csr(private_key_pem: str, common_name: str, sans: list[str]) -> str` (returns PEM-encoded CSR). Also add `csr_sha256_hex(csr_pem: str) -> str` which returns the hex-encoded SHA-256 fingerprint of the DER-encoded CSR, used as the Juju Secret label suffix.

## Why

These are the cryptographic primitives the adaptor needs to generate a key + CSR on behalf of each old-interface requirer (spec: Events Handled — `certificates_relation_changed`; ADR-1). Isolating them simplifies unit testing.

## Acceptance Criteria

- [x] `generate_private_key()` returns a valid PEM RSA private key of at least 2048 bits.
- [x] `build_csr(key_pem, common_name, sans)` returns a valid PEM CSR with the correct CN and SAN extension.
- [x] `csr_sha256_hex(csr_pem)` returns the lowercase hex SHA-256 fingerprint of the CSR.
- [x] Unit tests verify the above using `cryptography` library introspection (not just string checks).

## Files

- `src/certificate_provider.py` — add crypto utilities (or create `src/crypto.py`)
- `tests/unit/test_crypto.py` (or `test_certificate_provider.py`) — new/updated unit tests

## Notes

- Use the `cryptography` Python package (`cryptography.hazmat.primitives.asymmetric.rsa`, `cryptography.x509`). This is a transitive dependency of `charmlibs-interfaces-tls-certificates`.
- RSA key size: 2048-bit minimum per spec (ADR-1: Consequences).
- SANs should be added as `x509.DNSName` entries in the CSR's `SubjectAlternativeName` extension.
