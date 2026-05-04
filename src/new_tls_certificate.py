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

import logging

import ops
from charmlibs.interfaces.tls_certificates import (
    CertificateRequestAttributes,
    PrivateKey,
    ProviderCertificate,
    TLSCertificatesRequiresV4,
)

from constants import OLD_INTERFACE_RELATION_NAME, UPSTREAM_RELATION_NAME
from crypto import classify_sans, csr_sha256_hex
from models import CertificateRequest, IssuedCertificate

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
        certificate_requests: list[CertificateRequest],
        private_key_pem: str,
    ) -> None:
        """Initialise the upstream relation handler.

        Args:
            charm: The charm instance.
            certificate_requests: The current set of certificate requests from
                the old-interface handler, used to seed the upstream library.
            private_key_pem: PEM-encoded private key for the upstream CSR.
        """
        self._charm = charm
        cert_request_attrs = []
        for cr in certificate_requests:
            dns_sans, ip_sans = classify_sans(cr.sans_dns)
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
            A list of ProviderCertificate objects from the upstream (v4) relation.
        """
        return self._tls.get_provider_certificates()

    def get_issued_certificates(self) -> dict[str, IssuedCertificate]:
        """Return issued certificates keyed by CSR SHA-256 hex fingerprint.

        Maps each :class:`~charmlibs.interfaces.tls_certificates.ProviderCertificate`
        returned by the upstream (v4) library into an
        :class:`~old_tls_certificate.IssuedCertificate` and keys it by the
        SHA-256 hex fingerprint of the corresponding CSR.

        Returns:
            A dict mapping CSR fingerprint to IssuedCertificate for each
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
            certificate: The ProviderCertificate to renew.
        """
        self._tls.renew_certificate(certificate)
