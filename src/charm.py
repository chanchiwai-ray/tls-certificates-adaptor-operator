#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more at: https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/#build-a-charm

"""TLS Certificate Adaptor charm."""

import logging
import typing

import ops

from constants import OLD_INTERFACE_RELATION_NAME, UPSTREAM_RELATION_NAME
from state import CharmBaseWithState, CharmState

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)


class TLSCertificateAdaptorCharm(CharmBaseWithState):
    """TLS Certificate Adaptor implementing holistic reconciliation pattern.

    Bridges the legacy reactive tls-certificates interface with the modern
    tls-certificates-interface (charmlibs) used by vault-k8s or lego-k8s.

    See https://documentation.ubuntu.com/ops/latest/explanation/holistic-vs-delta-charms/
    for more information on the holistic reconcile pattern.
    """

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(
            self.on[OLD_INTERFACE_RELATION_NAME].relation_changed,
            self._on_certificates_relation_changed,
        )
        self.framework.observe(
            self.on[OLD_INTERFACE_RELATION_NAME].relation_broken,
            self._on_certificates_relation_broken,
        )

    @property
    def state(self) -> CharmState | None:
        """The charm state."""
        return CharmState.from_charm(self)

    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Holistic reconciliation method.

        Evaluates the current charm state and sets unit status accordingly.
        This method is idempotent and called from every event handler.
        """
        if not self.model.relations[UPSTREAM_RELATION_NAME]:
            self.unit.status = ops.WaitingStatus("Waiting for upstream TLS provider")
            return
        self.unit.status = ops.ActiveStatus()

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Handle install event."""
        self.reconcile(event)

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle changed configuration."""
        self.reconcile(event)

    def _on_certificates_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle old-interface relation changed."""
        self.reconcile(event)

    def _on_certificates_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle old-interface relation broken."""
        self.reconcile(event)


if __name__ == "__main__":  # pragma: nocover
    ops.main(TLSCertificateAdaptorCharm)
