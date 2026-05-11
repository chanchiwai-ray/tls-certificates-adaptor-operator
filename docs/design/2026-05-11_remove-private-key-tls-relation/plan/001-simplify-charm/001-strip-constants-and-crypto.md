# 001. Strip unused constants and crypto helpers

## What

Remove all constants and crypto functions that exist solely to support charm-owned private key
management and CSR fingerprinting. After this task, `constants.py` and `crypto.py` contain only
what the rest of the charm actually uses.

## How

**`src/constants.py`** — delete the following names:
- `CHARM_PRIVATE_KEY_SECRET_LABEL`
- `CSR_FINGERPRINTS_KEY`
- `JUJU_SECRET_LABEL_PREFIX`
- `JUJU_SECRET_IS_LEGACY_KEY`
- `JUJU_SECRET_IS_CLIENT_KEY`

**`src/crypto.py`** — delete the following functions and their imports:
- `generate_private_key()` (and its `rsa` / `serialization` imports if now unused)
- `build_csr()` (and its `x509` / `CertificateSigningRequestBuilder` imports if now unused)
- `csr_sha256_hex()`

Keep: `classify_sans`, `build_ca_bundle`.

Run the unit tests to confirm nothing else imported the deleted symbols:

```bash
tox -e unit -- tests/unit/test_crypto.py -x
```

## Notes

- `PrivateKey` from `charmlibs.interfaces.tls_certificates` may also be imported in
  `crypto.py` — remove if present.
- If `hashlib` is only used by `csr_sha256_hex`, remove that import too.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
