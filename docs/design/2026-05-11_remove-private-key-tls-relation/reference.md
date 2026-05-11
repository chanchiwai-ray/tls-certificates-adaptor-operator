---
name: Remove private key from new TLS certificates relation
date: 2026-05-11
description: Research into the implications of removing private key management from the upstream TLS certificates (v4) relation in the adaptor charm.
---

# Research References

## Summary

The `TLSCertificatesRequiresV4` library (charmlibs) allows the requirer to supply a private key
when constructing the object, but this is not required.  When no `private_key` is passed the
library generates and manages its own key internally, storing it in a provider-managed Juju
Secret.  The adaptor charm currently generates a single RSA private key, persists it in a
unit-owned Juju Secret (`tls-adaptor-private-key`), passes it to the library, and also stores
a copy of it in every per-CSR mapping secret so that it can be written back to the old-interface
requirer on `certificate_available`.

Because the old reactive tls-certificates (v1) interface *requires* the provider to return the
private key alongside the certificate, the adaptor must obtain that key from somewhere.  When no
`private_key` is supplied to `TLSCertificatesRequiresV4`, the library generates one per CSR
internally, and the resulting `CertificateAvailableEvent` does not surface the private key to
the charm handler.

There are two consequences for the adaptor:

1. **The upstream library's internally-managed key is inaccessible to the charm.**  When
   `private_key` is omitted, the charm cannot retrieve the private key from the event or from
   the library.  This means the adaptor can no longer write the private key to the old-interface
   relation databag, which breaks the old-interface protocol.

2. **The adaptor's private key served two purposes:** (a) signing CSRs sent upstream and
   (b) being delivered to old-interface requirers.  Both purposes disappear when the library
   owns the key.

However, looking at the old-interface writing code (`write_certificate`, `write_client_cert`),
the `key` field that is written to the old-interface databag comes from `mapping["private-key"]`
in the per-CSR mapping secret.  If the adaptor manages no private key of its own, it cannot
populate this field.

The correct resolution is: **the adaptor must generate its own per-CSR private key, but it does
NOT need to hand that key to the upstream library**.  Instead it passes the private key only to
`TLSCertificatesRequiresV4` as required (or not at all if the library supports omitting it) and
continues to store the key in the per-CSR mapping secret for delivery via the old interface.

Re-reading the external reviewer's comment: "You don't need to use `private_key` in the new TLS
certificates relation" — the recommendation is to stop passing the charm's single shared key
to the library.  Instead, either let the library manage its own key (if it can generate per-CSR
keys internally) or generate a fresh key per CSR and only use it for the old-interface delivery,
without passing it to the library constructor.

After examining `TLSCertificatesRequiresV4`: the constructor signature for `private_key` is
optional (`private_key: PrivateKey | None = None`).  When omitted the library generates and
manages its own key; the adaptor charm then has no key to deliver to old-interface requirers.

Therefore the full intent of the reviewer's three points, taken together, is:

- **Point 1**: Stop passing `private_key` to `TLSCertificatesRequiresV4`.
- **Point 2**: The charm-owned `tls-adaptor-private-key` Juju Secret (and all associated
  `generate_private_key` / `get_or_generate_private_key` logic) is no longer needed.
  The per-CSR mapping secret's `"private-key"` field is also removed because there is no
  longer a key to store there.
- **Point 3**: `certificate_denied` handling can be removed.

The implication for the old-interface `key` delivery is that the adaptor must **stop writing the
private key** to the old-interface relation databag.  This is a protocol change: old requirers
that currently read `{unit}.server.key` or `processed_requests[cn]["key"]` will no longer
receive a key.  This may be acceptable if downstream charms already generate their own keys or
if the key field is unused.  This is a deliberate breaking-protocol simplification requested by
the reviewer.

## Key Findings

- `TLSCertificatesRequiresV4` accepts `private_key` as an optional parameter; omitting it causes
  the library to manage the key internally without exposing it to the charm.
- The charm currently stores the private key in two places: a unit-owned Juju Secret
  (`tls-adaptor-private-key`) and inside every per-CSR mapping secret (`"private-key"` field).
- Removing `private_key` from the library call means the charm no longer has a key to write to
  the old-interface databag; the `key` field in `write_certificate` / `write_client_cert` must
  be removed or left empty.
- `handle_certificate_denied` in `NewTLSCertificatesRelation` only revokes the mapping secret;
  once the mapping secret no longer stores a private key, the denial handler becomes a log-only
  operation with no meaningful side effects, so it can be deleted.
- The `build_csr` helper in `crypto.py` and the `generate_private_key` helper both become unused
  once the charm stops owning the private key.
- `get_or_generate_private_key` in `secret.py` and the `CHARM_PRIVATE_KEY_SECRET_LABEL` constant
  can be deleted.
- `store_csr_mapping` signature loses the `private_key_pem` parameter; the `"private-key"` field
  is removed from the secret content.
- `OldTLSCertificatesRelation.__init__` no longer needs `private_key_pem`; the `_private_key_pem`
  attribute and all usages of it (`build_csr` calls in `process_relation`, `get_csr_fingerprints`)
  must be replaced with a key-free CSR fingerprinting strategy.
- Because CSR fingerprinting currently relies on rebuilding the CSR from the private key +
  common_name + SANs, an alternative fingerprinting approach is needed once the private key is
  dropped (e.g. store the CSR PEM itself or the fingerprint directly in the mapping secret).

## References

| #  | Source | Description | Relevance |
|----|--------|-------------|-----------|
| 1  | `src/new_tls_certificate.py` | Uses `PrivateKey.from_string(private_key_pem)` and passes it to `TLSCertificatesRequiresV4` | Primary change target |
| 2  | `src/secret.py:get_or_generate_private_key` | Generates and persists the charm's private key secret | To be deleted |
| 3  | `src/secret.py:store_csr_mapping` | Stores `"private-key"` in per-CSR mapping secrets | `private_key_pem` param to be removed |
| 4  | `src/charm.py:__init__` | Calls `get_or_generate_private_key` and wires `_on_certificate_denied` | Both to be removed |
| 5  | `src/old_tls_certificate.py:process_relation` | Calls `build_csr` with `self._private_key_pem` | Needs new CSR-free fingerprinting |
| 6  | `src/old_tls_certificate.py:get_csr_fingerprints` | Same `build_csr` usage | Needs new CSR-free fingerprinting |
| 7  | `src/old_tls_certificate.py:write_certificate` | Writes `key` to old-interface databag | `key` parameter to be removed |
| 8  | `src/old_tls_certificate.py:write_client_cert` | Writes `client.key` to old-interface databag | `key` parameter to be removed |
| 9  | `src/crypto.py:build_csr` | Builds a deterministic CSR from private key | Becomes unused; to be deleted |
| 10 | `src/crypto.py:generate_private_key` | Generates RSA key | Becomes unused; to be deleted |
| 11 | `src/constants.py:CHARM_PRIVATE_KEY_SECRET_LABEL` | Constant for the private key secret label | To be deleted |
