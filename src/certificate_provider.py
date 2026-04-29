# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Certificate provider: read and write the old reactive tls-certificates relation data."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import ops

from constants import CERT_REQUEST_KEY, OLD_INTERFACE_CERT_TYPE, PROCESSED_REQUESTS_SUFFIX

if TYPE_CHECKING:
    from state import CertificateRequest

logger = logging.getLogger(__name__)


def get_certificate_requests(relation: ops.Relation) -> list[CertificateRequest]:
    """Read certificate requests from an old-interface requirer's unit databag.

    Args:
        relation: The old-interface relation to read from.

    Returns:
        A list of CertificateRequest objects for all ``server`` cert requests found.
        Requests with a cert_type other than ``server`` are logged and skipped.
        Malformed or missing data returns an empty list.
    """
    from state import CertificateRequest

    requests: list[CertificateRequest] = []
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
    relation: ops.Relation,
    charm_unit: ops.Unit,
    requirer_unit_name: str,
    common_name: str,
    cert: str,
    key: str,
    ca: str,
) -> None:
    """Write a signed certificate and private key to the old-interface provider unit databag.

    Args:
        relation: The old-interface relation to write to.
        charm_unit: The adaptor's own unit (used to access its databag).
        requirer_unit_name: The old requirer unit name (e.g. ``keystone/0``).
        common_name: The common name of the certificate.
        cert: PEM-encoded signed certificate.
        key: PEM-encoded private key.
        ca: PEM-encoded CA certificate.
    """
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
    relation.data[charm_unit][databag_key] = payload
    logger.debug(
        "Wrote certificate for %s (common_name=%r) to relation %d",
        requirer_unit_name,
        common_name,
        relation.id,
    )
