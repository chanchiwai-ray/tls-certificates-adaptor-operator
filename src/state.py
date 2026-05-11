# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import ops
from charmlibs.interfaces.tls_certificates import PrivateKey, ProviderCertificate
from pydantic import BaseModel, ConfigDict

from config import CharmConfig
from models import CertificateRequest  # noqa: TC001

if TYPE_CHECKING:
    from new_tls_certificate import NewTLSCertificatesRelation
    from old_tls_certificate import OldTLSCertificatesRelation

logger = logging.getLogger(__name__)


class CharmState(BaseModel):
    """Single source of truth for all adaptor data.

    Built once per event by :meth:`from_charm` and treated as an immutable
    snapshot of the world for the duration of that hook execution.

    Attributes:
        certificate_requests: All pending cert requests read from old-interface
            requirer unit databags.  Empty when no old-interface relation exists
            or no requirer has submitted a request yet.
        provider_certificates: All currently issued certificates from the upstream
            TLS provider.  Empty until the provider has signed at least one CSR.
        private_key: The library-managed private key for this unit, or ``None``
            if the library has not yet generated it (e.g. no upstream relation).
        extra_ca_certificates: Optional extra PEM CA certs from charm config,
            appended to every CA bundle written to old-interface relations.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    certificate_requests: list[CertificateRequest] = []
    provider_certificates: list[ProviderCertificate] = []
    private_key: PrivateKey | None = None
    extra_ca_certificates: str = ""

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
        old_handler: OldTLSCertificatesRelation,
        upstream_handler: NewTLSCertificatesRelation,
    ) -> CharmState:
        """Build a CharmState snapshot from live charm and relation data.

        Reads all inputs eagerly so that the rest of the event handling operates
        on plain data rather than reaching back into relation handlers.

        Args:
            charm: The charm instance, used to load configuration.
            old_handler: Handler for old-interface (v1) relations; provides
                pending cert requests.
            upstream_handler: Handler for the upstream v4 relation; provides
                issued provider certificates and the unit private key.

        Returns:
            CharmState: Immutable snapshot valid for the current hook execution.
        """
        charm_config = CharmConfig.from_charm(charm)
        return cls(
            certificate_requests=old_handler.get_certificate_requests(),
            provider_certificates=upstream_handler.get_provider_certificates(),
            private_key=upstream_handler.get_private_key(),
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
