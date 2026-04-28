#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more at: https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/#build-a-charm

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

https://discourse.charmhub.io/t/4208
"""

import logging
import typing

import ops

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)


class Charm(ops.CharmBase):
    """Charm implementing holistic reconciliation pattern.

    The holistic pattern centralizes all state reconciliation logic into a single
    reconcile method that is called from all event handlers. This ensures consistency
    and reduces code duplication.
    See https://documentation.ubuntu.com/ops/latest/explanation/holistic-vs-delta-charms/
    for more information.
    """

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def reconcile(self) -> None:
        """Holistic reconciliation method.

        This method contains all the logic needed to reconcile the charm state.
        It is idempotent and can be called from any event handler.
        """
        # TODO: implement charm reconciliation logic here
        self.unit.status = ops.ActiveStatus()

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install event."""
        self.reconcile()

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle changed configuration."""
        self.reconcile()


if __name__ == "__main__":  # pragma: nocover
    ops.main(Charm)
