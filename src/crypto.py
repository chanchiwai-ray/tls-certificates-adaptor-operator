# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Crypto helpers: SAN classification and CA bundle construction."""

import ipaddress


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
