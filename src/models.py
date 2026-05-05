# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Shared Pydantic data models used across relation handler modules."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CertificateRequest(BaseModel):
    """A pending certificate request from an old-interface (v1) requirer unit.

    Attributes:
        common_name: The certificate common name (CN).
        sans: Subject Alternative Names for the certificate.
        requirer_unit_name: The Juju unit name of the requesting unit.
        relation_id: The relation ID on the old interface.
        is_legacy: Whether the request used the legacy unit_name.server_cert format.
        is_client: Whether this is a synthetic client certificate request.
    """

    model_config = ConfigDict(frozen=True)

    common_name: str
    sans: list[str]
    requirer_unit_name: str
    relation_id: int
    is_legacy: bool = False
    is_client: bool = False


class IssuedCertificate(BaseModel):
    """A certificate issued by the upstream TLS provider and ready to deliver.

    Attributes:
        certificate: PEM-encoded leaf certificate.
        ca: PEM-encoded CA certificate.
        chain: List of PEM-encoded intermediate certificates.
    """

    model_config = ConfigDict(frozen=True)

    certificate: str  # PEM
    ca: str  # PEM
    chain: list[str]  # list of PEM
