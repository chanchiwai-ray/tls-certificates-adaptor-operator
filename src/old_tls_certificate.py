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
    CSR_FINGERPRINTS_KEY,
    LEGACY_CERT_SUFFIX,
    LEGACY_KEY_SUFFIX,
    OLD_INTERFACE_CERT_TYPE,
    OLD_INTERFACE_RELATION_NAME,
    PROCESSED_REQUESTS_SUFFIX,
)
from crypto import build_csr, csr_sha256_hex
from models import CertificateRequest
from secret import get_csr_mapping, revoke_csr_mapping_by_fingerprint, store_csr_mapping

logger = logging.getLogger(__name__)


class OldTLSCertificatesRelation:
    """Manages read and write operations on all legacy reactive tls-certificates (v1) relations."""

    def __init__(self, charm: ops.CharmBase, private_key_pem: str = "") -> None:
        """Initialise the relation handler.

        Args:
            charm (ops.CharmBase): The charm instance.  The handler reads the active
                old-interface relations from ``charm.model.relations`` each
                time a method is called so it always reflects current state.
            private_key_pem (str): PEM-encoded RSA private key used to build CSRs
                for fingerprint computation and mapping-secret creation.
        """
        self._charm = charm
        self._private_key_pem = private_key_pem

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

    def get_csr_fingerprints(
        self,
        requests: list[CertificateRequest] | None = None,
    ) -> dict[int, list[str]]:
        """Return CSR SHA-256 fingerprints for all current requests, keyed by relation ID.

        Builds a deterministic CSR for each :class:`~models.CertificateRequest`
        and computes its SHA-256 fingerprint.  Used by :class:`~state.CharmState`
        to record which CSRs exist per relation without performing any side effects.

        Args:
            requests (list[CertificateRequest] | None): Pre-computed certificate
                requests to use.  If ``None``, calls :meth:`get_certificate_requests`
                to obtain them.  Pass the already-computed requests from
                :meth:`~state.CharmState.from_charm` to avoid a second round of
                relation-databag parsing.

        Returns:
            dict[int, list[str]]: Mapping of relation ID to a list of CSR fingerprints
                for all requests on that relation.
        """
        all_requests = requests if requests is not None else self.get_certificate_requests()
        result: dict[int, list[str]] = {}
        for cr in all_requests:
            csr_pem = build_csr(self._private_key_pem, cr.common_name, cr.sans)
            fp = csr_sha256_hex(csr_pem)
            result.setdefault(cr.relation_id, []).append(fp)
        return result

    def process_relation(
        self,
        relation: ops.Relation,
        requests: list[CertificateRequest],
    ) -> None:
        """Store CSR mapping secrets for all pending requests on a single relation.

        For each :class:`~models.CertificateRequest` on *relation* that does not
        yet have a mapping secret, builds a deterministic CSR from the charm's
        private key and persists a mapping secret keyed by the CSR fingerprint.
        Already-mapped requests are skipped (idempotent).  Writes the accumulated
        fingerprints into the local unit relation databag via
        :meth:`write_csr_fingerprints`.

        Args:
            relation (ops.Relation): The old-interface relation to process.
            requests (list[CertificateRequest]): The full list of current certificate
                requests (typically from :attr:`~state.CharmState.certificate_requests`).
                Requests for other relations are filtered out internally.
        """
        fingerprints: list[str] = []
        for cr in requests:
            if cr.relation_id != relation.id:
                continue
            csr_pem = build_csr(self._private_key_pem, cr.common_name, cr.sans)
            fp = csr_sha256_hex(csr_pem)
            fingerprints.append(fp)
            if get_csr_mapping(self._charm, csr_pem) is not None:
                logger.debug(
                    "CSR mapping already exists for %s (%s) — skipping",
                    cr.common_name,
                    cr.requirer_unit_name,
                )
                continue
            store_csr_mapping(
                self._charm,
                csr_pem,
                self._private_key_pem,
                cr.requirer_unit_name,
                cr.relation_id,
                is_legacy=cr.is_legacy,
                is_client=cr.is_client,
            )
            logger.info(
                "Stored CSR mapping for %s (%s) on relation %d",
                cr.common_name,
                cr.requirer_unit_name,
                cr.relation_id,
            )
        if fingerprints:
            self.write_csr_fingerprints(relation, fingerprints)

    def write_csr_fingerprints(self, relation: ops.Relation, fingerprints: list[str]) -> None:
        """Write CSR fingerprints to the local unit relation databag.

        The fingerprints are stored as a JSON-encoded list under
        ``csr-fingerprints`` so that :meth:`revoke_csr_mappings` can retrieve
        them when the relation is broken without needing remote-unit data.

        Args:
            relation (ops.Relation): The relation whose local unit databag to write.
            fingerprints (list[str]): List of hex SHA-256 CSR fingerprints.
        """
        relation.data[self._charm.unit][CSR_FINGERPRINTS_KEY] = json.dumps(fingerprints)
        logger.debug("Wrote %d CSR fingerprints to relation %d", len(fingerprints), relation.id)

    def revoke_csr_mappings(self, relation: ops.Relation) -> None:
        """Revoke all CSR mapping secrets for a broken old-interface relation.

        Reads the CSR fingerprints stored in the local unit relation databag by
        :meth:`write_csr_fingerprints` and removes each corresponding mapping
        secret.  Secrets already gone are silently skipped.

        Args:
            relation (ops.Relation): The relation that is being broken.
        """
        raw = relation.data[self._charm.unit].get(CSR_FINGERPRINTS_KEY, "")
        fingerprints: list[str] = json.loads(raw) if raw else []
        for fingerprint in fingerprints:
            revoke_csr_mapping_by_fingerprint(self._charm, fingerprint)
            logger.info(
                "Revoked mapping secret for fingerprint %s on broken relation %d",
                fingerprint,
                relation.id,
            )

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
