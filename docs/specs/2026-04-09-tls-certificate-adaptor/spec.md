---
title: TLS Certificate Adaptor Operator
status: Approved
date: 2026-04-27
---

# TLS Certificate Adaptor Operator

## Abstract

The `tls-certificate-adaptor-operator` is a machine charm that bridges the legacy reactive `tls-certificates` interface (Charmed OpenStack, Yoga and earlier) with the modern `tls-certificates-interface` used by vault-k8s, enabling Charmed OpenStack services to obtain TLS certificates from vault-k8s without modification to either side.

## Rationale

Charmed OpenStack services (keystone, nova, cinder, etc.) rely on the reactive `tls-certificates` interface in which the CA provider generates and returns both the private key and the signed certificate. Modern Juju TLS tooling (vault-k8s) implements the `tls-certificates-interface` (charmlibs), which requires the requirer to generate its own key, send a CSR, and receive back only the signed certificate.

Without an adaptor, OpenStack services cannot obtain certificates from vault-k8s. The adaptor sits between the two, translating requests and responses so that the underlying charms require no changes.

## Specification

### Goals

- Provide the old reactive `tls-certificates` interface to one or more Charmed OpenStack services simultaneously (multiple `certificates` relations).
- Forward certificate requests to vault-k8s using the modern `tls-certificates-interface` (charmlibs).
- Generate RSA private keys on behalf of old-interface requesters and return them alongside signed certificates.
- Propagate the signed certificate, CA certificate, and chain back to old-interface requesters.
- Handle certificate renewal when vault-k8s rotates or reissues a certificate.

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
    VK["vault-k8s"]

    OC -- "common_name + SANs (old tls-certificates)" --> AD
    AD -- "CSR (new tls-certificates)" --> VK
    VK -- "cert + CA + chain (new tls-certificates)" --> AD
    AD -- "cert + key + CA (old tls-certificates)" --> OC
```

#### Internal data flow

```mermaid
sequenceDiagram
    participant OC as OpenStack charm
    participant AD as Adaptor (this charm)
    participant VK as vault-k8s

    OC->>AD: relation-changed (common_name, SANs)
    AD->>AD: generate RSA private key
    AD->>AD: build CSR from key + common_name + SANs
    AD->>VK: send CSR (new tls-certificates)
    VK-->>AD: certificate_available event (cert, CA, chain)
    AD->>AD: look up requirer by CSR fingerprint
    AD->>OC: write cert + key + CA to relation data (old interface)
```

#### Certificate renewal flow

```mermaid
sequenceDiagram
    participant VK as vault-k8s
    participant AD as Adaptor
    participant OC as OpenStack charm

    VK-->>AD: certificate_expiring / certificate_invalidated
    AD->>AD: generate new RSA private key
    AD->>AD: build new CSR
    AD->>VK: re-send CSR
    VK-->>AD: certificate_available (new cert)
    AD->>OC: update cert + key + CA in relation data
```

### Example Deployment

A single `tls-certificate-adaptor` application serves all Charmed OpenStack services in the model — there is no need for a separate adaptor per service. Each OpenStack charm (keystone, nova-cloud-controller, cinder) forms its own `certificates` relation to the adaptor. The adaptor holds a single `vault-pki` relation to vault-k8s.

Because vault-k8s is a Kubernetes charm and the adaptor is a machine charm, the `vault-pki` relation is a **cross-model relation**: vault-k8s is deployed in a Kubernetes model, and the adaptor is deployed alongside the OpenStack charms in a machine model.

```mermaid
graph TB
    subgraph k8s-model ["Kubernetes model"]
        VK["vault-k8s (vault-pki endpoint)"]
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
    AD -- "vault-pki (cross-model)" --> VK
```

**Deployment steps:**

```bash
# 1. Deploy vault-k8s in a Kubernetes model and expose the vault-pki endpoint as an offer
juju switch k8s-model
juju deploy vault-k8s
juju offer vault-k8s:vault-pki

# 2. Deploy the adaptor in the machine model
juju switch machine-model
juju deploy tls-certificate-adaptor

# 3. Relate the adaptor to vault-k8s via cross-model relation
juju relate tls-certificate-adaptor:vault-pki admin/k8s-model.vault-k8s

# 4. Relate each OpenStack service to the adaptor
juju relate keystone:certificates tls-certificate-adaptor:certificates
juju relate nova-compute:certificates tls-certificate-adaptor:certificates
juju relate cinder:certificates tls-certificate-adaptor:certificates
```

After step 4, each unit of keystone, nova-compute, and cinder will receive its own signed certificate, private key, and CA certificate through the old `tls-certificates` relation data. All certificate requests are forwarded to the same vault-k8s instance.

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
  vault-pki:
    interface: tls-certificates # new charmlibs interface — same Juju interface name
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

| Event                                              | Source                 | Action                                                                                       |
| -------------------------------------------------- | ---------------------- | -------------------------------------------------------------------------------------------- |
| `certificates_relation_joined`                     | Old-interface requirer | No-op; wait for `relation_changed` with actual request data                                  |
| `certificates_relation_changed`                    | Old-interface requirer | Parse `cert_requests` from relation data; generate key + CSR; send to vault-k8s              |
| `certificates_relation_broken`                     | Old-interface requirer | Remove associated CSRs from new-interface relation data; clean up state                      |
| `tls_certificates_relation_joined`                 | vault-k8s              | Re-send any pending CSRs (idempotent recovery on relation re-join)                           |
| `certificate_available`                            | vault-k8s (charmlibs)  | Look up requirer by CSR fingerprint; write cert + key + CA to old-interface relation data    |
| `certificate_expiring` / `certificate_invalidated` | vault-k8s (charmlibs)  | Generate new key + CSR; re-send to vault-k8s; update old relation data when new cert arrives |

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

The adaptor uses the `charmlibs.interfaces.tls_certificates` library, which manages the relation data format automatically. The adaptor sends CSRs via `request_certificate_creation()` and reads results via the `certificate_available` event.

### Key Management

- **Old-interface private keys**: generated by the adaptor using `cryptography.hazmat.primitives.asymmetric.rsa` (RSA 2048-bit minimum). Stored in old-interface unit relation data alongside the certificate. This is a known limitation documented under "Security Considerations".
- **New-interface private keys** (adaptor's own upstream keys): managed by the `charmlibs.interfaces.tls_certificates` library, which stores them as Juju Secrets. Requires Juju >= 3.0.

### Juju Requirements

| Requirement          | Value                        |
| -------------------- | ---------------------------- |
| Minimum Juju version | 3.0                          |
| Charm type           | Machine                      |
| Juju Secrets         | Required (new interface leg) |

### Security Considerations

> **Known limitation:** Private keys generated by the adaptor for old-interface requesters are stored as plaintext in Juju unit relation data, which is persisted in the Juju controller database. This is an inherent limitation of the old `tls-certificates` reactive interface contract.
>
> The adaptor is intended as a **migration bridge** to allow Charmed OpenStack services to move off charm-vault (OpenStack) and onto vault-k8s incrementally. It is not a permanent TLS solution. Operators should prioritize upgrading OpenStack charms to use the new interface natively.

## Further Information

### Architecture Decisions

- [ADR-1: Private key ownership for legacy-interface certificate requesters](./decision.md) — Settles why private keys are stored in relation data and not in Juju Secrets.

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
