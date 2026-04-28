---
title: Private key ownership for legacy-interface certificate requesters
status: Approved
date: 2026-04-27
---

# 1. Private key ownership for legacy-interface certificate requesters

## Context

The adaptor charm bridges two fundamentally different TLS certificate interface designs:

- **Old interface** (`tls-certificates`, reactive): the CA provider generates **both** the private key and the signed certificate and returns both to the requirer through plain Juju relation data. Old OpenStack charms (Yoga and earlier) have no concept of generating their own keys or reading Juju Secrets.
- **New interface** (`tls-certificates`, charmlibs): the requirer generates its own private key, sends only a CSR, and receives back only the signed certificate. Private keys never leave the requirer unit.

The adaptor acts as a **provider** on the old interface side and as a **requirer** on the new interface side. Because old-interface requesters do not generate private keys, the adaptor must generate and supply them. The question is: where are those keys stored and how are they delivered?

Juju Secrets support cross-application sharing, but old reactive charms have no Juju Secrets support. The only delivery channel the old charms can consume is plain string values in Juju relation data, which is stored in the Juju controller database.

## Decision

The adaptor will **generate RSA private keys on behalf of each old-interface requirer unit** and write them into unit relation data alongside the signed certificate, as the old interface contract requires.

The adaptor's own private keys — used for the new interface leg when sending CSRs to vault-k8s — will be stored as **Juju Secrets** (internal to the adaptor, not shared with old charms).

## Considered Alternatives

| Alternative                                                      | Pros                                                             | Cons                                                                                                                                                   |
| ---------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Adaptor generates keys and stores in relation data (chosen)**  | Compatible with old interface; no changes to old charms required | Private keys stored in the Juju controller database (plaintext in unit relation data). Accepted limitation of the old interface design.                |
| Share generated keys via Juju Secrets                            | Private keys not stored as plain relation data in controller DB  | Old reactive charms have no Juju Secrets support; they cannot read secret IDs from relation data. Requires modifying old charms — defeats the purpose. |
| Refuse to supply private keys (requirer must supply its own CSR) | No key-in-relation-data risk                                     | Breaks the old interface contract entirely; old charms cannot use the certificate at all.                                                              |

## Consequences

- Private keys generated for old-style requesters will reside in the Juju controller database as part of unit relation data. This is a **known and accepted limitation** of the old interface design.
- The adaptor must be documented as a **migration tool** to enable gradual upgrade of Charmed OpenStack, not as a permanent TLS solution.
- The adaptor must use a cryptographically sound key-generation library (e.g., the `cryptography` Python package) to generate RSA keys.
- The adaptor must Juju >= 3.0 (required for Juju Secrets used on the new interface leg).

## References

- [canonical/interface-tls-certificates](https://github.com/canonical/interface-tls-certificates) — old reactive interface contract
- [charmlibs.interfaces.tls_certificates](https://charmhub.io/tls-certificates-interface/libraries/tls_certificates) — new interface library
- [Juju Secret reference](https://documentation.ubuntu.com/juju/en/latest/reference/secret/) — Juju Secrets lifecycle and cross-app sharing
