# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Shared pytest fixtures for unit tests."""

from datetime import timedelta

import pytest
from charmlibs.interfaces.tls_certificates import (
    Certificate,
    CertificateRequestAttributes,
    CertificateSigningRequest,
    PrivateKey,
)


@pytest.fixture(scope="session")
def ca_private_key() -> PrivateKey:
    """Return a session-scoped CA private key."""
    return PrivateKey.generate(key_size=2048)


@pytest.fixture(scope="session")
def ca_certificate(ca_private_key: PrivateKey) -> Certificate:
    """Return a session-scoped self-signed CA certificate."""
    attrs = CertificateRequestAttributes(common_name="Test CA")
    return Certificate.generate_self_signed_ca(attrs, ca_private_key, validity=timedelta(days=365))


@pytest.fixture(scope="session")
def intermediate_ca_private_key() -> PrivateKey:
    """Return a session-scoped private key for the intermediate CA."""
    return PrivateKey.generate(key_size=2048)


@pytest.fixture(scope="session")
def intermediate_ca_certificate(intermediate_ca_private_key: PrivateKey) -> Certificate:
    """Return a session-scoped self-signed intermediate CA certificate (distinct from root CA)."""
    attrs = CertificateRequestAttributes(common_name="Test Intermediate CA")
    return Certificate.generate_self_signed_ca(
        attrs, intermediate_ca_private_key, validity=timedelta(days=365)
    )


def sign_csr(csr_pem: str, ca: Certificate, ca_key: PrivateKey) -> Certificate:
    """Sign a PEM CSR with the given CA and return the issued Certificate.

    Args:
        csr_pem (str): PEM-encoded certificate signing request.
        ca (Certificate): CA certificate used to sign.
        ca_key (PrivateKey): CA private key used to sign.

    Returns:
        Certificate: The signed certificate, valid for 90 days.
    """
    return CertificateSigningRequest.from_string(csr_pem).sign(ca, ca_key, timedelta(days=90))
