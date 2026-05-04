# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Old tls-certificates interface (v1): read and write the legacy reactive relation data.

The "old" interface is the original reactive ``tls-certificates`` interface
(interface name ``tls-certificates``, sometimes called v1) used by Charmed
OpenStack services (keystone, nova-cloud-controller, cinder, etc.) up to and
including Yoga.  In this protocol the *provider* generates and returns both the
private key and the signed certificate.

Requesters write certificate requests into their unit databag in one of two
formats:

- **Legacy format**: ``common_name`` and ``sans`` as direct string keys
  (used by the reactive library for the first certificate per unit).
- **Batch format**: ``cert_requests`` as a JSON-encoded dict
  ``{"<cn>": {"sans": [...]}}`` (used by charmhelpers ``CertRequest.get_request()``).

This module provides :class:`OldTLSCertificatesRelation`, which handles all
reads and writes for all old-interface relations.  The shared data models
:class:`~models.CertificateRequest` and :class:`~models.IssuedCertificate` live
in :mod:`models`.
"""

from __future__ import annotations

import json
import logging

import ops

from constants import (
    CERT_REQUEST_KEY,
    LEGACY_CERT_SUFFIX,
    LEGACY_KEY_SUFFIX,
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

        Handles both request sub-formats written by OpenStack charms:

        - **Legacy format**: ``common_name`` and ``sans`` as direct databag keys.
        - **Batch format**: ``cert_requests`` as a JSON-encoded dict
          ``{"<cn>": {"sans": [...]}}``, used by charmhelpers
          ``CertRequest.get_request()``.

        Both formats may coexist in the same unit databag.  Malformed or
        missing data is logged and skipped.

        Returns:
            A list of :class:`~models.CertificateRequest` objects for all
            server certificate requests found across every active relation.
        """
        requests: list[CertificateRequest] = []
        for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
            for unit in relation.units:
                data = relation.data[unit]
                legacy = self._parse_legacy_request(data, unit.name, relation.id)
                if legacy is not None:
                    requests.append(legacy)
                requests.extend(self._parse_batch_requests(data, unit.name, relation.id))
        return requests

    def _parse_legacy_request(
        self,
        data: ops.RelationDataContent,
        unit_name: str,
        relation_id: int,
    ) -> CertificateRequest | None:
        """Parse a legacy single-cert request from a unit databag.

        Returns a :class:`~models.CertificateRequest` with ``is_legacy=True``
        if a ``common_name`` key is present, or ``None`` if not.
        """
        cn = data.get("common_name", "").strip()
        if not cn:
            return None
        raw_sans = data.get("sans", "")
        try:
            sans: list[str] = json.loads(raw_sans) if raw_sans else []
            if not isinstance(sans, list):
                raise ValueError("sans is not a list")
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "Malformed sans in legacy databag for %s on relation %d; using []",
                unit_name,
                relation_id,
            )
            sans = []
        return CertificateRequest(
            common_name=cn,
            sans_dns=[str(s) for s in sans],
            cert_type=OLD_INTERFACE_CERT_TYPE,
            requirer_unit_name=unit_name,
            relation_id=relation_id,
            is_legacy=True,
        )

    def _parse_batch_requests(
        self,
        data: ops.RelationDataContent,
        unit_name: str,
        relation_id: int,
    ) -> list[CertificateRequest]:
        """Parse batch-format cert requests (``cert_requests`` JSON dict) from a unit databag.

        Returns one :class:`~models.CertificateRequest` with ``is_legacy=False``
        per CN in the dict.  Returns an empty list if the key is absent or malformed.
        """
        raw = data.get(CERT_REQUEST_KEY, "")
        if not raw:
            return []
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Malformed cert_requests JSON for %s on relation %d",
                unit_name,
                relation_id,
            )
            return []
        if not isinstance(entries, dict):
            logger.warning(
                "cert_requests is not a dict for %s on relation %d",
                unit_name,
                relation_id,
            )
            return []
        results: list[CertificateRequest] = []
        for batch_cn, req in entries.items():
            if not batch_cn or not isinstance(req, dict):
                continue
            batch_sans = req.get("sans") or []
            if not isinstance(batch_sans, list):
                logger.warning(
                    "sans is not a list for CN %r from %s on relation %d; wrapping",
                    batch_cn,
                    unit_name,
                    relation_id,
                )
                batch_sans = [batch_sans]
            results.append(
                CertificateRequest(
                    common_name=batch_cn,
                    sans_dns=[str(s) for s in batch_sans],
                    cert_type=OLD_INTERFACE_CERT_TYPE,
                    requirer_unit_name=unit_name,
                    relation_id=relation_id,
                    is_legacy=False,
                )
            )
        return results

    def write_certificate(
        self,
        relation_id: int,
        requirer_unit_name: str,
        common_name: str,
        cert: str,
        key: str,
        ca: str,
        chain: str = "",
        is_legacy: bool = False,
    ) -> None:
        """Write a signed certificate and private key to the old-interface (v1) provider databag.

        For the **legacy** format (``is_legacy=True``), writes individual
        ``{munged}.server.cert`` / ``{munged}.server.key`` keys alongside a
        top-level ``ca`` key (and optional ``chain``), which is what the
        reactive ``server_certs`` property reads.

        For the **batch** format (``is_legacy=False``), merges the new cert
        into the ``{munged}.processed_requests`` dict so that multiple CNs
        from the same requirer unit accumulate in a single key, plus top-level
        ``ca`` (and optional ``chain``).

        Args:
            relation_id: ID of the old-interface relation to write to.
            requirer_unit_name: The old requirer unit name (e.g. ``keystone/0``).
            common_name: The common name of the certificate.
            cert: PEM-encoded signed certificate.
            key: PEM-encoded private key.
            ca: PEM-encoded CA certificate.
            chain: Optional PEM-encoded concatenated certificate chain.
            is_legacy: When True use the legacy single-cert key format; when
                False use the batch ``processed_requests`` dict format.
        """
        relation = self._charm.model.get_relation(OLD_INTERFACE_RELATION_NAME, relation_id)
        if relation is None:
            logger.warning(
                "Cannot write certificate: relation %d not found in active relations", relation_id
            )
            return
        munged = requirer_unit_name.replace("/", "_")
        databag = relation.data[self._charm.unit]

        if is_legacy:
            databag[f"{munged}{LEGACY_CERT_SUFFIX}"] = cert
            databag[f"{munged}{LEGACY_KEY_SUFFIX}"] = key
        else:
            key_name = f"{munged}{PROCESSED_REQUESTS_SUFFIX}"
            existing_raw = databag.get(key_name) or "{}"
            try:
                existing: dict = json.loads(existing_raw)
                if not isinstance(existing, dict):
                    existing = {}
            except json.JSONDecodeError:
                existing = {}
            existing[common_name] = {"cert": cert, "key": key}
            databag[key_name] = json.dumps(existing)

        databag["ca"] = ca
        if chain:
            databag["chain"] = chain

        logger.debug(
            "Wrote certificate for %s (common_name=%r, is_legacy=%s) to relation %d",
            requirer_unit_name,
            common_name,
            is_legacy,
            relation_id,
        )

    def write_ca(self, ca: str, chain: str = "") -> None:
        """Write the upstream CA cert to all active old-interface relations.

        This propagates the CA (and optional chain) to every old-interface
        relation so requirers that gate on ``{endpoint}.ca.available`` can
        proceed, and so that CA rotation is reflected without waiting for a
        certificate renewal event.

        Args:
            ca: PEM-encoded CA certificate.
            chain: Optional PEM-encoded concatenated certificate chain.
        """
        for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
            relation.data[self._charm.unit]["ca"] = ca
            if chain:
                relation.data[self._charm.unit]["chain"] = chain
        logger.debug("Propagated CA to all old-interface relations")
