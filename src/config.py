# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm config option module."""

import logging

import ops
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class InvalidCharmConfigError(Exception):
    """Exception raised when the charm configuration is invalid."""


class CharmConfig(BaseModel):
    """Pydantic model for charm configuration options.

    Attributes:
        ca_certificates (str): Extra CA certificates to append to the CA bundle.
    """

    model_config = ConfigDict(frozen=True)

    ca_certificates: str = ""

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "CharmConfig":
        """Build a CharmConfig from the charm's configuration.

        Args:
            charm (ops.CharmBase): The charm instance.

        Returns:
            CharmConfig: The charm configuration.
        """
        return cls(ca_certificates=str(charm.config.get("ca-certificates") or "").strip())
