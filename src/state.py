# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Charm state: single source of truth for all adaptor data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import ops
from pydantic import BaseModel, ConfigDict

from config import CharmConfig

logger = logging.getLogger(__name__)


class CharmState(BaseModel):
    """Single source of truth for all adaptor data."""

    model_config = ConfigDict(frozen=True)

    extra_ca_certificates: str = ""

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> CharmState:
        """Build a CharmState from the charm instance.

        Loads charm configuration into a single state object.

        Args:
            charm (ops.CharmBase): The charm instance, used to load configuration.

        Returns:
            CharmState: A CharmState with resolved configuration.
        """
        charm_config = CharmConfig.from_charm(charm)
        return cls(extra_ca_certificates=charm_config.ca_certificates)


class CharmBaseWithState(ops.CharmBase, ABC):
    """CharmBase that can build a CharmState."""

    @property
    @abstractmethod
    def state(self) -> CharmState | None:
        """The charm state."""

    @abstractmethod
    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Reconcile configuration."""
