---
title: Old-interface relation data parsing strategy
status: Ready for Review
date: 2026-05-04
---

# 1. Parsing strategy for old-interface (v1) relation data: charmhelpers vs native implementation

## Context

The `OldTLSCertificatesRelation` handler in `old_tls_certificate.py` was implemented with an incorrect
understanding of the old reactive `tls-certificates` (v1) relation data format. Local testing revealed
that the `cert_requests` key is either absent or in a format the current code cannot parse, causing
all certificate requests to be silently dropped.

Investigation of the upstream interface libraries reveals two distinct data formats written by requirer
charms:

**Legacy / single-cert format** (reactive `TlsRequires.request_server_cert`, first request only):

```
# requirer's unit databag
common_name       = "keystone.example.com"           # plain string
certificate_name  = "<uuid>"                          # plain string
sans              = '["10.0.0.1", "10.0.0.2"]'       # JSON list
unit_name         = "keystone_0"                      # plain string
```

**Batch / multi-cert format** (reactive `TlsRequires.request_server_cert` for subsequent requests,
and the charmhelpers `CertRequest.get_request()` for all requests):

```
# requirer's unit databag
cert_requests = '{"keystone.example.com": {"sans": ["10.0.0.1", "10.0.0.2"]}, ...}'  # JSON dict
unit_name     = "keystone_0"
```

Note that `CertRequest.get_request()` from `charmhelpers.contrib.openstack.cert_utils` always uses
the **batch format** for all requests (never the legacy format). Many Charmed OpenStack services
(keystone, nova-cloud-controller, cinder) use this function.

The current `get_certificate_requests()` implementation:

1. Reads `cert_requests` and expects it to be a **JSON-encoded list** of objects with `cert_type`,
   `common_name`, and `sans` fields — this format does not exist in the upstream interface.
2. Ignores the **legacy format** entirely (`common_name` and `certificate_name` direct keys).
3. Ignores the **batch format** because `isinstance(entries, list)` fails for a dict.

The question is whether to address these bugs by pulling in `charmhelpers` (or the reactive
`interface-tls-certificates` library) as a dependency, or by re-implementing the parsing natively.

## Decision

We will **implement the relation data parsing natively** in `OldTLSCertificatesRelation`, without
adding `charmhelpers` or the reactive interface library as a dependency.

## Considered Alternatives

| Alternative                             | Pros                                                                               | Cons                                                                                                                                        |
| --------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Native parsing (chosen)**             | No extra dependencies; ops-idiomatic; full control over error handling and logging | Must maintain a hand-written parser aligned to the upstream interface specification                                                         |
| `charmhelpers` as a pip dependency      | Reuses battle-tested requirer-side `CertRequest` class                            | `CertRequest` is a **requirer** utility; no provider-side parser exists in charmhelpers; the library pulls in reactive framework hooks      |
| `interface-tls-certificates` (reactive) | `TlsProvides.all_requests` already parses all formats                              | Depends on `charms.reactive` (reactive framework), `hookenv`, and reactive flag infrastructure — none of which work in an ops charm context |
| `charm-ops-interface-tls-certificates`  | Ops-framework version of the interface; may provide a provider-side parser         | The library is an OpenStack-specific ops port; brings in OpenStack-specific dependencies; is not available on CharmHub for general use      |

## Consequences

- `OldTLSCertificatesRelation.get_certificate_requests()` must be rewritten to handle both the
  **legacy format** (direct `common_name` key) and the **batch format** (`cert_requests` JSON dict).
- `OldTLSCertificatesRelation.write_certificate()` must be rewritten to write responses in the
  correct format understood by the reactive requirer (see specification).
- The `charmcraft.yaml` / `pyproject.toml` do **not** gain any new runtime dependencies.
- The native parser must be kept in sync with the upstream interface spec if the interface evolves.
  Because the old interface is effectively frozen (OpenStack Yoga is end-of-life), drift is unlikely.
- Unit tests must cover all three cases: legacy format, batch format, and mixed (both in same
  databag, which the reactive library supports).

## References

- [canonical/interface-tls-certificates — requires.py](https://github.com/canonical/interface-tls-certificates/blob/master/requires.py) — canonical source for requirer-side data written by OpenStack charms.
- [canonical/interface-tls-certificates — provides.py](https://github.com/canonical/interface-tls-certificates/blob/master/provides.py) — `all_requests` property: the reference implementation for parsing all three formats on the provider side.
- [juju/charm-helpers — cert_utils.py](https://github.com/juju/charm-helpers/blob/master/charmhelpers/contrib/openstack/cert_utils.py) — `CertRequest.get_request()`: confirms the batch-format dict structure written by most Charmed OpenStack services.

---

# 2. CA propagation strategy

## Context

The old reactive `tls-certificates` provider (charm-vault) writes the Vault root CA cert to the
relation databag as a `ca` top-level key after issuing certificates. The reactive
`TlsRequires.joined()` reads this key and sets `{endpoint}.ca.available`, which some OpenStack
charm versions use to gate further lifecycle steps (service restarts, cert expiry handling).

The adaptor can only obtain a CA from the `ProviderCertificate.ca` field, which is populated by
the upstream provider (vault-k8s) after it issues a certificate. There is no standalone CA
endpoint in the `charmlibs.interfaces.tls_certificates` library.

Note: this was initially framed as a bootstrapping deadlock (cinder won't write cert requests
without a CA). Field testing disproved this: cinder writes cert requests on
`{endpoint}.available` (set on join), not on `{endpoint}.ca.available`. The CA propagation
concern remains valid for charms that do gate on `ca.available` and for CA rotation scenarios.

## Decision

The adaptor will **propagate the upstream CA cert to all active old-interface relations as soon as
it is obtained from any `certificate_available` event**, without adding any self-signed CA
generation or dummy-certificate mechanisms.

## Considered Alternatives

| Alternative                                            | Pros                                                                    | Cons                                                                                                                                       |
| ------------------------------------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Propagate real CA on first cert_available (chosen)** | No security trade-offs; uses real CA from upstream; simple to implement | CA not available until first cert is issued; charms gating on `ca.available` must wait one cert cycle                                      |
| Generate a self-signed CA on join                      | Immediately propagates a CA on join                                     | Sends a fake CA to OpenStack charms; all certs issued by real upstream will fail validation until the real CA is propagated; security risk |
| Request a "probe" cert from upstream on join           | Gets real CA without waiting for an organic cert request                | Requires generating and tracking a probe CSR + key; adds complexity; wastes a cert slot on the upstream provider                           |

## Consequences

- The `write_ca()` method in `OldTLSCertificatesRelation` must write `ca` and `chain` to **all**
  active old-interface relations (not just the one for the specific issued cert) so that every
  connected OpenStack charm receives the CA on the first `certificate_available` event.
- OpenStack charm versions that gate on `{endpoint}.ca.available` will only proceed after the
  first upstream cert is issued. In practice this is the same cert lifecycle the adaptor already
  processes, so no extra operator steps are needed.

## References

- [canonical/interface-tls-certificates — requires.py `TlsRequires.joined()`](https://github.com/canonical/interface-tls-certificates/blob/master/requires.py) — `{endpoint}.available` is set unconditionally on join; `{endpoint}.ca.available` requires `ca` to be present.
- `charmlibs.interfaces.tls_certificates.ProviderCertificate` — `ca` field only available after cert issuance; no standalone CA endpoint exists in the library.
