# 004. Store `is-legacy` in the CSR mapping secret and thread it through `charm.py`

## What

Update `src/secret.py` to include an `is-legacy` field in the CSR mapping secret payload.
Update `src/charm.py` to:

1. Pass `is_legacy` when calling `store_csr_mapping()`.
2. Read `is-legacy` from the mapping secret in `_on_certificate_available()` and pass it to
   `write_certificate()`.
3. Call `self._old_handler.write_ca()` in `_on_certificate_available()` to propagate the CA cert
   to all old-interface relations.

## How

### `src/secret.py` — `store_csr_mapping()`

Add `is_legacy: bool = False` parameter and include it in the secret content:

```python
def store_csr_mapping(
    charm: ops.CharmBase,
    csr_pem: str,
    private_key_pem: str,
    requirer_unit: str,
    relation_id: int,
    is_legacy: bool = False,
) -> None:
    label = f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}"
    charm.unit.add_secret(
        content={
            "private-key": private_key_pem,
            "requirer-unit": requirer_unit,
            "relation-id": str(relation_id),
            "is-legacy": "true" if is_legacy else "false",
        },
        label=label,
    )
```

### `src/charm.py` — `_on_certificates_relation_changed()`

Pass `is_legacy` from the `CertificateRequest` to `store_csr_mapping()`:

```python
store_csr_mapping(
    self,
    csr_pem,
    self._charm_key_pem,
    cr.requirer_unit_name,
    cr.relation_id,
    is_legacy=cr.is_legacy,
)
```

### `src/charm.py` — `_on_certificate_available()`

Read `is-legacy` from the mapping dict and pass it to `write_certificate()`. Also call
`write_ca()` to propagate the CA to all old-interface relations:

```python
is_legacy = mapping.get("is-legacy", "false") == "true"

self._old_handler.write_certificate(
    relation_id=relation_id,
    requirer_unit_name=requirer_unit_name,
    common_name=str(event.certificate.common_name),
    cert=str(event.certificate),
    key=private_key_pem,
    ca=str(event.ca),
    chain="\n".join(str(c) for c in event.chain) if event.chain else "",
    is_legacy=is_legacy,
)
self._old_handler.write_ca(
    ca=str(event.ca),
    chain="\n".join(str(c) for c in event.chain) if event.chain else "",
)
```

Note: `write_ca()` will write to all relations including the one already written by
`write_certificate()` — this is idempotent (same values, same keys).

Run the full unit test suite:

```bash
tox -e unit
```

## Notes

- Existing secrets without `is-legacy` will return `mapping.get("is-legacy", "false") == "true"`
  → `False` — the batch format, which is the correct fallback.
- `event.chain` on `CertificateAvailableEvent` is a list of `Certificate` objects. Joining with
  `"\n"` produces a standard PEM bundle accepted by OpenStack services.
- `event.chain` is confirmed to be a `list[Certificate]` attribute on `CertificateAvailableEvent`
  (verified against the installed `charmlibs` library). The library also provides a
  `chain_as_pem` helper — either `"\n".join(str(c) for c in event.chain)` or
  `event.chain_as_pem` (if available on the event) can be used. Prefer whichever is simpler
  after checking the installed API.
- `store_csr_mapping()` has a default `is_legacy=False` so all existing call sites outside
  `charm.py` continue to work unchanged.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
