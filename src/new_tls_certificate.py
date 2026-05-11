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
    CertificateSigningRequest,
    PrivateKey,
    ProviderCertificate,
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

    def get_provider_certificates(self) -> list[ProviderCertificate]:
        """Return all currently issued provider certificates.

        Returns:
            list[ProviderCertificate]: Issued certificates from the upstream provider,
                or an empty list if none have been issued yet.
        """
        return self._tls.get_provider_certificates()

    def get_private_key(self) -> PrivateKey | None:
        """Return the library-managed private key for this unit, or None if unavailable.

        Returns:
            PrivateKey | None: The unit private key, or None if the upstream relation
                has not been established yet.
        """
        return self._tls.private_key

    def update_certificate_requests(self, requests: list[CertificateRequest]) -> None:
        """Update the upstream library's certificate requests and sync.

        Converts :class:`~models.CertificateRequest` objects to
        :class:`~charmlibs.interfaces.tls_certificates.CertificateRequestAttributes`,
        assigns them to the library, and calls ``sync()`` to submit new CSRs
        and clean up stale ones.

        Deduplicates by ``(common_name, sorted_dns_sans, sorted_ip_sans)`` so
        that multiple requirer units requesting the same CN+SANs result in only
        one upstream CSR.

        Args:
            requests (list[CertificateRequest]): The current set of certificate requests
                from the old-interface handler.
        """
        seen: set[tuple] = set()
        attrs = []
        for cr in requests:
            dns_sans, ip_sans = classify_sans(cr.sans)
            key = (
                cr.common_name,
                tuple(sorted(dns_sans)),
                tuple(sorted(ip_sans)),
            )
            if key in seen:
                continue
            seen.add(key)
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

    def deliver_certificates(
        self,
        provider_certificates: list[ProviderCertificate],
        certificate_requests: list[CertificateRequest],
        private_key: PrivateKey | None,
        old_handler: OldTLSCertificatesRelation,
        extra_ca_certificates: str,
    ) -> None:
        """Deliver all currently available provider certificates to old-interface requirers.

        Iterates every :class:`~charmlibs.interfaces.tls_certificates.ProviderCertificate`
        and calls :meth:`_deliver_one` for each, ensuring that every old-interface
        requirer unit whose request matches an issued certificate receives the cert,
        key, and CA — even if they joined the relation after the original
        ``certificate_available`` event fired.

        Also writes the CA bundle to all old-interface relations unconditionally
        when at least one provider certificate exists, so that requirers that
        have not yet submitted a cert request still receive the CA.

        Args:
            provider_certificates (list[ProviderCertificate]): Currently issued
                certificates from the upstream provider.
            certificate_requests (list[CertificateRequest]): All pending cert requests
                from old-interface requirer unit databags.
            private_key (PrivateKey | None): The library-managed unit private key.
            old_handler (OldTLSCertificatesRelation): Handler for writing to old-interface
                relations.
            extra_ca_certificates (str): Optional extra PEM-encoded CA certs to append
                to the CA bundle (from charm config).
        """
        if private_key is None:
            logger.debug("Private key not yet available; skipping certificate delivery")
            return

        for pc in provider_certificates:
            self._deliver_one(
                csr=pc.certificate_signing_request,
                certificate_pem=str(pc.certificate),
                ca_pem=str(pc.ca),
                chain_pems=[str(c) for c in pc.chain],
                certificate_requests=certificate_requests,
                private_key=private_key,
                old_handler=old_handler,
                extra_ca_certificates=extra_ca_certificates,
            )

        if provider_certificates:
            first = provider_certificates[0]
            full_ca_pem = build_ca_bundle(
                str(first.ca),
                [str(c) for c in first.chain],
                str(first.certificate),
                extra_ca_certificates,
            )
            old_handler.write_ca(ca=full_ca_pem)

    def handle_certificate_available(
        self,
        event: CertificateAvailableEvent,
        certificate_requests: list[CertificateRequest],
        private_key: PrivateKey | None,
        old_handler: OldTLSCertificatesRelation,
        extra_ca_certificates: str,
    ) -> None:
        """Deliver a signed certificate to the old-interface requirer.

        Matches the event's CSR against the pre-fetched ``certificate_requests``
        snapshot and writes the cert, key, and CA to all matching requirer
        relation databags.

        Logs an error and returns gracefully if no matching request is found or
        if the private key is unavailable.

        Args:
            event (CertificateAvailableEvent): The certificate available event.
            certificate_requests (list[CertificateRequest]): All pending cert requests
                from old-interface requirer unit databags.
            private_key (PrivateKey | None): The library-managed unit private key.
            old_handler (OldTLSCertificatesRelation): Handler for writing to old-interface
                relations.
            extra_ca_certificates (str): Optional extra PEM-encoded CA certs to append
                to the CA bundle (from charm config).
        """
        ca_pem = str(event.ca)
        chain_pems = [str(c) for c in event.chain]
        certificate_pem = str(event.certificate)
        delivered = self._deliver_one(
            csr=event.certificate_signing_request,
            certificate_pem=certificate_pem,
            ca_pem=ca_pem,
            chain_pems=chain_pems,
            certificate_requests=certificate_requests,
            private_key=private_key,
            old_handler=old_handler,
            extra_ca_certificates=extra_ca_certificates,
        )
        if delivered:
            full_ca_pem = build_ca_bundle(ca_pem, chain_pems, certificate_pem, extra_ca_certificates)
            old_handler.write_ca(ca=full_ca_pem)

    def _deliver_one(
        self,
        csr: CertificateSigningRequest,
        certificate_pem: str,
        ca_pem: str,
        chain_pems: list[str],
        certificate_requests: list[CertificateRequest],
        private_key: PrivateKey | None,
        old_handler: OldTLSCertificatesRelation,
        extra_ca_certificates: str,
    ) -> bool:
        """Deliver one certificate to all matching old-interface requirer units.

        Matches on ``(common_name, sorted_sans)`` against the pre-fetched
        ``certificate_requests`` snapshot so that the same cert is delivered to
        every requirer unit that requested it (e.g. ``keystone/0``, ``keystone/1``,
        ``keystone/2`` on the same relation).

        Args:
            csr (CertificateSigningRequest): The CSR the certificate was issued for.
            certificate_pem (str): PEM-encoded signed leaf certificate.
            ca_pem (str): PEM-encoded CA certificate.
            chain_pems (list[str]): PEM-encoded intermediate certificates.
            certificate_requests (list[CertificateRequest]): Pre-fetched snapshot of
                all pending old-interface cert requests.
            private_key (PrivateKey | None): The library-managed unit private key.
            old_handler (OldTLSCertificatesRelation): Handler for writing to old-interface
                relations.
            extra_ca_certificates (str): Optional extra PEM-encoded CA certs to append.

        Returns:
            bool: True if at least one certificate was written; False if delivery was
                skipped (no matching request or private key unavailable).
        """
        common_name = str(csr.common_name)
        sans = sorted((csr.sans_dns or set()) | (csr.sans_ip or set()))

        # Collect ALL matching requests: the same (CN, SANs) may be requested
        # by multiple requirer units and every one must receive the certificate.
        matched: list[CertificateRequest] = [
            cr
            for cr in certificate_requests
            if cr.common_name == common_name and sorted(cr.sans) == sans
        ]

        if not matched:
            logger.error(
                "No matching certificate request found for CN=%r sans=%r; skipping delivery",
                common_name,
                sans,
            )
            return False

        if private_key is None:
            logger.error(
                "Private key not yet available for CN=%r; skipping delivery",
                common_name,
            )
            return False

        full_ca_pem = build_ca_bundle(ca_pem, chain_pems, certificate_pem, extra_ca_certificates)
        key = str(private_key)

        for cr in matched:
            relation: ops.Relation | None = None
            with contextlib.suppress(ops.RelationNotFoundError):
                relation = self._charm.model.get_relation(
                    OLD_INTERFACE_RELATION_NAME, cr.relation_id
                )
            if relation is None or not relation.active:
                logger.info(
                    "Old-interface relation %d no longer active; skipping delivery for CN=%r",
                    cr.relation_id,
                    common_name,
                )
                continue

            if cr.is_client:
                old_handler.write_client_cert(
                    relation_id=cr.relation_id,
                    cert=certificate_pem,
                    key=key,
                )
            else:
                old_handler.write_certificate(
                    relation_id=cr.relation_id,
                    requirer_unit_name=cr.requirer_unit_name,
                    common_name=common_name,
                    cert=certificate_pem,
                    key=key,
                    ca=full_ca_pem,
                    is_legacy=cr.is_legacy,
                )
        return True
