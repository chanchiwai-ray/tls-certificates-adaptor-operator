# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

import ops
from pydantic import BaseModel, ConfigDict

from constants import OLD_INTERFACE_RELATION_NAME

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CertificateRequest(BaseModel):
    """A pending certificate request from an old-interface requirer unit."""

    model_config = ConfigDict(frozen=True)

    common_name: str
    sans_dns: list[str]
    cert_type: Literal["server"]
    requirer_unit_name: str
    relation_id: int


class IssuedCertificate(BaseModel):
    """A certificate issued by the upstream TLS provider and ready to deliver."""

    model_config = ConfigDict(frozen=True)

    certificate: str  # PEM
    ca: str  # PEM
    chain: list[str]  # list of PEM


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    model_config = ConfigDict(frozen=True)

    certificate_requests: list[CertificateRequest]
    issued_certificates: dict[str, IssuedCertificate]  # keyed by common_name

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "CharmState":
        """Build a CharmState by aggregating all active old-interface certificate requests.

        Args:
            charm: The charm instance.

        Returns:
            A CharmState with all pending certificate requests.
        """
        # Local import to avoid circular dependency with certificate_provider
        from certificate_provider import get_certificate_requests  # noqa: PLC0415

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
