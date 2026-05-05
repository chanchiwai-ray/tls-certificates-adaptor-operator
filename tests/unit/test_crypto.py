# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for crypto module."""

import hashlib
import ipaddress

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key

from crypto import build_csr, classify_sans, csr_sha256_hex, generate_private_key


class TestGeneratePrivateKey:
    """Tests for generate_private_key()."""

    def test_returns_valid_pem_rsa_key_of_at_least_2048_bits(self):
        """
        arrange: Nothing.
        act: Call generate_private_key().
        assert: Returns a valid PEM RSA private key of at least 2048 bits.
        """
        key_pem = generate_private_key()

        raw_key = load_pem_private_key(key_pem.encode(), password=None)
        assert isinstance(raw_key, rsa.RSAPrivateKey)
        assert raw_key.key_size >= 2048

    def test_returns_pem_encoded_string(self):
        """
        arrange: Nothing.
        act: Call generate_private_key().
        assert: The result starts with PEM header for a private key.
        """
        key_pem = generate_private_key()

        assert key_pem.startswith("-----BEGIN")


class TestBuildCsr:
    """Tests for build_csr()."""

    def test_returns_valid_pem_csr_with_correct_cn_and_sans(self):
        """
        arrange: A valid RSA private key.
        act: Call build_csr with a common name and SANs.
        assert: Returns a PEM CSR with the correct CN and SAN extension.
        """
        key_pem = generate_private_key()

        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal", "keystone"])

        csr = x509.load_pem_x509_csr(csr_pem.encode())
        cn_attrs = csr.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        assert cn_attrs[0].value == "keystone.internal"
        san_ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)
        assert "keystone.internal" in dns_names
        assert "keystone" in dns_names

    def test_is_deterministic_for_same_inputs(self):
        """
        arrange: A valid RSA private key and fixed CN + SANs.
        act: Call build_csr twice with identical arguments.
        assert: Both calls return CSRs with the same SHA-256 fingerprint.
        """
        key_pem = generate_private_key()

        csr1 = build_csr(key_pem, "keystone.internal", ["keystone.internal"])
        csr2 = build_csr(key_pem, "keystone.internal", ["keystone.internal"])

        assert csr_sha256_hex(csr1) == csr_sha256_hex(csr2)

    def test_different_keys_produce_different_fingerprints(self):
        """
        arrange: Two distinct RSA private keys.
        act: Build CSRs with the same CN + SANs using each key.
        assert: The fingerprints differ.
        """
        key1 = generate_private_key()
        key2 = generate_private_key()

        csr1 = build_csr(key1, "keystone.internal", ["keystone.internal"])
        csr2 = build_csr(key2, "keystone.internal", ["keystone.internal"])

        assert csr_sha256_hex(csr1) != csr_sha256_hex(csr2)

    def test_ip_sans_placed_in_ip_san_extension(self):
        """
        arrange: A valid RSA private key with a mixed SAN list containing an IP address.
        act: Call build_csr with an IP address as one of the SANs.
        assert: The IP address appears in the IP SAN extension, not in DNS SANs.
        """
        key_pem = generate_private_key()

        csr_pem = build_csr(key_pem, "cinder.internal", ["10.149.56.105"])

        csr = x509.load_pem_x509_csr(csr_pem.encode())
        san_ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ip_addrs = san_ext.value.get_values_for_type(x509.IPAddress)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)
        assert ipaddress.IPv4Address("10.149.56.105") in ip_addrs
        assert "10.149.56.105" not in dns_names

    def test_mixed_sans_classified_correctly(self):
        """
        arrange: A valid RSA private key with a list containing both a DNS name and an IP.
        act: Call build_csr.
        assert: DNS name is in DNS SANs; IP address is in IP SANs.
        """
        key_pem = generate_private_key()

        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal", "10.0.0.1"])

        csr = x509.load_pem_x509_csr(csr_pem.encode())
        san_ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)
        ip_addrs = san_ext.value.get_values_for_type(x509.IPAddress)
        assert "keystone.internal" in dns_names
        assert ipaddress.IPv4Address("10.0.0.1") in ip_addrs
        assert "10.0.0.1" not in dns_names

    def test_empty_sans_produces_valid_csr(self):
        """
        arrange: A valid RSA private key.
        act: Call build_csr with an empty SANs list.
        assert: Returns a valid PEM CSR (no SAN extension).
        """
        key_pem = generate_private_key()

        csr_pem = build_csr(key_pem, "keystone.internal", [])

        csr = x509.load_pem_x509_csr(csr_pem.encode())
        cn_attrs = csr.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        assert cn_attrs[0].value == "keystone.internal"


class TestClassifySans:
    """Tests for classify_sans()."""

    def test_ip_addresses_go_to_ip_sans(self):
        """
        arrange: A list containing only IP addresses.
        act: Call classify_sans.
        assert: All entries are in ip_sans; dns_sans is empty.
        """
        dns_sans, ip_sans = classify_sans(["10.149.56.105", "192.168.1.1"])

        assert dns_sans == []
        assert set(ip_sans) == {"10.149.56.105", "192.168.1.1"}

    def test_dns_names_go_to_dns_sans(self):
        """
        arrange: A list containing only DNS names.
        act: Call classify_sans.
        assert: All entries are in dns_sans; ip_sans is empty.
        """
        dns_sans, ip_sans = classify_sans(["keystone.internal", "nova.svc"])

        assert set(dns_sans) == {"keystone.internal", "nova.svc"}
        assert ip_sans == []

    def test_mixed_list_is_classified_correctly(self):
        """
        arrange: A list with both a DNS name and an IP address.
        act: Call classify_sans.
        assert: DNS name in dns_sans; IP address in ip_sans.
        """
        dns_sans, ip_sans = classify_sans(["keystone.internal", "10.0.0.1"])

        assert dns_sans == ["keystone.internal"]
        assert ip_sans == ["10.0.0.1"]

    def test_empty_list_returns_two_empty_lists(self):
        """
        arrange: An empty SANs list.
        act: Call classify_sans.
        assert: Both dns_sans and ip_sans are empty.
        """
        dns_sans, ip_sans = classify_sans([])

        assert dns_sans == []
        assert ip_sans == []

    def test_ipv6_address_classified_as_ip(self):
        """
        arrange: A list containing an IPv6 address.
        act: Call classify_sans.
        assert: IPv6 address is in ip_sans.
        """
        dns_sans, ip_sans = classify_sans(["::1"])

        assert dns_sans == []
        assert ip_sans == ["::1"]


class TestCsrSha256Hex:
    """Tests for csr_sha256_hex()."""

    def test_returns_64_char_lowercase_hex_string(self):
        """
        arrange: A valid PEM CSR.
        act: Call csr_sha256_hex.
        assert: Returns a 64-character lowercase hex string.
        """
        key_pem = generate_private_key()
        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal"])

        fingerprint = csr_sha256_hex(csr_pem)

        assert len(fingerprint) == 64
        assert fingerprint == fingerprint.lower()
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_matches_manual_sha256_of_der_bytes(self):
        """
        arrange: A valid PEM CSR.
        act: Compute fingerprint via csr_sha256_hex and manually via hashlib.
        assert: Both values are identical.
        """
        key_pem = generate_private_key()
        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal"])

        csr_obj = x509.load_pem_x509_csr(csr_pem.encode())
        der = csr_obj.public_bytes(Encoding.DER)
        expected = hashlib.sha256(der).hexdigest()

        assert csr_sha256_hex(csr_pem) == expected
