#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more at: https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/#build-a-charm

"""TLS Certificate Adaptor charm."""

import logging
import typing

import ops
from charmlibs.interfaces.tls_certificates import (
    CertificateRequestAttributes,
    PrivateKey,
    TLSCertificatesRequiresV4,
)

from constants import OLD_INTERFACE_RELATION_NAME, UPSTREAM_RELATION_NAME
from crypto import build_csr
from secret import get_csr_mapping, get_or_generate_private_key, store_csr_mapping
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

        # Retrieve (or generate) the stable RSA private key for this unit.
        # This single key is reused for all upstream CSRs so that certificate
        # fingerprints remain stable across charm restarts and events.
        self._charm_key_pem = get_or_generate_private_key(self)
        charm_key = PrivateKey.from_string(self._charm_key_pem)

        # Build the current list of CertificateRequestAttributes from the
        # pending old-interface requests so the upstream library can send
        # them to the upstream TLS provider.
        state = CharmState.from_charm(self)
        cert_request_attrs = [
            CertificateRequestAttributes(
                common_name=cr.common_name,
                sans_dns=cr.sans_dns if cr.sans_dns else None,
                add_unique_id_to_subject_name=False,
            )
            for cr in state.certificate_requests
        ]

        # Initialise the upstream TLS library with the current pending
        # requests and our stable private key.  Pass the old-interface
        # relation_changed event as a refresh trigger so the library
        # re-sends the updated CSR list whenever an old requirer changes.
        self.tls_certificates = TLSCertificatesRequiresV4(
            charm=self,
            relationship_name=UPSTREAM_RELATION_NAME,
            certificate_requests=cert_request_attrs,
            private_key=charm_key,
            refresh_events=[self.on[OLD_INTERFACE_RELATION_NAME].relation_changed],
        )

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
        self.framework.observe(
            self.on[UPSTREAM_RELATION_NAME].relation_joined,
            self._on_certificates_upstream_relation_joined,
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
        """Handle old-interface relation changed.

        For each new CertificateRequest that does not yet have a mapping
        secret, build the deterministic CSR from the charm's stable key and
        the request attributes, then store a mapping secret with the requirer
        information.  The upstream TLS library (initialised in ``__init__``)
        picks up the updated CSR list automatically via the ``refresh_events``
        hook.
        """
        state = CharmState.from_charm(self)
        for cr in state.certificate_requests:
            csr_pem = build_csr(self._charm_key_pem, cr.common_name, cr.sans_dns)
            if get_csr_mapping(self, csr_pem) is not None:
                logger.debug(
                    "CSR mapping already exists for %s (%s) — skipping",
                    cr.common_name,
                    cr.requirer_unit_name,
                )
                continue
            store_csr_mapping(
                self,
                csr_pem,
                self._charm_key_pem,
                cr.requirer_unit_name,
                cr.relation_id,
            )
            logger.info(
                "Stored CSR mapping for %s (%s) on relation %d",
                cr.common_name,
                cr.requirer_unit_name,
                cr.relation_id,
            )
        self.reconcile(event)

    def _on_certificates_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle old-interface relation broken."""
        self.reconcile(event)

    def _on_certificates_upstream_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Handle upstream TLS provider relation joined.

        The upstream TLS library's ``_configure`` fires automatically on
        relation events and re-sends all pending CSRs.  This handler updates
        the unit status via ``reconcile()``.
        """
        self.reconcile(event)


if __name__ == "__main__":  # pragma: nocover
    ops.main(TLSCertificateAdaptorCharm)
