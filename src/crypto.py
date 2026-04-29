# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Crypto helpers: RSA key generation, CSR building, and fingerprinting."""

import hashlib

from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes, PrivateKey
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding


def generate_private_key() -> str:
    """Generate a 2048-bit RSA private key and return it as a PEM string.

    Returns:
        str: PEM-encoded 2048-bit RSA private key.
    """
    return str(PrivateKey.generate(key_size=2048))


def build_csr(private_key_pem: str, common_name: str, sans: list[str]) -> str:
    """Build a deterministic PEM-encoded CSR for the given key, CN, and SANs.

    Uses ``add_unique_id_to_subject_name=False`` so that the same
    ``(private_key_pem, common_name, sans)`` triple always produces an
    identical fingerprint — required for idempotency checks in
    ``_on_certificates_relation_changed``.

    Args:
        private_key_pem (str): PEM-encoded RSA private key.
        common_name (str): The certificate common name.
        sans (list[str]): DNS Subject Alternative Names.

    Returns:
        str: PEM-encoded CSR.
    """
    pk = PrivateKey.from_string(private_key_pem)
    attrs = CertificateRequestAttributes(
        common_name=common_name,
        sans_dns=sans if sans else None,
        add_unique_id_to_subject_name=False,
    )
    csr = attrs.generate_csr(pk)
    return str(csr)


def csr_sha256_hex(csr_pem: str) -> str:
    """Return the lowercase hex SHA-256 fingerprint of the DER-encoded CSR.

    Args:
        csr_pem (str): PEM-encoded CSR.

    Returns:
        str: Lowercase 64-character hexadecimal SHA-256 fingerprint.
    """
    csr_obj = x509.load_pem_x509_csr(csr_pem.encode())
    der = csr_obj.public_bytes(Encoding.DER)
    return hashlib.sha256(der).hexdigest()
