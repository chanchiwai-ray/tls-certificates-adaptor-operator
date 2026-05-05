# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Crypto helpers: RSA key generation, CSR building, and fingerprinting."""

import hashlib
import ipaddress

from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes, PrivateKey
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding


def generate_private_key() -> str:
    """Generate a 2048-bit RSA private key and return it as a PEM string.

    Returns:
        str: PEM-encoded 2048-bit RSA private key.
    """
    return str(PrivateKey.generate(key_size=2048))


def classify_sans(sans: list[str]) -> tuple[list[str], list[str]]:
    """Classify a mixed list of SANs into DNS names and IP addresses.

    The reactive tls-certificates (v1) interface does not distinguish between
    DNS and IP SANs — requirers put both types in the same list.  This helper
    separates them so that IP addresses are placed in the correct X.509 IP SAN
    extension (rather than the DNS SAN extension), which is required for vault
    PKI role validation.

    Args:
        sans (list[str]): A list of SAN strings that may be DNS names or IP addresses
            (IPv4 or IPv6).

    Returns:
        tuple[list[str], list[str]]: A ``(dns_sans, ip_sans)`` tuple where each element is a list of the
            corresponding type.
    """
    dns_sans: list[str] = []
    ip_sans: list[str] = []
    for san in sans:
        try:
            ipaddress.ip_address(san)
            ip_sans.append(san)
        except ValueError:
            dns_sans.append(san)
    return dns_sans, ip_sans


def build_csr(private_key_pem: str, common_name: str, sans: list[str]) -> str:
    """Build a deterministic PEM-encoded CSR for the given key, CN, and SANs.

    SANs that are IP addresses are placed in the IP SAN extension; all others
    are placed in the DNS SAN extension.  This ensures the CSR fingerprint
    matches the one produced by the upstream ``TLSCertificatesRequiresV4``
    library (which uses the same ``CertificateRequestAttributes`` parameters).

    Uses ``add_unique_id_to_subject_name=False`` so that the same
    ``(private_key_pem, common_name, sans)`` triple always produces an
    identical fingerprint — required for idempotency checks in
    ``_on_certificates_relation_changed``.

    Args:
        private_key_pem (str): PEM-encoded RSA private key.
        common_name (str): The certificate common name.
        sans (list[str]): Subject Alternative Names (DNS names and/or IP
            addresses).

    Returns:
        str: PEM-encoded CSR.
    """
    pk = PrivateKey.from_string(private_key_pem)
    dns_sans, ip_sans = classify_sans(sans)
    attrs = CertificateRequestAttributes(
        common_name=common_name,
        sans_dns=dns_sans if dns_sans else None,
        sans_ip=ip_sans if ip_sans else None,
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


def build_ca_bundle(
    ca: str,
    chain: list[str],
    leaf_pem: str,
    extra_ca_certificates: str = "",
) -> str:
    """Build a full CA certificate bundle from provider data and optional extra certs.

    Strips the leaf cert from *chain*, then appends any CA certs not already
    present in *ca*.  Finally appends *extra_ca_certificates* (e.g. a root CA
    missing from the upstream provider's chain) if set.

    Args:
        ca (str): PEM-encoded CA certificate from the upstream provider.
        chain (list[str]): List of PEM-encoded certificates from the upstream provider.
        leaf_pem (str): PEM string of the leaf certificate to exclude from the chain.
        extra_ca_certificates (str): Optional additional PEM-encoded CA certs to append.

    Returns:
        str: PEM bundle containing all CA certs needed to verify the leaf cert.
    """
    ca_certs = [c for c in chain if c != leaf_pem] if chain else []
    full_ca_pem = ca
    for cert_pem in ca_certs:
        stripped = cert_pem.strip()
        if stripped not in full_ca_pem:
            full_ca_pem = full_ca_pem + "\n" + stripped
    if extra_ca_certificates and extra_ca_certificates not in full_ca_pem:
        full_ca_pem = full_ca_pem + "\n" + extra_ca_certificates
    return full_ca_pem
