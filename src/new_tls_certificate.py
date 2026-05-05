# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""New tls-certificates interface (v4): wraps TLSCertificatesRequiresV4 for the modern interface.

The "new" interface is the ``tls-certificates-interface`` charmlib
(``TLSCertificatesRequiresV4``, i.e. v4) implemented by modern TLS providers
such as vault-k8s and lego-k8s.  In this protocol the *requirer* generates its
own private key, sends a Certificate Signing Request (CSR), and receives back
only the signed certificate together with the CA and chain.  The library
handles CSR submission, renewal scheduling, and event dispatch.

This module provides :class:`NewTLSCertificatesRelation`, which wraps the
library to expose only the operations needed by the adaptor charm and
translates :class:`~charmlibs.interfaces.tls_certificates.ProviderCertificate`
objects into the shared :class:`~old_tls_certificate.IssuedCertificate` model
consumed by :class:`~state.CharmState`.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import ops
from charmlibs.interfaces.tls_certificates import (
    CertificateAvailableEvent,
    CertificateDeniedEvent,
    CertificateRequestAttributes,
    PrivateKey,
    ProviderCertificate,
    TLSCertificatesRequiresV4,
)

from constants import (
    JUJU_SECRET_IS_CLIENT_KEY,
    JUJU_SECRET_IS_LEGACY_KEY,
    OLD_INTERFACE_RELATION_NAME,
    UPSTREAM_RELATION_NAME,
)
from crypto import build_ca_bundle, classify_sans, csr_sha256_hex
from models import CertificateRequest, IssuedCertificate
from secret import get_csr_mapping, revoke_csr_mapping

if TYPE_CHECKING:
    from old_tls_certificate import OldTLSCertificatesRelation

logger = logging.getLogger(__name__)


class NewTLSCertificatesRelation:
    """Manages interactions with the upstream modern tls-certificates (v4) provider.

    Wraps :class:`~charmlibs.interfaces.tls_certificates.TLSCertificatesRequiresV4`
    to expose only the operations needed by the adaptor charm, and translates
    provider certificates into the shared :class:`~models.IssuedCertificate`
    model used by :class:`~state.CharmState`.
    """

    def __init__(
        self,
        charm: ops.CharmBase,
        private_key_pem: str,
        certificate_requests: list[CertificateRequest] | None = None,
    ) -> None:
        """Initialise the upstream relation handler.

        Args:
            charm (ops.CharmBase): The charm instance.
            private_key_pem (str): PEM-encoded private key for the upstream CSR.
            certificate_requests (list[CertificateRequest] | None): The current set of certificate
                requests from the old-interface handler, used to seed the upstream library.
                Defaults to an empty list when not provided.
        """
        self._charm = charm
        cert_request_attrs = []
        for cr in certificate_requests or []:
            dns_sans, ip_sans = classify_sans(cr.sans)
            cert_request_attrs.append(
                CertificateRequestAttributes(
                    common_name=cr.common_name,
                    sans_dns=dns_sans if dns_sans else None,
                    sans_ip=ip_sans if ip_sans else None,
                    add_unique_id_to_subject_name=False,
                )
            )
        self._tls = TLSCertificatesRequiresV4(
            charm=charm,
            relationship_name=UPSTREAM_RELATION_NAME,
            certificate_requests=cert_request_attrs,
            private_key=PrivateKey.from_string(private_key_pem),
            refresh_events=[
                charm.on[OLD_INTERFACE_RELATION_NAME].relation_changed,
                charm.on.upgrade_charm,
            ],
        )

    @property
    def tls_certificates(self) -> TLSCertificatesRequiresV4:
        """The underlying TLSCertificatesRequiresV4 library instance."""
        return self._tls

    def get_provider_certificates(self) -> list[ProviderCertificate]:
        """Return all provider certificates currently assigned by the upstream provider.

        Returns:
            list[ProviderCertificate]: A list of ProviderCertificate objects from the upstream (v4) relation.
        """
        return self._tls.get_provider_certificates()

    def get_issued_certificates(self) -> dict[str, IssuedCertificate]:
        """Return issued certificates keyed by CSR SHA-256 hex fingerprint.

        Maps each :class:`~charmlibs.interfaces.tls_certificates.ProviderCertificate`
        returned by the upstream (v4) library into an
        :class:`~old_tls_certificate.IssuedCertificate` and keys it by the
        SHA-256 hex fingerprint of the corresponding CSR.

        Returns:
            dict[str, IssuedCertificate]: A dict mapping CSR fingerprint to IssuedCertificate for each
                certificate currently assigned by the upstream provider.
        """
        issued: dict[str, IssuedCertificate] = {}
        for pc in self._tls.get_provider_certificates():
            fingerprint = csr_sha256_hex(str(pc.certificate_signing_request))
            issued[fingerprint] = IssuedCertificate(
                certificate=str(pc.certificate),
                ca=str(pc.ca),
                chain=[str(c) for c in pc.chain],
            )
        return issued

    def renew_certificate(self, certificate: ProviderCertificate) -> None:
        """Request renewal of an existing certificate from the upstream (v4) provider.

        Args:
            certificate (ProviderCertificate): The ProviderCertificate to renew.
        """
        self._tls.renew_certificate(certificate)

    def handle_certificate_available(
        self,
        event: CertificateAvailableEvent,
        old_handler: OldTLSCertificatesRelation,
        extra_ca_certificates: str,
    ) -> None:
        """Deliver a signed certificate to the old-interface requirer.

        Looks up the per-CSR mapping secret, builds the full CA bundle, then
        writes the cert and key to the old-interface requirer's relation databag.
        The mapping secret is intentionally retained so that library-managed
        renewal can reuse it when the same CSR fingerprint fires a new
        ``certificate_available``.  Logs an error and skips gracefully if the
        mapping is missing.  Revokes the mapping and logs at INFO if the
        old-interface relation is gone.

        Args:
            event (CertificateAvailableEvent): The certificate available event.
            old_handler (OldTLSCertificatesRelation): Handler for writing to old-interface relations.
            extra_ca_certificates (str): Optional extra PEM-encoded CA certs to append
                to the CA bundle (from charm config).
        """
        csr_pem = str(event.certificate_signing_request)
        mapping = get_csr_mapping(self._charm, csr_pem)
        if mapping is None:
            logger.error(
                "No CSR mapping found for certificate (CN=%s); skipping delivery",
                event.certificate.common_name,
            )
            return

        relation_id = int(mapping["relation-id"])
        requirer_unit_name = mapping["requirer-unit"]
        private_key_pem = mapping["private-key"]
        is_legacy = mapping.get(JUJU_SECRET_IS_LEGACY_KEY, "false") == "true"
        is_client = mapping.get(JUJU_SECRET_IS_CLIENT_KEY, "false") == "true"

        relation = None
        with contextlib.suppress(ops.RelationNotFoundError):
            relation = self._charm.model.get_relation(OLD_INTERFACE_RELATION_NAME, relation_id)
        if relation is None or not relation.active:
            logger.info(
                "Old-interface relation %d no longer exists; revoking mapping for %s",
                relation_id,
                requirer_unit_name,
            )
            revoke_csr_mapping(self._charm, csr_pem)
            return

        leaf_pem = str(event.certificate)
        full_ca_pem = build_ca_bundle(
            str(event.ca),
            [str(c) for c in event.chain],
            leaf_pem,
            extra_ca_certificates,
        )

        if is_client:
            old_handler.write_client_cert(
                relation_id=relation_id,
                cert=str(event.certificate),
                key=private_key_pem,
            )
        else:
            old_handler.write_certificate(
                relation_id=relation_id,
                requirer_unit_name=requirer_unit_name,
                common_name=str(event.certificate.common_name),
                cert=str(event.certificate),
                key=private_key_pem,
                ca=full_ca_pem,
                is_legacy=is_legacy,
            )
        old_handler.write_ca(ca=full_ca_pem)

    def handle_certificate_denied(self, event: CertificateDeniedEvent) -> None:
        """Handle a denied certificate request from the upstream TLS provider.

        Revokes the mapping secret for the denied CSR and logs the error so
        the operator can investigate.  The old-interface requirer is left in
        its current state; no data is written to the relation databag.

        Args:
            event (CertificateDeniedEvent): The certificate denied event.
        """
        csr_pem = str(event.certificate_signing_request)
        mapping = get_csr_mapping(self._charm, csr_pem)
        if mapping is None:
            logger.warning(
                "certificate_denied: no mapping found for denied CSR \u2014 already cleaned up"
            )
            return
        revoke_csr_mapping(self._charm, csr_pem)
        logger.error(
            "Certificate request denied for %s (error: %s); mapping revoked",
            mapping.get("requirer-unit", "unknown"),
            event.error,
        )
