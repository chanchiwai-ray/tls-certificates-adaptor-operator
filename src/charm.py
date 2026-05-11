#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more at: https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/#build-a-charm

"""TLS Certificate Adaptor charm."""

import logging
import typing

import ops

from constants import (
    OLD_INTERFACE_RELATION_NAME,
    UPSTREAM_RELATION_NAME,
)
from new_tls_certificate import NewTLSCertificatesRelation
from old_tls_certificate import OldTLSCertificatesRelation
from state import CharmBaseWithState, CharmState

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
            args (typing.Any): Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)

        self._state: CharmState | None = None

        self._old_handler = OldTLSCertificatesRelation(self)
        self._upstream_handler = NewTLSCertificatesRelation(self)

        self.framework.observe(self.on.install, self.reconcile)
        self.framework.observe(self.on.config_changed, self.reconcile)
        self.framework.observe(self.on.upgrade_charm, self.reconcile)
        self.framework.observe(
            self.on[OLD_INTERFACE_RELATION_NAME].relation_changed,
            self.reconcile,
        )
        self.framework.observe(
            self.on[OLD_INTERFACE_RELATION_NAME].relation_broken,
            self.reconcile,
        )
        self.framework.observe(
            self.on[UPSTREAM_RELATION_NAME].relation_changed,
            self.reconcile,
        )

    @property
    def state(self) -> CharmState:
        """The charm state, computed once per event and cached for the lifetime of this instance."""
        if self._state is None:
            self._state = CharmState.from_charm(self, self._old_handler, self._upstream_handler)
        return self._state

    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Process all old-interface relations and set unit status.

        Called from every event handler.  Idempotently submits certificate
        requests to the upstream provider and delivers issued certificates back
        to old-interface requirers, then updates the unit status.

        Sets BlockedStatus when either the upstream TLS provider relation or
        the old-interface relation is absent, otherwise ActiveStatus.
        """
        if not self.model.relations[UPSTREAM_RELATION_NAME]:
            self.unit.status = ops.BlockedStatus("Missing upstream TLS provider relation")
            return
        if not self.model.relations[OLD_INTERFACE_RELATION_NAME]:
            self.unit.status = ops.BlockedStatus("Missing old TLS interface relation")
            return

        state = self.state
        self._upstream_handler.update_certificate_requests(state.certificate_requests)
        self._upstream_handler.deliver_certificates(
            provider_certificates=state.provider_certificates,
            certificate_requests=state.certificate_requests,
            private_key=state.private_key,
            old_handler=self._old_handler,
            extra_ca_certificates=state.extra_ca_certificates,
        )

        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(TLSCertificateAdaptorCharm)
