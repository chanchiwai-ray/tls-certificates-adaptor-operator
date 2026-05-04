# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Juju Secret helpers for the charm private key and per-CSR requirer mapping."""

import logging

import ops

from constants import CHARM_PRIVATE_KEY_SECRET_LABEL, JUJU_SECRET_LABEL_PREFIX
from crypto import csr_sha256_hex, generate_private_key

logger = logging.getLogger(__name__)


def get_or_generate_private_key(charm: ops.CharmBase) -> str:
    """Return the charm's RSA private key, generating and persisting it if absent.

    The key is stored in a unit-owned Juju Secret so that the same key is
    reused across charm restarts and events.  All CSR mapping secrets and the
    upstream library use this single key.

    Args:
        charm (ops.CharmBase): The charm instance used to access the model and unit.

    Returns:
        str: PEM-encoded RSA private key.
    """
    try:
        secret = charm.model.get_secret(label=CHARM_PRIVATE_KEY_SECRET_LABEL)
        return secret.get_content(refresh=True)["private-key"]
    except ops.SecretNotFoundError:
        key_pem = generate_private_key()
        charm.unit.add_secret(
            content={"private-key": key_pem},
            label=CHARM_PRIVATE_KEY_SECRET_LABEL,
        )
        logger.info("Generated and stored new charm RSA private key")
        return key_pem


def store_csr_mapping(
    charm: ops.CharmBase,
    csr_pem: str,
    private_key_pem: str,
    requirer_unit: str,
    relation_id: int,
    is_legacy: bool = False,
) -> None:
    """Create a unit-owned Juju Secret mapping a CSR fingerprint to its requirer.

    The secret is labelled ``tls-adaptor-{csr_sha256_hex}`` and stores the
    private key and old-interface requirer information needed for certificate
    delivery.  The secret is never granted to any other application.

    Args:
        charm (ops.CharmBase): The charm instance used to access the unit.
        csr_pem (str): PEM-encoded CSR whose fingerprint is used as the secret label suffix.
        private_key_pem (str): PEM-encoded private key to store in the secret.
        requirer_unit (str): The old-interface requirer unit name (e.g. ``keystone/0``).
        relation_id (int): The old-interface relation ID.
        is_legacy (bool): When True the request used the legacy single-cert
            format; when False it used the batch format.  Stored so that
            ``_on_certificate_available`` can pass the correct flag to
            ``write_certificate()``.
    """
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
    logger.debug("Stored CSR mapping secret %r for requirer %s", label, requirer_unit)


def get_csr_mapping(charm: ops.CharmBase, csr_pem: str) -> dict[str, str] | None:
    """Look up the mapping secret for a CSR by its SHA-256 fingerprint.

    Args:
        charm (ops.CharmBase): The charm instance used to access the model.
        csr_pem (str): PEM-encoded CSR whose fingerprint identifies the secret.

    Returns:
        dict[str, str] | None: The secret content dict, or ``None`` if no matching secret exists.
    """
    label = f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}"
    try:
        secret = charm.model.get_secret(label=label)
        return secret.get_content(refresh=True)
    except ops.SecretNotFoundError:
        return None


def revoke_csr_mapping(charm: ops.CharmBase, csr_pem: str) -> None:
    """Remove the mapping secret for a CSR.  No-op if the secret does not exist.

    Args:
        charm (ops.CharmBase): The charm instance used to access the model.
        csr_pem (str): PEM-encoded CSR whose fingerprint identifies the secret to remove.
    """
    label = f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}"
    try:
        secret = charm.model.get_secret(label=label)
        secret.remove_all_revisions()
        logger.debug("Revoked CSR mapping secret %r", label)
    except ops.SecretNotFoundError:
        logger.debug("No CSR mapping secret %r to revoke (no-op)", label)
