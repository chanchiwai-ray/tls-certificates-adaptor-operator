#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more at: https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/#build-a-charm

"""TLS Certificate Adaptor charm."""

import logging
import typing

import ops
from charmlibs.interfaces.tls_certificates import CertificateAvailableEvent

from constants import (
    OLD_INTERFACE_RELATION_NAME,
    UPSTREAM_RELATION_NAME,
)
from crypto import build_ca_bundle
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
        self.tls_certificates = self._upstream_handler.tls_certificates

        self.framework.observe(self.on.install, self.reconcile)
        self.framework.observe(self.on.config_changed, self.reconcile)
        self.framework.observe(self.on.upgrade_charm, self.reconcile)
        self.framework.observe(
            self.on[OLD_INTERFACE_RELATION_NAME].relation_changed,
            self.reconcile,
        )
        self.framework.observe(
            self.on[OLD_INTERFACE_RELATION_NAME].relation_broken,
            self._on_certificates_relation_broken,
        )
        self.framework.observe(
            self.on[UPSTREAM_RELATION_NAME].relation_joined,
            self.reconcile,
        )
        self.framework.observe(
            self.tls_certificates.on.certificate_available,
            self._on_certificate_available,
        )

    @property
    def state(self) -> CharmState:
        """The charm state, computed once per event and cached for the lifetime of this instance."""
        if self._state is None:
            self._state = CharmState.from_charm(self, self._old_handler)
        return self._state

    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Process all old-interface relations and set unit status.

        Called from every event handler.  Idempotently submits certificate
        requests to the upstream provider, writes the CA bundle when upstream
        provider certificates are available, then updates the unit status.

        Sets BlockedStatus when either the upstream TLS provider relation or
        the old-interface relation is absent, otherwise ActiveStatus.
        """
        if not self.model.relations[UPSTREAM_RELATION_NAME]:
            self.unit.status = ops.BlockedStatus("Missing upstream TLS provider relation")
            return
        if not self.model.relations[OLD_INTERFACE_RELATION_NAME]:
            self.unit.status = ops.BlockedStatus("Missing old TLS interface relation")
            return

        requests = self._old_handler.get_certificate_requests()
        self._upstream_handler.update_certificate_requests(requests)

        if provider_certs := self.tls_certificates.get_provider_certificates():
            first = provider_certs[0]
            full_ca_pem = build_ca_bundle(
                str(first.ca),
                [str(c) for c in first.chain],
                str(first.certificate),
                self.state.extra_ca_certificates,
            )
            self._old_handler.write_ca(ca=full_ca_pem)

        self.unit.status = ops.ActiveStatus()

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Deliver a signed certificate to the old-interface requirer.

        Delegates to the upstream handler which re-parses live relation data
        to find the matching requirer and writes the cert, key, and CA to its
        relation databag.
        """
        self._upstream_handler.handle_certificate_available(
            event,
            self._old_handler,
            self.state.extra_ca_certificates,
        )
        self.unit.status = ops.ActiveStatus()

    def _on_certificates_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle a broken old-interface relation.

        Calls reconcile so that the upstream library cleans up any CSRs that
        were associated with the broken relation.
        """
        self.reconcile()


if __name__ == "__main__":  # pragma: nocover
    ops.main(TLSCertificateAdaptorCharm)
