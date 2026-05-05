# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import ops
from pydantic import BaseModel, ConfigDict

from config import CharmConfig  # noqa: TC001
from models import CertificateRequest, IssuedCertificate  # noqa: TC001
from new_tls_certificate import NewTLSCertificatesRelation  # noqa: TC001
from old_tls_certificate import OldTLSCertificatesRelation  # noqa: TC001

logger = logging.getLogger(__name__)


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    model_config = ConfigDict(frozen=True)

    certificate_requests: list[CertificateRequest]
    issued_certificates: dict[str, IssuedCertificate]  # keyed by CSR SHA-256 hex fingerprint
    extra_ca_certificates: str = ""

    def build_full_ca_pem(self, ca: str, chain: list[str], leaf_pem: str) -> str:
        """Build a full CA certificate bundle from provider data and charm config.

        Strips the leaf cert from *chain*, then appends any CA certs not already
        present in *ca*.  Finally appends the operator-supplied ``ca-certificates``
        config (e.g. a root CA missing from the upstream provider's chain) if set.

        Args:
            ca (str): PEM-encoded CA certificate from the upstream provider.
            chain (list[str]): List of PEM-encoded certificates from the upstream provider.
            leaf_pem (str): PEM string of the leaf certificate to exclude from the chain.

        Returns:
            str: PEM bundle containing all CA certs needed to verify the leaf cert.
        """
        # Build the full CA chain (all CA certs from immediate issuer to root) by
        # stripping the leaf cert from chain.  The old reactive tls-certificates (v1)
        # interface only reads the "ca" key and ignores "chain", so we concatenate all
        # CA certs into a single PEM bundle.
        ca_certs = [c for c in chain if c != leaf_pem] if chain else []
        full_ca_pem = ca
        for cert_pem in ca_certs:
            stripped = cert_pem.strip()
            if stripped not in full_ca_pem:
                full_ca_pem = full_ca_pem + "\n" + stripped
        # Append any operator-supplied extra CA certs (e.g. the root CA when the upstream
        # provider only delivers an intermediate CA and does not include the root in chain).
        if self.extra_ca_certificates and self.extra_ca_certificates not in full_ca_pem:
            full_ca_pem = full_ca_pem + "\n" + self.extra_ca_certificates
        return full_ca_pem

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
        old_handler: OldTLSCertificatesRelation,
        upstream: NewTLSCertificatesRelation,
    ) -> CharmState:
        """Build a CharmState from the charm instance and pre-constructed relation handlers.

        Loads charm configuration and aggregates relation data into a single
        state object.  Accepts handlers rather than instantiating them here
        (dependency injection).

        Args:
            charm (ops.CharmBase): The charm instance, used to load configuration.
            old_handler (OldTLSCertificatesRelation): Handler for all active old-interface (v1) relations.
                Reads cert requests from all remote-unit databags across every
                active relation.
            upstream (NewTLSCertificatesRelation): Handler for the modern upstream tls-certificates (v4)
                relation.  Provides currently-issued certificates.

        Returns:
            CharmState: A CharmState with all pending certificate requests, currently
                issued certificates, and resolved configuration.
        """
        charm_config = CharmConfig.from_charm(charm)
        return cls(
            certificate_requests=old_handler.get_certificate_requests(),
            issued_certificates=upstream.get_issued_certificates(),
            extra_ca_certificates=charm_config.ca_certificates,
        )


class CharmBaseWithState(ops.CharmBase, ABC):
    """CharmBase that can build a CharmState."""

    @property
    @abstractmethod
    def state(self) -> CharmState | None:
        """The charm state."""

    @abstractmethod
    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Reconcile configuration."""
