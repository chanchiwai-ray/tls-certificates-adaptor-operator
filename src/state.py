# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import ops
from pydantic import BaseModel, ConfigDict

from certificate_provider import CertificateRequest, IssuedCertificate, get_certificate_requests
from constants import OLD_INTERFACE_RELATION_NAME

logger = logging.getLogger(__name__)


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    model_config = ConfigDict(frozen=True)

    certificate_requests: list[CertificateRequest]
    issued_certificates: dict[str, IssuedCertificate]  # keyed by CSR SHA-256 hex fingerprint

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> CharmState:
        """Build a CharmState by aggregating all active old-interface certificate requests.

        Args:
            charm: The charm instance.

        Returns:
            A CharmState with all pending certificate requests.
        """
        requests: list[CertificateRequest] = []
        for relation in charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
            requests.extend(get_certificate_requests(relation))
        return cls(certificate_requests=requests, issued_certificates={})


class CharmBaseWithState(ops.CharmBase, ABC):
    """CharmBase that can build a CharmState."""

    @property
    @abstractmethod
    def state(self) -> CharmState | None:
        """The charm state."""

    @abstractmethod
    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Reconcile configuration."""
