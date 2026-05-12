---
title: Drop private_key from TLSCertificatesRequiresV4 and related cleanup
status: Approved
date: 2026-05-11
---

# 1. Remove private key management from the upstream TLS certificates relation

## Context

The adaptor charm currently generates a single RSA private key at startup, persists it in a
unit-owned Juju Secret (`tls-adaptor-private-key`), and passes it to
`TLSCertificatesRequiresV4` via the `private_key` constructor argument. The same key is also
copied into every per-CSR mapping secret (`tls-adaptor-{fingerprint}`) so that it can be written
back to old-interface requirers when `certificate_available` fires. Each mapping secret also
stores `requirer-unit`, `relation-id`, `is-legacy`, and `is-client` fields.

An external reviewer noted that passing `private_key` to the modern v4 library is not
recommended. The library is capable of generating and managing its own key internally via its
`private_key` property (`TLSCertificatesRequiresV4.private_key -> PrivateKey | None`);
supplying a charm-owned key couples the two concerns unnecessarily and means the charm owns a
long-lived secret with no functional benefit.

Additionally, the `certificate_denied` handler only revokes the per-CSR mapping secret and logs
an error — a side effect that is implicit in the library's own error handling and produces no
observable benefit for old-interface requirers.

Constructing `TLSCertificatesRequiresV4` with `certificate_requests` at `__init__` time creates
a rigid ordering dependency: the old-relation data must be parsed before the library object can
be created. Using `sync()` with a mutable `certificate_requests` attribute removes this coupling.

When `certificate_available` fires, the charm needs to know which old-interface relation and unit
to deliver the certificate to, and whether to use the legacy or batch format. Currently this is
stored in the per-CSR mapping secret. However, the live old-interface relation data is still
present at event time and contains all the information needed to re-derive these fields without
any stored state.

## Decision

`private_key` is not passed to `TLSCertificatesRequiresV4`. The library generates and manages
its own key, which is retrieved via the `private_key` property for old-interface delivery.

`TLSCertificatesRequiresV4` is constructed with `certificate_requests=[]`. In `reconcile`,
`self._tls.certificate_requests` is updated from old-relation data and `self._tls.sync()` is
called to submit CSRs and clean up stale ones.

**The per-CSR mapping secrets (`tls-adaptor-{fingerprint}`) are eliminated entirely.** At
`certificate_available` time, `common_name` and `sans` are extracted from
`event.certificate_signing_request`. The charm iterates all active old-interface relations and
their unit databags, re-parses requests using the same logic as `get_certificate_requests()`,
and finds the matching request by `(common_name, sans)`. The `relation_id`, `requirer_unit`,
`is_legacy`, and `is_client` fields are all re-derived from live relation data. This is
acceptable because the number of active old-interface relations is small (typically one) and the
relation data is always available when the upstream provider is responding.

As a consequence, `secret.py` is deleted entirely, along with all constants and databag keys
used to track CSR identifiers across events.

`_on_certificate_available` does not call `reconcile()`. All certificate delivery work is done
inside `handle_certificate_available`; `ActiveStatus` is set directly afterwards. This avoids
the following recursion: `sync()` calls `_configure()`, which calls
`_find_available_certificates()`, which emits `certificate_available` synchronously and inline
(ops custom events are nested, not queued). Calling `reconcile()` → `sync()` from within
`_on_certificate_available` would therefore re-enter `_on_certificate_available` for the same
certificate, causing double-delivery.

## Considered Alternatives

| Alternative | Pros | Cons |
|-------------|------|------|
| Re-derive from live relation data (chosen) | No Juju Secrets; stateless; no cleanup on relation-break | Slightly more work per `certificate_available` event (iterate relations) |
| Keep per-CSR mapping secrets without private key | Explicit state; fast lookup at delivery time | Requires secret lifecycle management; cleanup on relation-break; orphaned secrets on upgrade |
| Keep current approach | No change | Contradicts reviewer guidance; charm manages secrets with no unique benefit |

## Consequences

**Easier:**
- The charm no longer manages any Juju Secrets of its own, reducing attack surface and
  operational complexity.
- `secret.py` is deleted entirely.
- `crypto.py:build_csr`, `crypto.py:generate_private_key`, and `crypto.py:csr_sha256_hex` are
  deleted (unused).
- `CSR_FINGERPRINTS_KEY`, `CSR_MAPPING_IDS_KEY`, `CHARM_PRIVATE_KEY_SECRET_LABEL`,
  `JUJU_SECRET_LABEL_PREFIX`, `JUJU_SECRET_IS_LEGACY_KEY`, and `JUJU_SECRET_IS_CLIENT_KEY`
  constants are deleted from `constants.py`.
- `OldTLSCertificatesRelation.process_relation`, `write_csr_fingerprints`, and
  `revoke_csr_mappings` are deleted; `_on_certificates_relation_broken` is simplified to just
  calling `reconcile()`.
- `CertificateDeniedEvent` import, handler, and framework observation are deleted from
  `charm.py`.
- `TLSCertificatesRequiresV4` construction no longer depends on old-relation data being parsed
  first.

**Harder / Risks:**
- Existing deployments have `csr-fingerprints` in unit relation databags and orphaned
  `tls-adaptor-{fingerprint}` mapping secrets. After upgrade these are inert; old mapping
  secrets can be removed manually with `juju remove-secret`. The `csr-fingerprints` databag key
  is simply never read again.
- Old-interface requirers now share the library's single key rather than a key the charm fully
  controlled. This is an acceptable trade-off given the library manages the key securely.

## References

- `docs/design/2026-05-11_remove-private-key-tls-relation/reference.md`
