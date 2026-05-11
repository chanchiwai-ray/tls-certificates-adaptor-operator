# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""New tls-certificates interface (v4): wraps TLSCertificatesRequiresV4 for the modern interface.

The "new" interface is the ``tls-certificates-interface`` charmlib
(``TLSCertificatesRequiresV4``, i.e. v4) implemented by modern TLS providers
such as vault-k8s and lego-k8s.  In this protocol the *requirer* generates its
own private key, sends a Certificate Signing Request (CSR), and receives back
only the signed certificate together with the CA and chain.  The library
handles CSR submission, renewal scheduling, and event dispatch.

Certificate renewal is managed internally by the library: when ``secret_expired``
fires for a provider-managed secret, or when a ``refresh_events`` hook runs,
the library automatically re-submits the CSR.  The adaptor charm does not need
to implement any explicit renewal logic.

This module provides :class:`NewTLSCertificatesRelation`, which wraps the
library to expose only the operations needed by the adaptor charm.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import ops
from charmlibs.interfaces.tls_certificates import (
    CertificateAvailableEvent,
    CertificateRequestAttributes,
    TLSCertificatesRequiresV4,
)

from constants import OLD_INTERFACE_RELATION_NAME, UPSTREAM_RELATION_NAME
from crypto import build_ca_bundle, classify_sans

if TYPE_CHECKING:
    from models import CertificateRequest
    from old_tls_certificate import OldTLSCertificatesRelation

logger = logging.getLogger(__name__)


class NewTLSCertificatesRelation:
    """Manages interactions with the upstream modern tls-certificates (v4) provider.

    Wraps :class:`~charmlibs.interfaces.tls_certificates.TLSCertificatesRequiresV4`
    to expose only the operations needed by the adaptor charm.
    """

    def __init__(self, charm: ops.CharmBase) -> None:
        """Initialise the upstream relation handler.

        Args:
            charm (ops.CharmBase): The charm instance.
        """
        self._charm = charm
        self._tls = TLSCertificatesRequiresV4(
            charm=charm,
            relationship_name=UPSTREAM_RELATION_NAME,
            certificate_requests=[],
        )

    @property
    def tls_certificates(self) -> TLSCertificatesRequiresV4:
        """The underlying TLSCertificatesRequiresV4 library instance."""
        return self._tls

    def update_certificate_requests(self, requests: list[CertificateRequest]) -> None:
        """Update the upstream library's certificate requests and sync.

        Converts :class:`~models.CertificateRequest` objects to
        :class:`~charmlibs.interfaces.tls_certificates.CertificateRequestAttributes`,
        assigns them to the library, and calls ``sync()`` to submit new CSRs
        and clean up stale ones.

        Args:
            requests (list[CertificateRequest]): The current set of certificate requests
                from the old-interface handler.
        """
        attrs = []
        for cr in requests:
            dns_sans, ip_sans = classify_sans(cr.sans)
            attrs.append(
                CertificateRequestAttributes(
                    common_name=cr.common_name,
                    sans_dns=dns_sans if dns_sans else None,
                    sans_ip=ip_sans if ip_sans else None,
                    add_unique_id_to_subject_name=False,
                )
            )
        self._tls.certificate_requests = attrs
        self._tls.sync()

    def handle_certificate_available(
        self,
        event: CertificateAvailableEvent,
        old_handler: OldTLSCertificatesRelation,
        extra_ca_certificates: str,
    ) -> None:
        """Deliver a signed certificate to the old-interface requirer.

        Re-parses live old-interface relation data to find the matching
        :class:`~models.CertificateRequest` by ``(common_name, sans)``, then
        writes the cert, key, and CA to the requirer's relation databag.

        Logs an error and returns gracefully if no matching request is found
        or if the old-interface relation is no longer active.

        Args:
            event (CertificateAvailableEvent): The certificate available event.
            old_handler (OldTLSCertificatesRelation): Handler for writing to old-interface relations.
            extra_ca_certificates (str): Optional extra PEM-encoded CA certs to append
                to the CA bundle (from charm config).
        """
        csr = event.certificate_signing_request
        common_name = str(csr.common_name)
        sans = sorted((csr.sans_dns or set()) | (csr.sans_ip or set()))

        # Re-derive routing from live relation data.
        matched: CertificateRequest | None = None
        for cr in old_handler.get_certificate_requests():
            if cr.common_name == common_name and sorted(cr.sans) == sans:
                matched = cr
                break

        if matched is None:
            logger.error(
                "No matching certificate request found for CN=%r sans=%r; skipping delivery",
                common_name,
                sans,
            )
            return

        relation: ops.Relation | None = None
        with contextlib.suppress(ops.RelationNotFoundError):
            relation = self._charm.model.get_relation(
                OLD_INTERFACE_RELATION_NAME, matched.relation_id
            )
        if relation is None or not relation.active:
            logger.info(
                "Old-interface relation %d no longer active; skipping delivery for CN=%r",
                matched.relation_id,
                common_name,
            )
            return

        leaf_pem = str(event.certificate)
        full_ca_pem = build_ca_bundle(
            str(event.ca),
            [str(c) for c in event.chain],
            leaf_pem,
            extra_ca_certificates,
        )
        key = str(self._tls.private_key)

        if matched.is_client:
            old_handler.write_client_cert(
                relation_id=matched.relation_id,
                cert=leaf_pem,
                key=key,
            )
        else:
            old_handler.write_certificate(
                relation_id=matched.relation_id,
                requirer_unit_name=matched.requirer_unit_name,
                common_name=common_name,
                cert=leaf_pem,
                key=key,
                ca=full_ca_pem,
                is_legacy=matched.is_legacy,
            )
        old_handler.write_ca(ca=full_ca_pem)
