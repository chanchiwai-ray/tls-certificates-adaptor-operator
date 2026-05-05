# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import ops
from pydantic import BaseModel, ConfigDict

from config import CharmConfig
from models import CertificateRequest  # noqa: TC001
from old_tls_certificate import OldTLSCertificatesRelation  # noqa: TC001

logger = logging.getLogger(__name__)


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    model_config = ConfigDict(frozen=True)

    certificate_requests: list[CertificateRequest]
    csr_fingerprints: dict[int, list[str]] = {}  # keyed by relation_id
    extra_ca_certificates: str = ""

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
        old_handler: OldTLSCertificatesRelation,
    ) -> CharmState:
        """Build a CharmState from the charm instance and the old-interface relation handler.

        Loads charm configuration and aggregates relation data into a single
        state object.  Accepts the handler rather than instantiating it here
        (dependency injection).

        Args:
            charm (ops.CharmBase): The charm instance, used to load configuration.
            old_handler (OldTLSCertificatesRelation): Handler for all active old-interface (v1) relations.
                Reads cert requests from all remote-unit databags across every
                active relation.

        Returns:
            CharmState: A CharmState with all pending certificate requests and resolved configuration.
        """
        charm_config = CharmConfig.from_charm(charm)
        certificate_requests = old_handler.get_certificate_requests()
        return cls(
            certificate_requests=certificate_requests,
            csr_fingerprints=old_handler.get_csr_fingerprints(certificate_requests),
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
