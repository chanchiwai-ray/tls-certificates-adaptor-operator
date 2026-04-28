---
title: TLS Certificate Adaptor Operator
status: Approved
date: 2026-04-27
---

# TLS Certificate Adaptor Operator

## Abstract

The `tls-certificate-adaptor-operator` is a machine charm that bridges the legacy reactive `tls-certificates` interface (Charmed OpenStack, Yoga and earlier) with the modern `tls-certificates-interface` (charmlibs), enabling Charmed OpenStack services to obtain TLS certificates from any compatible upstream TLS provider — such as vault-k8s or lego-k8s — without modification to either side.

## Rationale

Charmed OpenStack services (keystone, nova, cinder, etc.) rely on the reactive `tls-certificates` interface in which the CA provider generates and returns both the private key and the signed certificate. Modern Juju TLS tooling (vault-k8s, lego-k8s) implements the `tls-certificates-interface` (charmlibs), which requires the requirer to generate its own key, send a CSR, and receive back only the signed certificate.

Without an adaptor, OpenStack services cannot obtain certificates from these modern providers. The adaptor sits between the two, translating requests and responses so that the underlying charms require no changes.

## Specification

### Goals

- Provide the old reactive `tls-certificates` interface to one or more Charmed OpenStack services simultaneously (multiple `certificates` relations).
- Forward certificate requests to a compatible upstream TLS provider (vault-k8s or lego-k8s) using the modern `tls-certificates-interface` (charmlibs).
- Generate RSA private keys on behalf of old-interface requesters and return them alongside signed certificates.
- Propagate the signed certificate, CA certificate, and chain back to old-interface requesters.
- Handle certificate renewal when the upstream TLS provider rotates or reissues a certificate.

### Non-Goals

- Client, application-shared, and intermediate CA certificate types. Only `server` certificates are in scope for this initial version.
- Modifying or replacing the old interface in the requirer charms.
- Providing a long-term replacement for migrating to the new interface (the adaptor is a migration bridge, not a permanent solution).
- Custom renewal scheduling or certificate validity configuration.

### Architecture

The adaptor charm is a machine charm with no workload process. Its only responsibility is routing certificate requests and responses between the two interface sides.

```mermaid
graph LR
    OC["OpenStack charms (keystone, nova-cloud-controller, cinder…)"]
    AD["tls-certificate-adaptor (this charm)"]
    UP["upstream TLS provider (vault-k8s or lego-k8s)"]

    OC -- "common_name + SANs (old tls-certificates)" --> AD
    AD -- "CSR (new tls-certificates)" --> UP
    UP -- "cert + CA + chain (new tls-certificates)" --> AD
    AD -- "cert + key + CA (old tls-certificates)" --> OC
```

#### Internal data flow

```mermaid
sequenceDiagram
    participant OC as OpenStack charm
    participant AD as Adaptor (this charm)
    participant JS as Juju Secret (internal)
    participant UP as Upstream TLS provider

    OC->>AD: relation-changed (common_name, SANs)
    AD->>AD: generate RSA private key for old requirer
    AD->>AD: build CSR from key + common_name + SANs
    AD->>JS: store secret(csr_sha256) = {private_key, requirer_unit, relation_id}
    AD->>UP: send CSR (new tls-certificates)
    UP-->>AD: certificate_available event (cert, CA, chain)
    AD->>JS: look up secret by CSR fingerprint → get private_key + requirer
    AD->>OC: write cert + key + CA to relation data (old interface)
```

#### Certificate renewal flow

```mermaid
sequenceDiagram
    participant UP as Upstream TLS provider
    participant AD as Adaptor
    participant JS as Juju Secret (internal)
    participant OC as OpenStack charm

    UP-->>AD: certificate_expiring / certificate_invalidated
    AD->>AD: generate new RSA private key
    AD->>AD: build new CSR
    AD->>JS: store new secret(new_csr_sha256) = {private_key, requirer_unit, relation_id}
    AD->>UP: re-send CSR
    UP-->>AD: certificate_available (new cert)
    AD->>JS: look up secret by new CSR fingerprint
    AD->>OC: update cert + key + CA in relation data
```

### Example Deployment

A single `tls-certificate-adaptor` application serves all Charmed OpenStack services in the model — there is no need for a separate adaptor per service. Each OpenStack charm (keystone, nova-cloud-controller, cinder) forms its own `certificates` relation to the adaptor. The adaptor holds a single `certificates-upstream` relation to an upstream TLS provider.

Both vault-k8s and lego-k8s implement the same `tls-certificates` interface (charmlibs) and are interchangeable as the upstream provider. Because these are Kubernetes charms and the adaptor is a machine charm, the `certificates-upstream` relation is a **cross-model relation**: the TLS provider is deployed in a Kubernetes model, and the adaptor is deployed alongside the OpenStack charms in a machine model.

```mermaid
graph TB
    subgraph k8s-model ["Kubernetes model"]
        UP["vault-k8s (vault-pki endpoint) or lego-k8s (certificates endpoint)"]
    end

    subgraph machine-model ["Machine model"]
        AD["tls-certificate-adaptor"]
        KS["keystone"]
        NV["nova-cloud-controller"]
        CN["cinder"]
    end

    KS -- "certificates" --> AD
    NV -- "certificates" --> AD
    CN -- "certificates" --> AD
    AD -- "certificates-upstream (cross-model)" --> UP
```

**Deployment steps:**

```bash
# Option A: using vault-k8s as the upstream provider
juju switch k8s-model
juju deploy vault-k8s
juju offer vault-k8s:vault-pki

juju switch machine-model
juju deploy tls-certificate-adaptor
juju relate tls-certificate-adaptor:certificates-upstream admin/k8s-model.vault-k8s

# Option B: using lego-k8s as the upstream provider
juju switch k8s-model
juju deploy lego-k8s
juju offer lego-k8s:certificates

juju switch machine-model
juju deploy tls-certificate-adaptor
juju relate tls-certificate-adaptor:certificates-upstream admin/k8s-model.lego-k8s

# Either way — relate each OpenStack service to the adaptor
juju relate keystone:certificates tls-certificate-adaptor:certificates
juju relate nova-cloud-controller:certificates tls-certificate-adaptor:certificates
juju relate cinder:certificates tls-certificate-adaptor:certificates
```

Each unit of keystone, nova-cloud-controller, and cinder will receive its own signed certificate, private key, and CA certificate through the old `tls-certificates` relation data. All certificate requests are forwarded to the single upstream TLS provider.

### Module Structure

The charm follows the standard `charm.py → state.py → (no workload)` pattern from the project design guidelines.

| Module                    | Responsibility                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `charm.py`                | Observe Juju events; call `reconcile()`                                                          |
| `state.py`                | `CharmState`: aggregate old-interface requests and new-interface certificates into a single view |
| `certificate_provider.py` | Read and write old-interface relation data (reactive `tls-certificates` format)                  |

### Charm Metadata

```yaml
# charmcraft.yaml (relevant excerpt)
provides:
  certificates:
    interface: tls-certificates # old reactive interface

requires:
  certificates-upstream:
    interface: tls-certificates # new charmlibs interface — same Juju interface name; compatible with vault-k8s and lego-k8s
    limit: 1
```

### State Model

```python
class CertificateRequest(BaseModel):
    """A pending certificate request from an old-interface requirer unit."""

    common_name: str
    sans: list[str]
    cert_type: Literal["server"]
    requirer_unit_name: str
    relation_id: int


class IssuedCertificate(BaseModel):
    """A certificate issued by vault-k8s and ready to deliver."""

    certificate: str   # PEM
    ca: str            # PEM
    chain: list[str]   # list of PEM
    private_key: str   # PEM — generated by adaptor, stored for delivery to old requirer


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    certificate_requests: list[CertificateRequest]
    issued_certificates: dict[str, IssuedCertificate]  # keyed by CSR fingerprint
```

### Events Handled

| Event                                              | Source                 | Action                                                                                                                   |
| -------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `certificates_relation_joined`                     | Old-interface requirer | No-op; wait for `relation_changed` with actual request data                                                              |
| `certificates_relation_changed`                    | Old-interface requirer | Parse `cert_requests` from relation data; generate key + CSR; send to vault-k8s                                          |
| `certificates_relation_broken`                     | Old-interface requirer | Remove associated CSRs from upstream relation data; revoke mapping secrets; clean up state                               |
| `certificates_upstream_relation_joined`            | Upstream TLS provider  | Re-send any pending CSRs (idempotent recovery on relation re-join)                                                       |
| `certificate_available`                            | Upstream TLS provider  | Look up requirer via CSR-fingerprint secret; write cert + key + CA to old-interface relation data; revoke mapping secret |
| `certificate_expiring` / `certificate_invalidated` | Upstream TLS provider  | Generate new key + CSR; store new mapping secret; re-send CSR; update old relation data when new cert arrives            |

### Old-Interface Relation Data Format

The adaptor writes certificates to the provider's **unit** databag using the key `{munged_unit_name}.processed_requests`, where `munged_unit_name` replaces `/` with `_`. Each value is a JSON list of certificate objects.

Example:

```json
// adaptor unit databag for relation with keystone/0
{
  "keystone_0.processed_requests": "[{\"cert_type\": \"server\", \"common_name\": \"keystone.internal\", \"cert\": \"-----BEGIN CERTIFICATE-----\ ...\", \"key\": \"-----BEGIN RSA PRIVATE KEY-----\ ...\"}]"
}
```

### New-Interface Relation Data Format

The adaptor uses the `charmlibs.interfaces.tls_certificates` library, which manages the relation data format automatically. The adaptor initialises `TLSCertificatesRequiresV4` with a list of `CertificateRequestAttributes`; the library automatically sends CSRs and surfaces results via the `certificate_available` event.

### Key Management

There are three categories of key/secret managed by the adaptor:

| Category                                | Owner                            | Storage                                            | Visible to old charm?                                    |
| --------------------------------------- | -------------------------------- | -------------------------------------------------- | -------------------------------------------------------- |
| Old-requirer private key                | Adaptor (generated per unit CSR) | Juju Secret (internal) + relation data on delivery | Key delivered via plain relation data; secret not shared |
| CSR→requirer mapping                    | Adaptor                          | Juju Secret (internal, unit-owned)                 | No                                                       |
| Upstream private key (adaptor→provider) | Adaptor                          | Juju Secret (managed by charmlibs)                 | No                                                       |

#### Old-requirer private key and CSR mapping

When an old-interface `certificates_relation_changed` event arrives, the adaptor:

1. Generates an RSA private key (2048-bit minimum) for the old requirer unit.
2. Builds a CSR from that key, the `common_name`, and the `sans`.
3. **Creates a unit-owned Juju Secret** with label `tls-adaptor-{csr_sha256_hex}` containing:
   - `private-key`: the generated RSA private key (PEM)
   - `requirer-unit`: e.g. `keystone/0`
   - `relation-id`: the old-interface relation ID as a string
4. Sends the CSR to the upstream provider via charmlibs.

This secret is **never granted or shared** with old reactive charms. When `certificate_available` fires, the adaptor retrieves the secret by CSR fingerprint, writes the cert + private key to the old requirer's relation data, then revokes the secret.

> **Why not peer relation data?** Peer data requires a `peers` endpoint and is visible to all units. A unit-owned Juju Secret is simpler, scoped to the adaptor unit, and keeps the private key off the relation data bus until it must be delivered.

#### Upstream private key

The adaptor's own private key (used when building the CSR sent to vault-k8s / lego-k8s) is managed entirely by the `charmlibs.interfaces.tls_certificates` library, which stores it as a Juju Secret. The adaptor does not handle this key directly. Requires Juju >= 3.0.

### Juju Requirements

| Requirement          | Value                        |
| -------------------- | ---------------------------- |
| Minimum Juju version | 3.0                          |
| Charm type           | Machine                      |
| Juju Secrets         | Required (new interface leg) |

### Security Considerations

> **Known limitation:** Private keys generated by the adaptor for old-interface requesters are stored as plaintext in Juju unit relation data, which is persisted in the Juju controller database. This is an inherent limitation of the old `tls-certificates` reactive interface contract.
>
> The adaptor is intended as a **migration bridge** to allow Charmed OpenStack services to move off charm-vault (OpenStack) and onto vault-k8s or lego-k8s incrementally. It is not a permanent TLS solution. Operators should prioritize upgrading OpenStack charms to use the new interface natively.

## Further Information

### Architecture Decisions

- [ADR-1: Private key ownership for legacy-interface certificate requesters](./decision.md#1-private-key-ownership-for-legacy-interface-certificate-requesters) — Settles why old-requirer keys are delivered via relation data.
- [ADR-2: CSR-to-requirer mapping persistence](./decision.md#2-csr-to-requirer-mapping-persistence) — Settles why unit-owned Juju Secrets are used for the internal mapping.

### Library Choice

The adaptor uses `charmlibs.interfaces.tls_certificates` (pip: `charmlibs-interfaces-tls-certificates`) for the new interface leg. The older `charms.tls_certificates_interface.v4.tls_certificates` library is deprecated and must not be used.

### Cert-Type Scope

Only `server` certificate requests are handled in this initial version. Requests for `client`, `application`, or `intermediate` cert types from old-interface requesters are logged and ignored.

## References

- [R1: canonical/interface-tls-certificates](https://github.com/canonical/interface-tls-certificates) — old reactive interface definition
- [R2: charmlibs tls_certificates library](https://charmhub.io/tls-certificates-interface/libraries/tls_certificates) — new interface API
- [R3: tls_certificates v4 source](https://github.com/canonical/tls-certificates-interface/blob/main/lib/charms/tls_certificates_interface/v4/tls_certificates.py) — relation data schemas and lifecycle
- [R4: charm-vault vault_pki.py](https://opendev.org/openstack/charm-vault/src/branch/master/src/lib/charm/vault_pki.py) — how the old provider side works
- [R5: charm-ops-interface-tls-certificates ca_client.py](https://opendev.org/openstack/charm-ops-interface-tls-certificates/src/branch/master/interface_tls_certificates/ca_client.py) — exact old-interface relation data keys
- [R6: OpenStack Charm Deployment Guide — TLS certificates](https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-certificate-management.html)
- [R7: Juju Secret reference](https://documentation.ubuntu.com/juju/en/latest/reference/secret/)
- [R9: canonical/vault-k8s-operator](https://github.com/canonical/vault-k8s-operator) — target new-interface provider
