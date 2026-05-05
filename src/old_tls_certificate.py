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
    CLIENT_CERT_KEY,
    CLIENT_KEY_KEY,
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
            charm (ops.CharmBase): The charm instance.  The handler reads the active
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

        Also synthesizes one **client cert request** per relation that has at
        least one server cert request.  The old reactive tls-certificates
        provider convention always generated a shared ``client.cert``/
        ``client.key`` pair alongside the per-unit server certs, which charms
        such as ovn-central use for mutual TLS between their OVSDB components.

        Returns:
            list[CertificateRequest]: A list of CertificateRequest objects for all
                server certificate requests found across every active relation,
                plus one synthetic client cert request per active relation.
        """
        requests: list[CertificateRequest] = []
        for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
            relation_requests: list[CertificateRequest] = []
            app_name: str | None = None
            for unit in relation.units:
                data = relation.data[unit]
                legacy = self._parse_legacy_request(data, unit.name, relation.id)
                if legacy is not None:
                    relation_requests.append(legacy)
                relation_requests.extend(self._parse_batch_requests(data, unit.name, relation.id))
                if app_name is None:
                    app_name = unit.name.split("/")[0]
            requests.extend(relation_requests)
            if relation_requests and app_name:
                requests.append(
                    CertificateRequest(
                        common_name=f"{app_name}-client",
                        sans=[],
                        cert_type="client",
                        requirer_unit_name=f"{app_name}/client",
                        relation_id=relation.id,
                        is_client=True,
                    )
                )
        return requests

    def _parse_legacy_request(
        self,
        data: ops.RelationDataContent,
        unit_name: str,
        relation_id: int,
    ) -> CertificateRequest | None:
        """Parse a legacy single-cert request from a unit databag.

        Args:
            data (ops.RelationDataContent): The unit databag to parse.
            unit_name (str): The unit name for logging purposes.
            relation_id (int): The relation ID for the request.

        Returns:
            CertificateRequest | None: A CertificateRequest with ``is_legacy=True``
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
            sans=[str(s) for s in sans],
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

        Args:
            data (ops.RelationDataContent): The unit databag to parse.
            unit_name (str): The unit name for logging purposes.
            relation_id (int): The relation ID for the request.

        Returns:
            list[CertificateRequest]: One CertificateRequest with ``is_legacy=False``
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
            if not batch_cn.strip() or not isinstance(req, dict):
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
                    sans=[str(s) for s in batch_sans],
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
        is_legacy: bool = False,
    ) -> None:
        """Write a signed certificate and private key to the old-interface (v1) provider databag.

        For the **legacy** format (``is_legacy=True``), writes individual
        ``{munged}.server.cert`` / ``{munged}.server.key`` keys alongside a
        top-level ``ca`` key, which is what the reactive ``server_certs``
        property reads.

        For the **batch** format (``is_legacy=False``), merges the new cert
        into the ``{munged}.processed_requests`` dict so that multiple CNs
        from the same requirer unit accumulate in a single key, plus top-level
        ``ca``.

        Args:
            relation_id (int): ID of the old-interface relation to write to.
            requirer_unit_name (str): The old requirer unit name (e.g. ``keystone/0``).
            common_name (str): The common name of the certificate.
            cert (str): PEM-encoded signed certificate.
            key (str): PEM-encoded private key.
            ca (str): PEM-encoded CA certificate.
            is_legacy (bool): When True use the legacy single-cert key format; when
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

        logger.debug(
            "Wrote certificate for %s (common_name=%r, is_legacy=%s) to relation %d",
            requirer_unit_name,
            common_name,
            is_legacy,
            relation_id,
        )

    def write_client_cert(self, relation_id: int, cert: str, key: str) -> None:
        """Write a shared client certificate and key to the old-interface provider databag.

        The reactive tls-certificates provider convention writes a shared
        ``client.cert``/``client.key`` pair to the relation databag alongside
        per-unit server certificates.  Charms such as ovn-central use this
        client cert for mutual TLS between their OVSDB components
        (ovn-northd ↔ ovsdb-server connections).

        Args:
            relation_id (int): ID of the old-interface relation to write to.
            cert (str): PEM-encoded signed client certificate.
            key (str): PEM-encoded private key for the client certificate.
        """
        relation = self._charm.model.get_relation(OLD_INTERFACE_RELATION_NAME, relation_id)
        if relation is None:
            logger.warning(
                "Cannot write client cert: relation %d not found in active relations", relation_id
            )
            return
        databag = relation.data[self._charm.unit]
        databag[CLIENT_CERT_KEY] = cert
        databag[CLIENT_KEY_KEY] = key
        logger.debug("Wrote client.cert/client.key to relation %d", relation_id)

    def write_ca(self, ca: str) -> None:
        """Write the upstream CA cert bundle to all active old-interface relations.

        Writes the full CA chain (all CA certs from the immediate issuer to
        root, concatenated) into the ``ca`` key of every old-interface
        relation provider databag.  The old reactive tls-certificates (v1)
        interface only reads ``ca`` — there is no ``chain`` key in this
        protocol — so all CA certs must be bundled into this single field.

        Args:
            ca (str): PEM-encoded CA certificate bundle (may be concatenated certs).
        """
        for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
            relation.data[self._charm.unit]["ca"] = ca
        logger.debug("Propagated CA to all old-interface relations")
