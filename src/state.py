# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import ops
from pydantic import BaseModel, ConfigDict

from models import CertificateRequest, IssuedCertificate  # noqa: TC001
from new_tls_certificate import NewTLSCertificatesRelation  # noqa: TC001
from old_tls_certificate import OldTLSCertificatesRelation  # noqa: TC001

logger = logging.getLogger(__name__)


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    model_config = ConfigDict(frozen=True)

    certificate_requests: list[CertificateRequest]
    issued_certificates: dict[str, IssuedCertificate]  # keyed by CSR SHA-256 hex fingerprint

    @classmethod
    def from_charm(
        cls,
        old_handler: OldTLSCertificatesRelation,
        upstream: NewTLSCertificatesRelation,
    ) -> CharmState:
        """Build a CharmState from pre-constructed relation handlers.

        Accepts handlers rather than a raw charm instance so that the state
        module has no direct dependency on how the handlers are constructed
        (dependency injection).

        Args:
            old_handler (OldTLSCertificatesRelation): Handler for all active old-interface (v1) relations.
                Reads cert requests from all remote-unit databags across every
                active relation.
            upstream (NewTLSCertificatesRelation): Handler for the modern upstream tls-certificates (v4)
                relation.  Provides currently-issued certificates.

        Returns:
            A CharmState with all pending certificate requests and currently
            issued certificates.
        """
        return cls(
            certificate_requests=old_handler.get_certificate_requests(),
            issued_certificates=upstream.get_issued_certificates(),
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
