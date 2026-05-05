# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Shared Pydantic data models used across relation handler modules."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class CertificateRequest(BaseModel):
    """A pending certificate request from an old-interface (v1) requirer unit."""

    model_config = ConfigDict(frozen=True)

    common_name: str
    sans: list[str]
    cert_type: Literal["server", "client"]
    requirer_unit_name: str
    relation_id: int
    is_legacy: bool = False
    is_client: bool = False


class IssuedCertificate(BaseModel):
    """A certificate issued by the upstream TLS provider and ready to deliver."""

    model_config = ConfigDict(frozen=True)

    certificate: str  # PEM
    ca: str  # PEM
    chain: list[str]  # list of PEM
