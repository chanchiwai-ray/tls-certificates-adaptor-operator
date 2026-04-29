#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more at: https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/#build-a-charm

"""TLS Certificate Adaptor charm."""

import contextlib
import json
import logging
import typing

import ops
from charmlibs.interfaces.tls_certificates import (
    CertificateAvailableEvent,
    CertificateDeniedEvent,
    CertificateRequestAttributes,
    PrivateKey,
    TLSCertificatesRequiresV4,
)

from certificate_provider import write_certificate
from constants import (
    CSR_FINGERPRINTS_KEY,
    JUJU_SECRET_LABEL_PREFIX,
    OLD_INTERFACE_RELATION_NAME,
    UPSTREAM_RELATION_NAME,
)
from crypto import build_csr, csr_sha256_hex
from secret import (
    get_csr_mapping,
    get_or_generate_private_key,
    revoke_csr_mapping,
    store_csr_mapping,
)
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
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)

        self._state: CharmState | None = None
        self._charm_key_pem = get_or_generate_private_key(self)

        # Build CertificateRequestAttributes from the current old-interface
        # requests so the upstream library sends them on initialisation.
        cert_request_attrs = []
        if state := self.state:
            cert_request_attrs = [
                CertificateRequestAttributes(
                    common_name=cr.common_name,
                    sans_dns=cr.sans_dns if cr.sans_dns else None,
                    add_unique_id_to_subject_name=False,
                )
                for cr in state.certificate_requests
            ]

        self.tls_certificates = TLSCertificatesRequiresV4(
            charm=self,
            relationship_name=UPSTREAM_RELATION_NAME,
            certificate_requests=cert_request_attrs,
            private_key=PrivateKey.from_string(self._charm_key_pem),
            refresh_events=[self.on[OLD_INTERFACE_RELATION_NAME].relation_changed],
        )

        self.framework.observe(self.on.install, self.reconcile)
        self.framework.observe(self.on.config_changed, self.reconcile)
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
            self.reconcile,
        )
        self.framework.observe(
            self.tls_certificates.on.certificate_available,
            self._on_certificate_available,
        )
        self.framework.observe(
            self.tls_certificates.on.certificate_denied,
            self._on_certificate_denied,
        )

    @property
    def state(self) -> CharmState | None:
        """The charm state, computed once per event and cached for the lifetime of this instance."""
        if self._state is None:
            self._state = CharmState.from_charm(self)
        return self._state

    def reconcile(self, _: ops.HookEvent | None = None) -> None:
        """Evaluate current state and set unit status.

        Called from every event handler.  Sets WaitingStatus until the
        upstream TLS provider relation exists, then ActiveStatus.
        """
        if not self.model.relations[UPSTREAM_RELATION_NAME]:
            self.unit.status = ops.WaitingStatus("Waiting for upstream TLS provider")
            return
        self.unit.status = ops.ActiveStatus()

    def _on_certificates_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Store a CSR mapping secret for each new old-interface certificate request.

        For each CertificateRequest that does not yet have a mapping secret,
        builds a deterministic CSR from the charm's stable private key and
        the request attributes, then persists a mapping secret keyed by the
        CSR fingerprint.  The upstream TLS library picks up the updated CSR
        list automatically via the ``refresh_events`` hook registered in
        ``__init__``.  Already-mapped requests are skipped (idempotent).

        Also writes the accumulated CSR fingerprints for this relation into the
        local unit relation databag so that ``_on_certificates_relation_broken``
        can revoke them without needing remote unit data.
        """
        state = self.state
        fingerprints = []
        for cr in state.certificate_requests if state else []:
            if cr.relation_id != event.relation.id:
                continue
            csr_pem = build_csr(self._charm_key_pem, cr.common_name, cr.sans_dns)
            fingerprints.append(csr_sha256_hex(csr_pem))
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
        if fingerprints:
            event.relation.data[self.unit][CSR_FINGERPRINTS_KEY] = json.dumps(fingerprints)
        self.reconcile(event)

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Deliver a signed certificate to the old-interface requirer.

        Looks up the per-CSR mapping secret, writes cert + key + CA to the
        old-interface requirer's relation databag.  The mapping secret is
        intentionally retained so that library-managed renewal can reuse it
        when the same CSR fingerprint fires a new ``certificate_available``.
        Logs an error and skips gracefully if the mapping is missing.
        If the old-interface relation is gone, revokes the mapping and logs
        at INFO.
        """
        csr_pem = str(event.certificate_signing_request)
        mapping = get_csr_mapping(self, csr_pem)
        if mapping is None:
            logger.error(
                "No CSR mapping found for certificate (CN=%s); skipping delivery",
                event.certificate.common_name,
            )
            return

        relation_id = int(mapping["relation-id"])
        requirer_unit_name = mapping["requirer-unit"]
        private_key_pem = mapping["private-key"]

        relation = None
        with contextlib.suppress(ops.RelationNotFoundError):
            relation = self.model.get_relation(OLD_INTERFACE_RELATION_NAME, relation_id)
        if relation is None or not relation.active:
            logger.info(
                "Old-interface relation %d no longer exists; revoking mapping for %s",
                relation_id,
                requirer_unit_name,
            )
            revoke_csr_mapping(self, csr_pem)
            return

        write_certificate(
            relation=relation,
            charm_unit=self.unit,
            requirer_unit_name=requirer_unit_name,
            common_name=str(event.certificate.common_name),
            cert=str(event.certificate),
            key=private_key_pem,
            ca=str(event.ca),
        )
        self.reconcile()

    def _on_certificate_denied(self, event: CertificateDeniedEvent) -> None:
        """Handle a denied certificate request from the upstream TLS provider.

        Revokes the mapping secret for the denied CSR and logs the error so
        the operator can investigate.  The old-interface requirer is left in
        its current state; no data is written to the relation databag.
        """
        csr_pem = str(event.certificate_signing_request)
        mapping = get_csr_mapping(self, csr_pem)
        if mapping is None:
            logger.warning(
                "certificate_denied: no mapping found for denied CSR — already cleaned up"
            )
            return
        revoke_csr_mapping(self, csr_pem)
        logger.error(
            "Certificate request denied for %s (error: %s); mapping revoked",
            mapping.get("requirer-unit", "unknown"),
            event.error,
        )

    def _on_certificates_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Revoke all mapping secrets for the broken old-interface relation.

        Reads the CSR fingerprints stored in the local unit relation databag
        during ``_on_certificates_relation_changed`` and revokes each mapping
        secret.  Secrets already gone are silently skipped.  Calls
        ``reconcile()`` to update unit status.
        """
        raw = event.relation.data[self.unit].get(CSR_FINGERPRINTS_KEY, "")
        fingerprints: list[str] = json.loads(raw) if raw else []
        for fingerprint in fingerprints:
            label = f"{JUJU_SECRET_LABEL_PREFIX}{fingerprint}"
            try:
                secret = self.model.get_secret(label=label)
                secret.remove_all_revisions()
                logger.info(
                    "Revoked mapping secret %r for broken relation %d", label, event.relation.id
                )
            except ops.SecretNotFoundError:
                logger.debug("Mapping secret %r already gone — skipping", label)
        self.reconcile()


if __name__ == "__main__":  # pragma: nocover
    ops.main(TLSCertificateAdaptorCharm)
