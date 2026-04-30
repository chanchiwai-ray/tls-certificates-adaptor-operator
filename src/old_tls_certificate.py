# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Old tls-certificates interface (v1): read and write the legacy reactive relation data.

The "old" interface is the original reactive ``tls-certificates`` interface
(interface name ``tls-certificates``, sometimes called v1) used by Charmed
OpenStack services (keystone, nova-cloud-controller, cinder, etc.) up to and
including Yoga.  In this protocol the *provider* generates and returns both the
private key and the signed certificate.  The requirer writes a JSON list of
certificate requests (``cert_requests`` key) into its unit databag; the
provider writes the issued material back into its own unit databag under a key
derived from the requirer unit name.

This module provides :class:`OldTLSCertificatesRelation`, which handles all
reads and writes for a single such relation.  The shared data models
:class:`~models.CertificateRequest` and :class:`~models.IssuedCertificate` live
in :mod:`models`.
"""

from __future__ import annotations

import json
import logging

import ops

from constants import (
    CERT_REQUEST_KEY,
    OLD_INTERFACE_CERT_TYPE,
    OLD_INTERFACE_RELATION_NAME,
    PROCESSED_REQUESTS_SUFFIX,
)
from models import CertificateRequest

logger = logging.getLogger(__name__)


class OldTLSCertificatesRelation:
    """Manages read and write operations on all legacy reactive tls-certificates (v1) relations."""

    def __init__(self, charm: ops.CharmBase) -> None:
        """Initialise the relation handler.

        Args:
            charm: The charm instance.  The handler reads the active
                old-interface relations from ``charm.model.relations`` each
                time a method is called so it always reflects current state.
        """
        self._charm = charm

    def get_certificate_requests(self) -> list[CertificateRequest]:
        """Read certificate requests from all old-interface (v1) requirer unit databags.

        Returns:
            A list of CertificateRequest objects for all ``server`` cert requests found
            across every active old-interface relation.
            Requests with a cert_type other than ``server`` are logged and skipped.
            Malformed or missing data is logged and skipped.
        """
        requests: list[CertificateRequest] = []
        for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
            for unit in relation.units:
                raw = relation.data[unit].get(CERT_REQUEST_KEY, "")
                if not raw:
                    logger.debug(
                        "No cert_requests data in unit databag for %s on relation %d",
                        unit.name,
                        relation.id,
                    )
                    continue
                try:
                    entries = json.loads(raw)
                except json.JSONDecodeError:
                    logger.debug(
                        "Malformed cert_requests JSON in unit databag for %s on relation %d",
                        unit.name,
                        relation.id,
                    )
                    continue
                if not isinstance(entries, list):
                    logger.debug(
                        "cert_requests is not a list for %s on relation %d",
                        unit.name,
                        relation.id,
                    )
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    cert_type = entry.get("cert_type", "")
                    if cert_type != OLD_INTERFACE_CERT_TYPE:
                        logger.warning(
                            "Skipping cert request with unsupported cert_type %r from %s on relation %d",
                            cert_type,
                            unit.name,
                            relation.id,
                        )
                        continue
                    common_name = entry.get("common_name", "")
                    sans_raw = entry.get("sans") or entry.get("sans_dns") or []
                    if not isinstance(sans_raw, list):
                        sans_raw = [sans_raw]
                    sans_dns = [str(s) for s in sans_raw]
                    requests.append(
                        CertificateRequest(
                            common_name=common_name,
                            sans_dns=sans_dns,
                            cert_type=OLD_INTERFACE_CERT_TYPE,
                            requirer_unit_name=unit.name,
                            relation_id=relation.id,
                        )
                    )
        return requests

    def write_certificate(
        self,
        relation_id: int,
        requirer_unit_name: str,
        common_name: str,
        cert: str,
        key: str,
        ca: str,
    ) -> None:
        """Write a signed certificate and private key to the old-interface (v1) provider databag.

        Args:
            relation_id: ID of the old-interface relation to write to.
            requirer_unit_name: The old requirer unit name (e.g. ``keystone/0``).
            common_name: The common name of the certificate.
            cert: PEM-encoded signed certificate.
            key: PEM-encoded private key.
            ca: PEM-encoded CA certificate.
        """
        relation = self._charm.model.get_relation(OLD_INTERFACE_RELATION_NAME, relation_id)
        if relation is None:
            logger.warning(
                "Cannot write certificate: relation %d not found in active relations", relation_id
            )
            return
        munged = requirer_unit_name.replace("/", "_")
        databag_key = f"{munged}{PROCESSED_REQUESTS_SUFFIX}"
        payload = json.dumps(
            [
                {
                    "cert_type": OLD_INTERFACE_CERT_TYPE,
                    "common_name": common_name,
                    "cert": cert,
                    "key": key,
                    "ca": ca,
                }
            ]
        )
        relation.data[self._charm.unit][databag_key] = payload
        logger.debug(
            "Wrote certificate for %s (common_name=%r) to relation %d",
            requirer_unit_name,
            common_name,
            relation_id,
        )
