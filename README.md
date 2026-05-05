<!--
Avoid using this README file for information that is maintained or published elsewhere, e.g.:

* metadata.yaml > published on Charmhub
* documentation > published on (or linked to from) Charmhub
* detailed contribution guide > documentation or CONTRIBUTING.md

Use links instead.
-->

# TLS Certificates Adaptor

<!-- Use this space for badges -->

> **Note:** This is a transitional charm intended for existing Charmed OpenStack deployments (Yoga and earlier) that need to bridge the legacy `tls-certificates` interface with modern TLS providers. It is not intended for new OpenStack deployments. If you are planning a new OpenStack deployment, consider using [Canonical OpenStack](https://canonical.com/openstack) instead.

A machine charm that bridges the legacy reactive `tls-certificates` interface (v1, Charmed OpenStack Yoga and earlier) with the modern `tls-certificates-interface` (v4) used by `vault-k8s` and `lego-k8s`, enabling Charmed OpenStack services to obtain TLS certificates from modern providers without modification to either side.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more. For Charmed tls-certificates-adaptor, this includes:

- Automatic CSR generation and forwarding to the upstream TLS provider
- Certificate delivery to all connected legacy OpenStack services
- Full CA chain assembly, including optional extra CA certificates via config
- Transparent certificate renewal managed by the upstream library

For information about how to deploy, integrate, and manage this charm, see the Official [tls-certificates-adaptor Documentation](https://charmhub.io/tls-certificates-adaptor).

## Get started

### Prerequisites

- A Juju model with Ubuntu 22.04 or 24.04 machines
- An upstream TLS provider deployed in a reachable Juju model (e.g. `vault-k8s` or `lego-k8s`)
- One or more Charmed OpenStack services that consume the legacy `tls-certificates` interface (e.g. `keystone`, `nova-cloud-controller`, `cinder`)

### Deploy

```bash
juju deploy tls-certificates-adaptor
```

### Integrate with an upstream TLS provider

```bash
# The new vault: https://canonical-vault-charms.readthedocs-hosted.com/en/latest/
juju relate tls-certificates-adaptor:certificates-upstream vault

# The new vault needs a certificates providers e.g. self-signed-certificates charm: https://charmhub.io/self-signed-certificates
juju deploy self-signed-certificates
juju relate vault self-signed-certificates

# Configure the vault pki_* config options as needed, e.g.
juju config vault pki_ca_common_name="My Root CA" pki_allow_any_name=true pki_allow_ip_sans=true pki_allow_subdomains=true
```

### Integrate with legacy OpenStack services

```bash
juju relate keystone:certificates tls-certificates-adaptor:certificates
juju relate cinder:certificates tls-certificates-adaptor:certificates
juju relate nova-cloud-controller:certificates tls-certificates-adaptor:certificates
...
```

### Basic operations

**Append an extra root CA to the delivered chain** (useful when the upstream provider uses an intermediate CA not rooted in a well-known CA):

```bash
juju config tls-certificates-adaptor ca-certificates="$(cat /path/to/root-ca.pem)"
```

## Integrations

| Relation name           | Role     | Interface          | Description                                                      |
| ----------------------- | -------- | ------------------ | ---------------------------------------------------------------- |
| `certificates`          | Provider | `tls-certificates` | Legacy v1 interface consumed by Charmed OpenStack services       |
| `certificates-upstream` | Requirer | `tls-certificates` | Modern v4 interface provided by vault-k8s or lego-k8s (limit: 1) |

## Learn more

- [Read more](https://charmhub.io/tls-certificates-adaptor)
- [Developer documentation](https://github.com/chanchiwai-ray/tls-certificates-adaptor-operator)
- [tls-certificates-interface library](https://charmhub.io/tls-certificates-interface)
- [Troubleshooting](https://github.com/chanchiwai-ray/tls-certificates-adaptor-operator/issues)

## Project and community

- [Issues](https://github.com/chanchiwai-ray/tls-certificate-adaptor-operator/issues)
- [Contributing](CONTRIBUTING.md)
- [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

## Licensing and trademark (optional)
