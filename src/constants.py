# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Project-wide constants."""

CERT_REQUEST_KEY = "cert_requests"
OLD_INTERFACE_CERT_TYPE = "server"
OLD_INTERFACE_RELATION_NAME = "certificates"
UPSTREAM_RELATION_NAME = "certificates-upstream"

CHARM_PRIVATE_KEY_SECRET_LABEL = "tls-adaptor-private-key"  # nosec B105
JUJU_SECRET_LABEL_PREFIX = "tls-adaptor-"  # nosec B105
JUJU_SECRET_IS_LEGACY_KEY = "is-legacy"  # nosec B105
JUJU_SECRET_IS_CLIENT_KEY = "is-client"  # nosec B105
PROCESSED_REQUESTS_SUFFIX = ".processed_requests"
LEGACY_CERT_SUFFIX = ".server.cert"
LEGACY_KEY_SUFFIX = ".server.key"
CLIENT_CERT_KEY = "client.cert"
CLIENT_KEY_KEY = "client.key"
CSR_FINGERPRINTS_KEY = "csr-fingerprints"
